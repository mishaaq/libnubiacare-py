"""Nubia Care account authentication."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin

import aiohttp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .constants import (
    APP_KEY,
    APP_SECRET,
    BASE_URL,
    DEFAULT_MOBILE_TYPE,
    DEFAULT_TIMEOUT,
    PASSWORD_KEY,
    USER_AGENT,
)
from .exceptions import (
    NubiaApiError,
    NubiaAuthenticationError,
    NubiaConnectionError,
    NubiaProtocolError,
)
from .models import NubiaSession

_AUTH_QUERY_KEYS = ("sign", "timestamp", "nonce", "appKey")


class NubiaAuth:
    """Authenticate Nubia Care accounts and sign each request.

    Home Assistant library guidance expects the auth layer to own signing,
    request construction, and token handling while leaving the caller's
    ``aiohttp.ClientSession`` in charge of the HTTP lifecycle.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str = base64.b64decode(BASE_URL).decode("utf-8"),
        app_key: str = base64.b64decode(APP_KEY).decode("utf-8"),
        app_secret: str = base64.b64decode(APP_SECRET).decode("utf-8"),
        user_agent: str = USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        password_key: bytes = PASSWORD_KEY,
    ) -> None:
        """Initialize authentication with a caller-owned aiohttp session."""
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if len(password_key) not in (16, 24, 32):
            raise ValueError("password_key must be a valid AES key")
        self._session = session
        self._base_url = base_url.rstrip("/") + "/"
        self._app_key = app_key
        self._app_secret = app_secret
        self._user_agent = user_agent
        self._timeout = timeout
        self._password_key = password_key

    async def async_request(
        self,
        method: str,
        path: str,
        *,
        session: NubiaSession | None = None,
        auth_token: str | None = None,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a signed request and return the JSON response body."""
        request_params = dict(params or {})
        request_headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        request_headers.update(headers or {})
        if session is not None:
            request_params.update(
                openid=session.openid,
                accesstoken=session.accesstoken,
            )
            auth_token = session.accesstoken
        if auth_token is not None:
            request_headers["token"] = auth_token

        body_bytes: bytes | None = None
        if json_body is not None:
            body = dict(json_body)
            signed = self._signed_parameters({**request_params, **body})
            signed_query = {key: signed[key] for key in _AUTH_QUERY_KEYS}
            body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        else:
            signed = self._signed_parameters(request_params)
            signed_query = signed

        payload = await self._request_json(
            method,
            path,
            params=signed_query,
            body=body_bytes,
            headers=request_headers,
        )
        if "code" in payload and payload["code"] != 0:
            raise NubiaApiError(
                str(payload.get("msg") or "Nubia Care API request failed")
            )
        return payload

    def _signed_parameters(self, parameters: Mapping[str, Any]) -> dict[str, str]:
        """Build a signed query signature for the API request."""
        signed = {key: str(value) for key, value in parameters.items()}
        signed["timestamp"] = str(time.time_ns() // 1_000_000)
        signed["nonce"] = secrets.token_hex(16)
        signed["appKey"] = self._app_key
        preimage = "".join(f"{key}={signed[key]}&" for key in sorted(signed))
        signed["sign"] = hashlib.sha256(
            (preimage + self._app_secret).encode("utf-8")
        ).hexdigest()
        return signed

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any],
        body: bytes | None,
        headers: Mapping[str, str],
    ) -> dict[str, Any]:
        url = urljoin(self._base_url, path.lstrip("/"))
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except aiohttp.ClientResponseError as err:
            raise NubiaApiError(
                f"Nubia Care returned HTTP {err.status}", status=err.status
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NubiaConnectionError(
                f"Could not communicate with Nubia Care: {err}"
            ) from err
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            raise NubiaProtocolError("Nubia Care returned invalid JSON") from err
        if not isinstance(payload, dict):
            raise NubiaProtocolError("Nubia Care returned a non-object JSON response")
        return payload

    async def async_login(
        self,
        login_name: str,
        password: str,
        *,
        mobile_type: str = DEFAULT_MOBILE_TYPE,
    ) -> NubiaSession:
        """Authenticate and return caller-owned, serializable session tokens."""
        body = {
            "dypwdFlag": "N",
            "loginName": login_name,
            "mobileType": mobile_type,
            "password": self._encrypt_password(password),
        }
        try:
            payload = await self.async_request(
                "POST",
                "api/account/login",
                json_body=body,
                headers={
                    "Accept-Language": "en",
                    "token": "",
                },
            )
        except NubiaApiError as err:
            if err.status is not None:
                raise
            raise NubiaAuthenticationError(str(err)) from err

        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise NubiaProtocolError("login response is missing its data object")
        openid = data.get("openid")
        accesstoken = data.get("accesstoken")
        if not isinstance(openid, str) or not openid:
            raise NubiaProtocolError("login response is missing openid")
        if not isinstance(accesstoken, str) or not accesstoken:
            raise NubiaProtocolError("login response is missing accesstoken")
        return NubiaSession(openid=openid, accesstoken=accesstoken)

    def _encrypt_password(self, password: str) -> str:
        """Encrypt a password using the Nubia Care AES key."""
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self._password_key).encrypt(
            nonce, password.encode("utf-8"), None
        )
        return base64.b64encode(nonce + ciphertext).decode("ascii") + "\n"

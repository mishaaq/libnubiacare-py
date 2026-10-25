"""Tests for authentication and signed requests."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from nubia_care import NubiaAuth, NubiaAuthenticationError, NubiaSession


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self, *, content_type: str | None = None) -> dict[str, object]:
        return self.payload


class _FakeSession:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.request_args: tuple[object, ...] | None = None
        self.request_kwargs: dict[str, object] | None = None

    def request(self, *args: object, **kwargs: object) -> _FakeResponse:
        self.request_args = args
        self.request_kwargs = kwargs
        return _FakeResponse(self.payload)


class AuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_encrypts_password_and_returns_serializable_tokens(self) -> None:
        session = _FakeSession(
            {"code": 0, "data": {"openid": "open-id", "accesstoken": "access-token"}}
        )
        auth = NubiaAuth(session)
        nonce = bytes(range(12))
        with patch("nubia_care.auth.secrets.token_bytes", return_value=nonce):
            tokens = await auth.async_login("user@example.com", "password")

        self.assertEqual(
            tokens.to_dict(),
            {"openid": "open-id", "accesstoken": "access-token"},
        )
        assert session.request_kwargs is not None
        body = json.loads(session.request_kwargs["data"])
        encrypted = base64.b64decode(body["password"])
        self.assertEqual(encrypted[:12], nonce)
        self.assertEqual(
            AESGCM(b"YNSSFWTeip5M2hSzmpoW4dXr0rWTc0Wr").decrypt(
                encrypted[:12], encrypted[12:], None
            ),
            b"password",
        )
        self.assertTrue(body["password"].endswith("\n"))

    async def test_login_signature_covers_body(self) -> None:
        session = _FakeSession(
            {"code": 0, "data": {"openid": "open-id", "accesstoken": "token"}}
        )
        auth = NubiaAuth(session)
        with (
            patch("nubia_care.auth.secrets.token_bytes", return_value=b"\x00" * 12),
            patch("nubia_care.auth.time.time_ns", return_value=1_000_000),
            patch("nubia_care.auth.secrets.token_hex", return_value="a" * 32),
        ):
            await auth.async_login("user", "pass")

        assert session.request_kwargs is not None
        body = json.loads(session.request_kwargs["data"])
        signed = {
            **body,
            "timestamp": "1",
            "nonce": "a" * 32,
            "appKey": "U7yJRy5eO0DKTlNVrnx4z5ICm5y16a4S",
        }
        preimage = "".join(f"{key}={signed[key]}&" for key in sorted(signed))
        expected = hashlib.sha256(
            (preimage + "fR1gX2AEiYxflz8sVsLFzfwTOfk8NzBu").encode()
        ).hexdigest()
        self.assertEqual(session.request_kwargs["params"]["sign"], expected)
        self.assertEqual(
            NubiaSession.from_dict({"openid": "o", "accesstoken": "t"}).to_dict(),
            {"openid": "o", "accesstoken": "t"},
        )

    async def test_rejected_login_raises_authentication_error(self) -> None:
        session = _FakeSession({"code": 1001, "msg": "Invalid credentials"})
        auth = NubiaAuth(session)

        with self.assertRaisesRegex(NubiaAuthenticationError, "Invalid credentials"):
            await auth.async_login("user", "wrong-password")

    async def test_generic_post_sends_session_token_in_header(self) -> None:
        http_session = _FakeSession({"code": 0})
        auth = NubiaAuth(http_session)

        await auth.async_request(
            "POST",
            "api/example",
            session=NubiaSession(openid="open-id", accesstoken="token"),
            json_body={"enabled": True},
        )

        assert http_session.request_kwargs is not None
        self.assertEqual(http_session.request_kwargs["headers"]["token"], "token")
        self.assertEqual(
            json.loads(http_session.request_kwargs["data"]), {"enabled": True}
        )
        self.assertEqual(
            set(http_session.request_kwargs["params"]),
            {"sign", "timestamp", "nonce", "appKey"},
        )

    async def test_generic_get_signs_session_params(self) -> None:
        http_session = _FakeSession({"code": 0})
        auth = NubiaAuth(http_session)

        await auth.async_request(
            "GET",
            "getway/devices/device-1",
            session=NubiaSession(openid="open-id", accesstoken="token"),
        )

        assert http_session.request_kwargs is not None
        self.assertEqual(http_session.request_kwargs["params"]["openid"], "open-id")
        self.assertEqual(http_session.request_kwargs["params"]["accesstoken"], "token")
        self.assertNotIn("token", http_session.request_kwargs["params"])
        self.assertEqual(http_session.request_kwargs["headers"]["token"], "token")

    async def test_firmware_style_request_puts_token_in_header_and_body(self) -> None:
        http_session = _FakeSession({"code": 0, "data": {}})
        auth = NubiaAuth(http_session)

        await auth.async_request(
            "POST",
            "api/device/upgrade",
            auth_token="access-token",
            json_body={"deviceId": "device-1", "token": "access-token"},
        )

        assert http_session.request_kwargs is not None
        self.assertEqual(
            http_session.request_kwargs["headers"]["token"], "access-token"
        )
        self.assertEqual(
            json.loads(http_session.request_kwargs["data"]),
            {"deviceId": "device-1", "token": "access-token"},
        )
        self.assertEqual(
            set(http_session.request_kwargs["params"]),
            {"sign", "timestamp", "nonce", "appKey"},
        )

    def test_session_rejects_malformed_persisted_tokens(self) -> None:
        with self.assertRaisesRegex(ValueError, "openid must be a non-empty string"):
            NubiaSession.from_dict({"openid": None, "accesstoken": "token"})


if __name__ == "__main__":
    unittest.main()

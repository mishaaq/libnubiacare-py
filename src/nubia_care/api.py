"""Nubia Care API resources and endpoint methods."""

from __future__ import annotations

from collections.abc import Mapping

from .auth import NubiaAuth
from .exceptions import NubiaApiError, NubiaDeviceNotFoundError, NubiaProtocolError
from .models import NubiaDevice, NubiaFirmware, NubiaSession


class NubiaAPI:
    """Access Nubia Care resources using the authenticated request layer."""

    def __init__(self, auth: NubiaAuth) -> None:
        """Initialize the API resource facade with a NubiaAuth instance."""
        self._auth = auth

    async def async_get_devices(
        self, session: NubiaSession
    ) -> list[NubiaDevice]:
        """Return the account's related devices."""
        payload = await self._auth.async_request(
            "GET",
            f"getway/accounts/{session.openid}/related-device",
            session=session,
        )
        data = payload.get("data", payload)
        if not isinstance(data, Mapping):
            raise NubiaProtocolError("related-device response is not an object")
        devices: list[NubiaDevice] = []
        entries = data.get("chatGroupDevices") or []
        if not isinstance(entries, list):
            raise NubiaProtocolError(
                "related-device field chatGroupDevices is not a list"
            )
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise NubiaProtocolError(
                    "related-device field chatGroupDevices contains invalid data"
                )
            if not isinstance(entry.get("imei"), str):
                raise NubiaProtocolError(
                    "related-device entry in chatGroupDevices is missing imei"
                )
            devices.append(NubiaDevice(entry))
        return devices

    async def async_get_device(
        self, session: NubiaSession, device_id: str
    ) -> NubiaDevice:
        """Return current details for one device by its API device ID."""
        try:
            payload = await self._auth.async_request(
                "GET",
                f"getway/devices/{device_id}",
                session=session,
            )
        except NubiaApiError as err:
            if err.status != 404:
                raise
            raise NubiaDeviceNotFoundError(
                f"Nubia Care account has no device with ID {device_id!r}",
                status=err.status,
            ) from err
        data = payload.get("data", payload)
        if not isinstance(data, Mapping):
            raise NubiaProtocolError("device detail response is not an object")
        if not isinstance(data.get("imei"), str):
            raise NubiaProtocolError("device detail response is missing imei")
        return NubiaDevice(data)

    async def async_get_device_firmware(
        self, session: NubiaSession, device_id: str
    ) -> NubiaFirmware:
        """Return available and installed firmware versions for a device."""
        payload = await self._auth.async_request(
            "POST",
            "api/device/upgrade",
            auth_token=session.accesstoken,
            json_body={
                "deviceId": device_id,
                "token": session.accesstoken,
            },
        )
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise NubiaProtocolError("firmware response is missing its data object")
        return NubiaFirmware(data)

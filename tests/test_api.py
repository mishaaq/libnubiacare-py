"""Tests for API resource parsing."""

from __future__ import annotations

import unittest

from nubia_care import NubiaAPI, NubiaFirmware, NubiaSession


class _Auth:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def async_request(
        self,
        method: str,
        path: str,
        *,
        session: NubiaSession | None = None,
        auth_token: str | None = None,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            (
                method,
                path,
                {
                    "session": session,
                    "auth_token": auth_token,
                    "json_body": json_body,
                },
            )
        )
        if path == "api/device/upgrade":
            return {
                "code": 0,
                "data": {
                    "firmware": "",
                    "fileSize": "",
                    "releaseNote": "",
                    "deviceFirmware": "1.2.3",
                },
            }
        if path.startswith("getway/devices/"):
            return {
                "imei": path.rsplit("/", 1)[-1],
                "name": "Watch",
                "lastLocation": {
                    "lat": "51.5",
                    "lon": "-0.1",
                    "timestamp": 123,
                },
            }
        return {
            "code": 0,
                "chatGroupDevices": [
                    {"imei": "device-1", "name": "Watch"},
                    {"imei": "device-2", "name": "Shared"},
                ],
            }


class APITests(unittest.IsolatedAsyncioTestCase):
    async def test_related_devices_include_owned_and_shared_devices(self) -> None:
        api = NubiaAPI(_Auth())  # type: ignore[arg-type]
        devices = await api.async_get_devices(
            NubiaSession(openid="open-id", accesstoken="token")
        )

        self.assertEqual([device.imei for device in devices], ["device-1", "device-2"])
        self.assertEqual([device.id for device in devices], ["device-1", "device-2"])
        self.assertEqual(devices[0].name, "Watch")

    async def test_get_device_queries_by_device_id(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")

        device = await api.async_get_device(session, "device-1")

        self.assertEqual(device.id, "device-1")
        self.assertEqual(auth.calls[0][1], "getway/devices/device-1")
        self.assertIsNotNone(device.location)
        assert device.location is not None
        self.assertEqual(device.location.latitude, "51.5")
        self.assertEqual(device.location.longitude, "-0.1")

    async def test_get_device_firmware_queries_by_device_id(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")

        firmware = await api.async_get_device_firmware(session, "device-1")

        self.assertIsInstance(firmware, NubiaFirmware)
        self.assertEqual(firmware.device_firmware, "1.2.3")
        self.assertEqual(auth.calls[0][1], "api/device/upgrade")
        self.assertEqual(
            auth.calls[0][2]["json_body"],
            {"deviceId": "device-1", "token": "token"},
        )
        self.assertEqual(auth.calls[0][2]["auth_token"], "token")


if __name__ == "__main__":
    unittest.main()

"""Tests for API resource parsing."""

from __future__ import annotations

import unittest
from decimal import Decimal

from nubia_care import (
    NubiaAPI,
    NubiaDevice,
    NubiaDeviceConfiguration,
    NubiaDeviceState,
    NubiaFirmware,
    NubiaFocusScheduleInterval,
    NubiaFocusScheduleRule,
    NubiaMessageTooLongError,
    NubiaProtocolError,
    NubiaSentMessage,
    NubiaSession,
    NubiaWeekMask,
)


class _Auth:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []
        self.message_response: dict[str, object] = {
            "id": "message-1",
            "content": "Hello!",
        }
        self.configuration_response: dict[str, object] = {
            "code": 0,
            "data": {
                "callWhitelist": 1,
                "autoAnswer": 2,
                "locMode": 3,
                "longLifeMode": 1,
                "disBan": [{"week": "1000000", "interval": []}],
                "bootOffStartTime": "06:00",
                "bootOffEndTime": "22:30",
                "smsSwitch": 1,
                "smsReceiveOnlyMember": 2,
                "positionSwitch": 1,
                "batterySwitch": 2,
                "sportsSwitch": 1,
                "appSwitch": 2,
            },
        }

    async def async_request(
        self,
        method: str,
        path: str,
        *,
        session: NubiaSession | None = None,
        auth_token: str | None = None,
        json_body: dict[str, object] | None = None,
        form_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            (
                method,
                path,
                {
                    "session": session,
                    "auth_token": auth_token,
                    "json_body": json_body,
                    "form_body": form_body,
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
        if path == "api/device/query/systemconfig":
            return self.configuration_response
        if path.startswith("getway/single/"):
            return self.message_response
        if path.startswith("getway/devices/"):
            return {
                "imei": path.rsplit("/", 1)[-1],
                "name": "Watch",
                "battery": {"updateTime": 123, "percent": 57},
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

        self.assertIsInstance(device, NubiaDeviceState)
        self.assertEqual(device.id, "device-1")
        self.assertEqual(device.battery_level, 57)
        self.assertEqual(auth.calls[0][1], "getway/devices/device-1")
        self.assertIsNotNone(device.location)
        assert device.location is not None
        self.assertEqual(device.location.latitude, "51.5")
        self.assertEqual(device.location.longitude, "-0.1")

    async def test_get_device_configuration_parses_relevant_settings(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")

        config = await api.async_get_device_configuration(session, "device-1")

        self.assertIsInstance(config, NubiaDeviceConfiguration)
        self.assertEqual(auth.calls[0][0], "POST")
        self.assertEqual(auth.calls[0][1], "api/device/query/systemconfig")
        self.assertEqual(
            auth.calls[0][2]["json_body"],
            {"deviceId": "device-1", "token": "token"},
        )
        self.assertEqual(auth.calls[0][2]["auth_token"], "token")
        self.assertTrue(config.call_whitelist)
        self.assertFalse(config.auto_answer)
        self.assertEqual(config.loc_mode, 3)
        self.assertTrue(config.long_life_mode)
        self.assertEqual(config.focus_schedule, ({"week": "1000000", "interval": []},))
        self.assertEqual(config.boot_off_start_time, "06:00")
        self.assertEqual(config.boot_off_end_time, "22:30")
        self.assertTrue(config.sms_switch)
        self.assertFalse(config.sms_receive_only_member)
        self.assertTrue(config.position_switch)
        self.assertFalse(config.battery_switch)
        self.assertTrue(config.sports_switch)
        self.assertFalse(config.app_switch)

    async def test_get_device_configuration_requires_data_object(self) -> None:
        auth = _Auth()
        auth.configuration_response = {"code": 0, "data": None}
        api = NubiaAPI(auth)  # type: ignore[arg-type]

        with self.assertRaisesRegex(
            NubiaProtocolError,
            "device configuration response is missing its data object",
        ):
            await api.async_get_device_configuration(
                NubiaSession(openid="open-id", accesstoken="token"),
                "device-1",
            )

    def test_device_location_preserves_decimal_precision(self) -> None:
        latitude = Decimal("51.1234567890123456789012345")
        longitude = Decimal("-0.1234567890123456789012345")
        device = NubiaDevice(
            {"imei": "device-1", "lastLocation": {"lat": latitude, "lon": longitude}}
        )

        assert device.location is not None
        self.assertIs(device.location.latitude, latitude)
        self.assertIs(device.location.longitude, longitude)

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

    async def test_request_last_location_uses_device_endpoint(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")

        await api.async_request_last_location(session, "device-1")

        self.assertEqual(auth.calls[0][0], "POST")
        self.assertEqual(
            auth.calls[0][1],
            "getway/devices/device-1/location/last",
        )
        self.assertEqual(
            auth.calls[0][2]["form_body"],
            {"openid": "open-id", "accesstoken": "token", "token": "token"},
        )

    async def test_send_text_message_uses_single_device_endpoint(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")

        response = await api.async_send_text_message(session, "device-1", "Hello!")

        self.assertIsInstance(response, NubiaSentMessage)
        self.assertEqual(response.id, "message-1")
        self.assertEqual(response.content, "Hello!")
        self.assertEqual(response.raw_data, {"id": "message-1", "content": "Hello!"})
        self.assertEqual(auth.calls[0][0], "POST")
        self.assertEqual(auth.calls[0][1], "getway/single/device-1/message")
        self.assertEqual(
            auth.calls[0][2]["json_body"],
            {
                "accesstoken": "token",
                "content": "Hello!",
                "duration": 0.0,
                "openid": "open-id",
                "type": 1,
                "token": "token",
            },
        )
        self.assertEqual(auth.calls[0][2]["auth_token"], "token")

    async def test_send_text_message_allows_64_utf16_code_units(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        content = "a" * 62 + "😀"

        await api.async_send_text_message(
            NubiaSession(openid="open-id", accesstoken="token"),
            "device-1",
            content,
        )

        self.assertEqual(auth.calls[0][2]["json_body"], {
            "accesstoken": "token",
            "content": content,
            "duration": 0.0,
            "openid": "open-id",
            "type": 1,
            "token": "token",
        })

    async def test_send_text_message_rejects_more_than_64_utf16_code_units(
        self,
    ) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        content = "a" * 63 + "😀"

        with self.assertRaises(NubiaMessageTooLongError) as err:
            await api.async_send_text_message(
                NubiaSession(openid="open-id", accesstoken="token"),
                "device-1",
                content,
            )

        self.assertEqual(err.exception.max_length, 64)
        self.assertEqual(auth.calls, [])

    async def test_install_device_firmware_uses_system_config_endpoint(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")

        await api.async_install_device_firmware(session, "device-1")

        self.assertEqual(auth.calls[0][0], "POST")
        self.assertEqual(auth.calls[0][1], "api/device/save/systemconfig")
        self.assertEqual(
            auth.calls[0][2]["json_body"],
            {"deviceId": "device-1", "type": 11, "token": "token"},
        )
        self.assertEqual(auth.calls[0][2]["auth_token"], "token")

    async def test_save_device_focus_schedule_uses_type_six(self) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        session = NubiaSession(openid="open-id", accesstoken="token")
        rule = NubiaFocusScheduleRule(
            name="Monday",
            week=NubiaWeekMask("1000000"),
            status=1,
            intervals=(
                NubiaFocusScheduleInterval(
                    interval_name="am",
                    begin_time="07:30",
                    end_time="11:55",
                    status=1,
                ),
                NubiaFocusScheduleInterval(interval_name="pm", status=2),
            ),
        )

        await api.async_save_device_focus_schedule(session, "device-1", rule)

        self.assertEqual(auth.calls[0][0], "POST")
        self.assertEqual(auth.calls[0][1], "api/device/save/systemconfig")
        self.assertEqual(
            auth.calls[0][2]["json_body"],
            {
                "deviceId": "device-1",
                "rule": {
                    "del": 0,
                    "interval": [
                        {
                            "beginTime": "07:30",
                            "endTime": "11:55",
                            "intervalName": "am",
                            "status": 1,
                        },
                        {"intervalName": "pm", "status": 2},
                    ],
                    "name": "Monday",
                    "status": 1,
                    "week": "1000000",
                },
                "type": 6,
                "token": "token",
            },
        )
        self.assertEqual(auth.calls[0][2]["auth_token"], "token")

    async def test_save_device_focus_schedule_includes_rule_id_and_delete_flag(
        self,
    ) -> None:
        auth = _Auth()
        api = NubiaAPI(auth)  # type: ignore[arg-type]
        rule = NubiaFocusScheduleRule(
            name="Weekdays",
            week=NubiaWeekMask("1111100"),
            status=2,
            intervals=(),
            rule_id="rule-1",
            delete=1,
        )

        await api.async_save_device_focus_schedule(
            NubiaSession(openid="open-id", accesstoken="token"),
            "device-1",
            rule,
        )

        body = auth.calls[0][2]["json_body"]
        assert isinstance(body, dict)
        self.assertEqual(
            body["rule"],
            {
                "del": 1,
                "interval": [],
                "name": "Weekdays",
                "ruleId": "rule-1",
                "status": 2,
                "week": "1111100",
            },
        )


if __name__ == "__main__":
    unittest.main()

"""Tests for the account verification command."""

from __future__ import annotations

import json
import unittest
from decimal import Decimal

from scripts.nubia_care_cli import format_device_summary
from nubia_care.models import (
    NubiaDevice,
    NubiaDeviceConfiguration,
    NubiaDeviceState,
)


class CLITests(unittest.TestCase):
    def test_summary_merges_latest_device_data_and_location(self) -> None:
        related = NubiaDevice(
            {
                "imei": "device-1",
                "name": "Watch",
                "onlineStatus": 1,
                "battery": {"percent": 80},
                "lastLocation": {"lat": "1", "lon": "2"},
            }
        )
        details = NubiaDeviceState(
            {
                "imei": "device-1",
                "name": "Watch",
                "model": "EW2301",
                "lastLocation": {
                    "lat": "3",
                    "lon": "4",
                    "timestamp": 123,
                },
            }
        )
        configuration = NubiaDeviceConfiguration(
            {
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
            }
        )

        summary = format_device_summary(related, details, configuration)

        self.assertEqual(summary["id"], "device-1")
        self.assertEqual(summary["properties"]["onlineStatus"], 1)
        self.assertEqual(summary["properties"]["model"], "EW2301")
        self.assertEqual(
            summary["location"],
            {"lat": "3", "lon": "4", "timestamp": 123},
        )
        self.assertEqual(
            summary["configuration"],
            {
                "call_whitelist": True,
                "auto_answer": False,
                "loc_mode": 3,
                "long_life_mode": True,
                "focus_schedule": [{"week": "1000000", "interval": []}],
                "boot_off_start_time": "06:00",
                "boot_off_end_time": "22:30",
                "sms_switch": True,
                "sms_receive_only_member": False,
                "position_switch": True,
                "battery_switch": False,
                "sports_switch": True,
                "app_switch": False,
            },
        )
        self.assertNotIn("lastLocation", summary["properties"])

    def test_summary_handles_missing_location(self) -> None:
        device = NubiaDevice({"imei": "device-1", "name": "Watch"})
        details = NubiaDeviceState({"imei": "device-1"})
        configuration = NubiaDeviceConfiguration({})

        summary = format_device_summary(device, details, configuration)

        self.assertEqual(summary["name"], "Watch")
        self.assertIsNone(summary["location"])

    def test_summary_keeps_decimal_coordinates_json_serializable(self) -> None:
        latitude = Decimal("51.1234567890123456789012345")
        longitude = Decimal("-0.1234567890123456789012345")
        related = NubiaDevice(
            {
                "imei": "device-1",
                "name": "Watch",
            }
        )
        details = NubiaDeviceState(
            {
                "imei": "device-1",
                "lastLocation": {"lat": latitude, "lon": longitude},
            }
        )
        configuration = NubiaDeviceConfiguration({})

        encoded = json.dumps(format_device_summary(related, details, configuration))
        decoded = json.loads(encoded)

        self.assertEqual(decoded["location"]["lat"], str(latitude))
        self.assertEqual(decoded["location"]["lon"], str(longitude))


if __name__ == "__main__":
    unittest.main()

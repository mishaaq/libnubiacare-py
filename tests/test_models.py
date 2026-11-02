"""Tests for Nubia API data models."""

from __future__ import annotations

import unittest

from nubia_care import DeviceFeatures, NubiaDevice


class NubiaDeviceTests(unittest.TestCase):
    def test_battery_level_reads_nested_battery_percent(self) -> None:
        device = NubiaDevice(
            {
                "imei": "device-1",
                "battery": {"updateTime": 1793651007907, "percent": 76},
            }
        )

        self.assertEqual(device.battery_level, 76)

    def test_battery_level_is_none_when_missing_or_invalid(self) -> None:
        for raw_data in (
            {"imei": "device-1"},
            {"imei": "device-1", "battery": None},
            {"imei": "device-1", "battery": {"percent": "76"}},
            {"imei": "device-1", "battery": {"percent": True}},
        ):
            with self.subTest(raw_data=raw_data):
                self.assertIsNone(NubiaDevice(raw_data).battery_level)

    def test_parses_device_properties(self) -> None:
        device = NubiaDevice(
            {
                "imei": "device-1",
                "deviceType": 0,
                "permissions": "basic,positioning,management,location_y",
                "model": "EW2301",
                "modeType": "ZTE Watch K1 Pro",
            }
        )

        self.assertEqual(device.device_type, 0)
        self.assertEqual(
            device.permissions,
            ("basic", "positioning", "management", "location_y"),
        )
        self.assertEqual(device.model, "EW2301")
        self.assertEqual(device.model_name, "ZTE Watch K1 Pro")

    def test_features_query_one_or_all_supported_features(self) -> None:
        device = NubiaDevice(
            {
                "imei": "device-1",
                "support_reset": 0,
                "support_step": 1,
                "support_sos": True,
                "support_wifi": "0",
            }
        )

        self.assertIsInstance(device.features, DeviceFeatures)
        self.assertTrue(device.features.supports("step"))
        self.assertTrue(device.features.supports("support_sos"))
        self.assertFalse(device.features.supports("reset"))
        self.assertFalse(device.features.supports("wifi"))
        self.assertEqual(device.features.available_features(), ("step", "sos"))

    def test_unknown_feature_is_not_silently_normalized(self) -> None:
        device = NubiaDevice({"imei": "device-1", "support_sos": 1})

        with self.assertRaisesRegex(KeyError, "unknown device feature"):
            device.features.supports("missing")

    def test_missing_permissions_are_empty(self) -> None:
        device = NubiaDevice({"imei": "device-1"})

        self.assertEqual(device.permissions, ())


if __name__ == "__main__":
    unittest.main()

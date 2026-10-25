"""Tests for the account verification command."""

from __future__ import annotations

import unittest

from scripts.nubia_care_cli import format_device_summary
from nubia_care.models import NubiaDevice


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
        details = NubiaDevice(
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

        summary = format_device_summary(related, details)

        self.assertEqual(summary["id"], "device-1")
        self.assertEqual(summary["properties"]["onlineStatus"], 1)
        self.assertEqual(summary["properties"]["model"], "EW2301")
        self.assertEqual(
            summary["location"],
            {"lat": "3", "lon": "4", "timestamp": 123},
        )
        self.assertNotIn("lastLocation", summary["properties"])

    def test_summary_handles_missing_location(self) -> None:
        device = NubiaDevice({"imei": "device-1", "name": "Watch"})

        summary = format_device_summary(device, device)

        self.assertIsNone(summary["location"])


if __name__ == "__main__":
    unittest.main()

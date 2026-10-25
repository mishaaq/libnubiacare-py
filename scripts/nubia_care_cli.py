#!/usr/bin/env python3
"""Verify Nubia Care API access from a source checkout."""

from __future__ import annotations

import asyncio
import getpass
import json
import sys
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nubia_care import (  # noqa: E402
    NubiaAPI,
    NubiaAuth,
    NubiaDevice,
    NubiaError,
)


def format_device_summary(
    related_device: NubiaDevice, details: NubiaDevice
) -> dict[str, Any]:
    """Combine related-device properties with the latest device details."""
    properties = {**related_device.raw_data, **details.raw_data}
    location = properties.pop("lastLocation", None)
    if not isinstance(location, Mapping):
        location = None
    return {
        "id": details.id,
        "name": details.name,
        "properties": _json_compatible(properties),
        "location": _json_compatible(location),
    }


def _json_compatible(value: Any) -> Any:
    """Convert precise decimal values to JSON strings without rounding."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _json_compatible(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    return value


async def _async_run(login_name: str, password: str) -> None:
    async with aiohttp.ClientSession() as http_session:
        auth = NubiaAuth(http_session)
        account_session = await auth.async_login(login_name, password)
        api = NubiaAPI(auth)
        devices = await api.async_get_devices(account_session)

        if not devices:
            print("No related devices found.")
            return

        for related_device in devices:
            device_id = related_device.id
            if device_id is None:
                print("Skipping related device without an ID.", file=sys.stderr)
                continue
            details = await api.async_get_device(account_session, device_id)
            print(
                json.dumps(
                    format_device_summary(related_device, details),
                    ensure_ascii=False,
                    indent=2,
                )
            )


def main() -> int:
    """Prompt for account credentials and print related device summaries."""
    login_name = input("Nubia Care login: ").strip()
    if not login_name:
        print("A login name is required.", file=sys.stderr)
        return 2

    password = getpass.getpass("Nubia Care password: ")
    if not password:
        print("A password is required.", file=sys.stderr)
        return 2

    try:
        asyncio.run(_async_run(login_name, password))
    except NubiaError as err:
        print(f"Unable to retrieve Nubia Care devices: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

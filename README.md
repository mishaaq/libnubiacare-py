# libnubiacare-py

An asynchronous Python client for the Nubia Care API used by ZTE Kids watches.
The library handles request signing, password encryption, and the API's JSON
responses. It leaves the `aiohttp.ClientSession` and authenticated session data
under the caller's control, which makes it suitable for Home Assistant
integrations.

## Installation

```console
python -m pip install libnubiacare-py
```

## Usage

```python
import asyncio

import aiohttp

from nubia_care import NubiaAPI, NubiaAuth


async def main() -> None:
    async with aiohttp.ClientSession() as http_session:
        auth = NubiaAuth(http_session)
        credentials = await auth.async_login("account@example.com", "password")

        api = NubiaAPI(auth)
        devices = await api.async_get_devices(credentials)
        for device in devices:
            details = await api.async_get_device(credentials, device.id)
            print(details.id, details.name)
            if details.location is not None:
                print(details.location.latitude, details.location.longitude)

            firmware = await api.async_get_device_firmware(credentials, device.id)
            print(firmware.device_firmware, firmware.firmware)

        # Store credentials.to_dict() in the application's own config entry
        # or credential store. The library does not retain login credentials.


asyncio.run(main())
```

`NubiaAuth` owns the built-in request signing and HTTP handling, while the
caller provides the shared `aiohttp.ClientSession` and keeps the returned
`NubiaSession` in their persistence layer. The API provides typed device and
location views while retaining each response in `raw_data`.
`NubiaAPI.async_get_device()` returns a `NubiaDeviceState` containing the
device ID, current battery level, latest location, and other device details.
Use `NubiaDevice.id` as the identifier for device-details and firmware
requests. `NubiaAPI.async_install_device_firmware(session, device_id)` asks a
device to install its available firmware update; the API does not expose
installation progress.
JSON decimal numbers are decoded as `Decimal`, so numeric latitude and
longitude values retain their reported precision; coordinate values returned
as strings remain strings.

The API host, mobile client description, and protocol keys can be supplied to
`NubiaAuth` for compatible service variants. See the class documentation and
type signatures for the supported options.

`NubiaDevice` exposes device capabilities through `device.features.supports()`
and `device.features.available_features()`. It also exposes parsed
`battery_level`, `device_type`, `permissions`, `model`, and `model_name`
properties; `battery_level` reads the `percent` value from the API's nested
`battery` object and is `None` when that value is unavailable. The original API
response remains available as `device.raw_data`.

## CLI

The repository includes a simple verification script for checking access to the
Nubia Care API from a source checkout:

```console
PYTHONPATH=src .venv/bin/python scripts/nubia_care_cli.py
```

The script prompts for a Nubia Care login and password, then prints a JSON
summary for each related device, including the latest device metadata and
location information. It is intended for local validation and troubleshooting,
and it is not part of the installed library API.

## Development

Create and activate a virtual environment, then install the project in editable
mode from the repository root. This installs the dependencies and makes the
`src/nubia_care` package importable without setting `PYTHONPATH`:

```console
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Run the test suite:

```console
python -m unittest discover -s tests
```

Releases are published to PyPI from GitHub Releases.
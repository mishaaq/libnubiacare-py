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
location views while retaining each response in `raw_data`. Use
`NubiaDevice.id` as the identifier for device-details and firmware requests.

The API host, mobile client description, and protocol keys can be supplied to
`NubiaAuth` for compatible service variants. See the class documentation and
type signatures for the supported options.

`NubiaDevice` exposes device capabilities through `device.features.supports()`
and `device.features.available_features()`. It also exposes parsed
`device_type`, `permissions`, `model`, and `model_name` properties; the
original API response remains available as `device.raw_data`.

## Development

Run the test suite with:

```console
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Releases are published to PyPI from GitHub Releases.
"""Small data views over Nubia Care API responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


_FEATURE_PREFIX = "support_"


@dataclass(frozen=True, slots=True)
class NubiaSession:
    """JSON-serializable account tokens returned by the login endpoint."""

    openid: str
    accesstoken: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NubiaSession:
        """Create a session from a previously persisted dictionary."""
        try:
            openid = data["openid"]
            accesstoken = data["accesstoken"]
        except KeyError as err:
            raise ValueError(f"missing Nubia session field: {err.args[0]}") from err
        if not isinstance(openid, str) or not openid:
            raise ValueError("Nubia session openid must be a non-empty string")
        if not isinstance(accesstoken, str) or not accesstoken:
            raise ValueError("Nubia session accesstoken must be a non-empty string")
        return cls(openid=openid, accesstoken=accesstoken)

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation of these tokens."""
        return {"openid": self.openid, "accesstoken": self.accesstoken}


@dataclass(frozen=True, slots=True)
class NubiaLocation:
    """A watch's latest location, retaining the API's field names and values."""

    raw_data: Mapping[str, Any]

    @property
    def latitude(self) -> str | None:
        """Return the API's latitude value."""
        return self.raw_data.get("lat")

    @property
    def longitude(self) -> str | None:
        """Return the API's longitude value."""
        return self.raw_data.get("lon")

    @property
    def timestamp(self) -> int | None:
        """Return the API's location timestamp."""
        return self.raw_data.get("timestamp")

    @property
    def radius(self) -> float | None:
        """Return the API's reported location radius."""
        return self.raw_data.get("radius")

    @property
    def location_query_type(self) -> str:
        """Return the API's location source."""
        return self.raw_data.get("loc_type", "")


@dataclass(frozen=True, slots=True)
class DeviceFeatures:
    """Feature support flags reported for a Nubia device."""

    raw_data: Mapping[str, Any]

    def supports(self, feature: str) -> bool:
        """Return whether a named feature is supported by the device.

        Feature names may be passed with or without the API's ``support_``
        prefix. Raises ``KeyError`` when the API did not report that feature.
        """
        candidate = feature.removeprefix(_FEATURE_PREFIX)
        lookup = feature if feature.startswith(_FEATURE_PREFIX) else f"{_FEATURE_PREFIX}{candidate}"
        if lookup not in self.raw_data and candidate not in self.raw_data:
            raise KeyError(f"unknown device feature: {feature}")
        value = self.raw_data.get(lookup)
        if value is None:
            value = self.raw_data.get(candidate)
        return value is True or value == 1 or value == "1"

    def available_features(self) -> tuple[str, ...]:
        """Return the names of all features supported by this device."""
        return tuple(
            name.removeprefix(_FEATURE_PREFIX)
            for name in self.raw_data
            if self.supports(name)
        )


class DeviceImei:
    """Expose the device identifier in a device response."""

    __slots__ = ()

    raw_data: Mapping[str, Any]

    @property
    def imei(self) -> str | None:
        """Return the device's IMEI."""
        return self.raw_data.get("imei")


class DeviceModel:
    """Expose the device model in a device response."""

    __slots__ = ()

    raw_data: Mapping[str, Any]

    @property
    def model(self) -> str | None:
        """Return the device model code."""
        return self.raw_data.get("model")


class DeviceBattery:
    """Expose the battery status in a device response."""

    __slots__ = ()

    raw_data: Mapping[str, Any]

    @property
    def battery_level(self) -> int | None:
        """Return the current battery percentage, if reported."""
        battery = self.raw_data.get("battery")
        if not isinstance(battery, Mapping):
            return None
        percent = battery.get("percent")
        if isinstance(percent, bool) or not isinstance(percent, int):
            return None
        return percent


class DeviceLocation:
    """Expose the latest location in a device response."""

    __slots__ = ()

    raw_data: Mapping[str, Any]

    @property
    def location(self) -> NubiaLocation | None:
        """Return the most recent location, if one has been reported."""
        location = self.raw_data.get("lastLocation")
        if not isinstance(location, Mapping):
            return None
        return NubiaLocation(location)


@dataclass(frozen=True, slots=True)
class NubiaDevice(DeviceImei, DeviceModel, DeviceBattery, DeviceLocation):
    """A watch or other device returned by the related-device endpoint."""

    raw_data: Mapping[str, Any]

    @property
    def id(self) -> str | None:
        """Return the API device ID."""
        return self.imei

    @property
    def name(self) -> str | None:
        """Return the API-provided device name."""
        return self.raw_data.get("name")

    @property
    def features(self) -> DeviceFeatures:
        """Return the device's supported-feature view."""
        feature_data: dict[str, Any] = {}
        for key, value in self.raw_data.items():
            if not key.startswith(_FEATURE_PREFIX):
                continue
            feature_data[key.removeprefix(_FEATURE_PREFIX)] = value
        return DeviceFeatures(feature_data)

    @property
    def device_type(self) -> str | None:
        """Return the API's device type value."""
        return self.raw_data.get("deviceType")

    @property
    def permissions(self) -> tuple[str, ...]:
        """Return the account permissions listed by the API."""
        value = self.raw_data.get("permissions")
        if not isinstance(value, str) or not value:
            return ()
        return tuple(
            permission.strip()
            for permission in value.split(",")
            if permission.strip()
        )


@dataclass(frozen=True, slots=True)
class NubiaDeviceState(DeviceImei, DeviceModel, DeviceBattery, DeviceLocation):
    """Current state reported for a device."""

    raw_data: Mapping[str, Any]

    @property
    def id(self) -> str | None:
        """Return the API device ID."""
        return self.imei

    @property
    def model_name(self) -> str | None:
        """Return the human-readable device model name."""
        return self.raw_data.get("modeType")


@dataclass(frozen=True, slots=True)
class NubiaFirmware:
    """Firmware update information returned for a device."""

    raw_data: Mapping[str, Any]

    @property
    def firmware(self) -> str | None:
        """Return the available firmware version, if an update exists."""
        return self.raw_data.get("firmware")

    @property
    def file_size(self) -> str | None:
        """Return the firmware package size as reported by the API."""
        return self.raw_data.get("fileSize")

    @property
    def release_note(self) -> str | None:
        """Return the API-provided firmware release notes."""
        return self.raw_data.get("releaseNote")

    @property
    def device_firmware(self) -> str | None:
        """Return the firmware version currently installed on the device."""
        return self.raw_data.get("deviceFirmware")


@dataclass(frozen=True, slots=True)
class NubiaSentMessage:
    """A message created for a Nubia Care device."""

    raw_data: Mapping[str, Any]

    @property
    def id(self) -> str | None:
        """Return the API message ID."""
        return self.raw_data.get("id")

    @property
    def content(self) -> str | None:
        """Return the API message content."""
        return self.raw_data.get("content")

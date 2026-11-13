"""Exceptions raised by the Nubia Care client."""


class NubiaError(Exception):
    """Base exception for Nubia Care library errors."""


class NubiaAuthenticationError(NubiaError):
    """The API rejected the supplied login credentials."""


class NubiaConnectionError(NubiaError):
    """The client could not connect to the API."""


class NubiaApiError(NubiaError):
    """The API returned an HTTP or application-level error."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class NubiaDeviceNotFoundError(NubiaApiError):
    """The requested device is not associated with the account."""


class NubiaProtocolError(NubiaError):
    """The API response did not match the expected JSON protocol."""


class NubiaMessageTooLongError(NubiaError):
    """The message content exceeds Nubia Care's character limit."""

    def __init__(self, max_length: int) -> None:
        self.max_length = max_length
        super().__init__(
            f"message content exceeds the limit of {max_length} UTF-16 code units"
        )

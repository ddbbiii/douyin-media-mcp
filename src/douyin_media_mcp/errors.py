from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .redaction import redact_text


@dataclass
class MediaMCPError(Exception):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.message = redact_text(self.message)
        if self.details:
            self.details = {
                str(key): redact_text(str(value)) for key, value in self.details.items()
            }
        super().__init__(self.message)

    def payload(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "error",
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            },
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


def safe_error(exc: Exception, *, code: str = "RESOLVER_CHANGED") -> MediaMCPError:
    if isinstance(exc, MediaMCPError):
        return exc
    return MediaMCPError(code, f"{type(exc).__name__}: {exc}")

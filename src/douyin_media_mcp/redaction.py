from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\r\n]+)"),
    re.compile(r"(?i)(cookie\s*[:=]\s*)([^\r\n]+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]+)"),
    re.compile(r"(?i)(sessionid|sid_tt|passport_csrf_token|msToken)(=|%3D)[^&\s]+"),
)


def redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return "<redacted-url>"
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return "<redacted-url>"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def redact_text(value: str) -> str:
    text = _URL_PATTERN.sub(lambda match: redact_url(match.group(0)), value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}<redacted>", text)
    return text


def redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("cookie", "authorization", "signed_url")):
                cleaned[str(key)] = "<redacted>"
            else:
                cleaned[str(key)] = redact_mapping(item)
        return cleaned
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, tuple):
        return [redact_mapping(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value

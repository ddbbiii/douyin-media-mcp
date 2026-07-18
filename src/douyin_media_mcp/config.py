from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    request_timeout_seconds: float = 20.0
    browser_timeout_seconds: float = 35.0
    browser_settle_seconds: float = 3.0
    browser_headless: bool = False
    browser_channel: str | None = "chrome"
    browser_profile_dir: Path | None = None
    cdp_url: str | None = None
    use_browser_cookies: bool = False
    download_retries: int = 3
    media_download_concurrency: int = 2
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    @classmethod
    def from_env(cls) -> Settings:
        profile = os.getenv("DOUYIN_MCP_BROWSER_PROFILE")
        channel = os.getenv("DOUYIN_MCP_BROWSER_CHANNEL", "chrome").strip()
        return cls(
            request_timeout_seconds=float(os.getenv("DOUYIN_MCP_REQUEST_TIMEOUT", "20")),
            browser_timeout_seconds=float(os.getenv("DOUYIN_MCP_BROWSER_TIMEOUT", "35")),
            browser_settle_seconds=float(os.getenv("DOUYIN_MCP_BROWSER_SETTLE", "3")),
            browser_headless=_env_bool("DOUYIN_MCP_BROWSER_HEADLESS", False),
            browser_channel=channel or None,
            browser_profile_dir=Path(profile).expanduser().resolve() if profile else None,
            cdp_url=os.getenv("DOUYIN_MCP_CDP_URL") or None,
            use_browser_cookies=_env_bool("DOUYIN_MCP_USE_BROWSER_COOKIES", False),
            download_retries=max(1, int(os.getenv("DOUYIN_MCP_DOWNLOAD_RETRIES", "3"))),
            media_download_concurrency=max(
                1, int(os.getenv("DOUYIN_MCP_DOWNLOAD_CONCURRENCY", "2"))
            ),
            ffmpeg_path=os.getenv("DOUYIN_MCP_FFMPEG", "ffmpeg"),
            ffprobe_path=os.getenv("DOUYIN_MCP_FFPROBE", "ffprobe"),
        )

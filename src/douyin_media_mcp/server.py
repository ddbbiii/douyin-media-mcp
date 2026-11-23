from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .errors import MediaMCPError, safe_error
from .service import DouyinMediaService

mcp = FastMCP(
    "Douyin Media MCP",
    instructions=(
        "Resolve and download user-authorized Douyin media. "
        "Never use these tools to bypass login, CAPTCHA, DRM, paywalls, or access controls. "
        "resolve_douyin_url does not expose temporary signed media URLs."
    ),
    json_response=True,
)


def _service() -> DouyinMediaService:
    return DouyinMediaService()


@mcp.tool()
async def resolve_douyin_url(
    url: str,
    browser_mode: str = "auto",
) -> dict[str, Any]:
    """Resolve a Douyin share URL without saving media or exposing signed stream URLs.

    Use browser_mode="auto" normally. "direct" only expands redirects; "browser" forces
    Playwright network observation. Human verification challenges are reported, never bypassed.
    """
    try:
        result = await _service().resolve(url, browser_mode)  # type: ignore[arg-type]
        return result.public_payload()
    except Exception as exc:
        return safe_error(exc).payload()


@mcp.tool()
async def download_douyin_media(
    url: str,
    output_dir: str,
    quality: str = "best",
    filename: str | None = None,
    overwrite: bool = False,
    keep_separate_streams: bool = False,
) -> dict[str, Any]:
    """Download, stream-copy mux, probe, decode-check, and hash authorized Douyin media.

    Audio can be independent or embedded in the selected video stream; both are preserved.
    A validated video-only file is returned only when the final media actually has no audio.
    Signed URLs are never exposed.
    """
    try:
        return await _service().download(
            url,
            output_dir,
            quality,  # type: ignore[arg-type]
            filename,
            overwrite,
            keep_separate_streams,
        )
    except MediaMCPError as exc:
        return exc.payload()
    except Exception as exc:
        return safe_error(exc, code="DOWNLOAD_FAILED").payload()


@mcp.tool()
async def probe_media(
    path: str, decode_check: bool = True, require_audio: bool = False
) -> dict[str, Any]:
    """Inspect a local media file with FFprobe, SHA-256, and optional three-point decoding."""
    try:
        result = await _service().probe(path, decode_check, require_audio)
        return {"status": "completed", **result.model_dump(mode="json")}
    except Exception as exc:
        return safe_error(exc, code="VALIDATION_FAILED").payload()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

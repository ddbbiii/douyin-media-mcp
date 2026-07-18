from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

import httpx

from .errors import MediaMCPError

ALLOWED_HOSTS = {"douyin.com", "www.douyin.com", "v.douyin.com"}
_AWEME_PATH = re.compile(r"/(?:video|note)/(\d{10,})")


def validate_douyin_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
    except ValueError as exc:
        raise MediaMCPError("INVALID_URL", "链接格式无效。") from exc
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise MediaMCPError("UNSUPPORTED_URL", "只支持 douyin.com 官方分享或作品链接。")
    return parts.geturl()


def extract_aweme_id(value: str) -> str | None:
    parts = urlsplit(value)
    match = _AWEME_PATH.search(parts.path)
    if match:
        return match.group(1)
    query = parse_qs(parts.query)
    for key in ("modal_id", "aweme_id", "item_id"):
        candidate = (query.get(key) or [None])[0]
        if candidate and str(candidate).isdigit():
            return str(candidate)
    return None


async def expand_share_url(value: str, *, timeout_seconds: float = 20.0) -> tuple[str, str]:
    url = validate_douyin_url(value)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds)),
            headers=headers,
        ) as client:
            response = await client.get(url)
        canonical = validate_douyin_url(str(response.url))
    except httpx.HTTPError as exc:
        raise MediaMCPError(
            "DOWNLOAD_FAILED", "展开分享链接失败。", retryable=True
        ) from exc
    aweme_id = extract_aweme_id(canonical) or extract_aweme_id(url)
    if not aweme_id:
        raise MediaMCPError("NOT_FOUND", "重定向结果中没有找到作品 ID。")
    return f"https://www.douyin.com/video/{aweme_id}", aweme_id

from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlsplit

from .errors import MediaMCPError
from .models import MediaCandidate

_DIMENSION_PATTERN = re.compile(r"(?<!\d)(\d{3,5})[xX_](\d{3,5})(?!\d)")


def candidate_from_response(
    url: str,
    *,
    content_type: str | None,
    content_length: str | None = None,
    content_range: str | None = None,
    request_headers: dict[str, str] | None = None,
) -> MediaCandidate | None:
    decoded = unquote(url).lower()
    path_text = unquote(urlsplit(url).path).lower()
    mime = (content_type or "").split(";", 1)[0].strip().lower() or None
    query = parse_qs(urlsplit(url).query)
    query_text = " ".join(value for values in query.values() for value in values).lower()
    kind: str | None = None
    if (
        "audio" in path_text
        or "mime_type=audio" in decoded
        or "audio_mp4" in decoded
        or "audio" in query_text
    ):
        kind = "audio"
    elif "mime_type=video" in decoded or "video_mp4" in decoded:
        kind = "video"
    elif mime and mime.startswith("audio/"):
        kind = "audio"
    elif mime and mime.startswith("video/"):
        kind = "video"
    if kind is None:
        return None

    width = _query_int(query, "width", "w")
    height = _query_int(query, "height", "h")
    if not width or not height:
        match = _DIMENSION_PATTERN.search(decoded)
        if match:
            width, height = int(match.group(1)), int(match.group(2))
    total_length = _total_content_length(content_range) or _safe_int(content_length)
    bitrate = _query_int(query, "bitrate", "bit_rate", "br")
    safe_headers = {
        key: value
        for key, value in (request_headers or {}).items()
        if key.lower() in {"user-agent", "referer", "cookie", "accept", "accept-language"}
    }
    return MediaCandidate(
        kind=kind,  # type: ignore[arg-type]
        url=url,
        mime_type=mime,
        width=width,
        height=height,
        bitrate=bitrate,
        content_length=total_length,
        request_headers=safe_headers,
    )


def deduplicate_candidates(candidates: list[MediaCandidate]) -> list[MediaCandidate]:
    selected: dict[tuple[str, str], MediaCandidate] = {}
    for candidate in candidates:
        parts = urlsplit(candidate.url)
        key = (candidate.kind, f"{parts.netloc}{parts.path}")
        current = selected.get(key)
        if current is None or _score(candidate) > _score(current):
            selected[key] = candidate
    return list(selected.values())


def select_streams(
    candidates: list[MediaCandidate], quality: str = "best"
) -> tuple[MediaCandidate, MediaCandidate | None, str]:
    videos = [item for item in candidates if item.kind == "video"]
    audios = [item for item in candidates if item.kind == "audio"]
    if not videos:
        raise MediaMCPError(
            "RESOLVER_CHANGED",
            "浏览器没有捕获到可下载的视频流。",
            retryable=True,
            details={"video_candidates": len(videos), "audio_candidates": len(audios)},
        )
    target_height = {"1080p": 1080, "720p": 720}.get(quality)
    if target_height:
        under_target = [item for item in videos if item.height and item.height <= target_height]
        video_pool = under_target or videos
    else:
        video_pool = videos
    video = max(video_pool, key=_score)
    audio = max(audios, key=_score) if audios else None
    reason = (
        f"quality={quality}; selected video "
        f"{video.width or '?'}x{video.height or '?'} by resolution/bitrate/size score; "
        f"audio={'selected' if audio else 'not_captured'}"
    )
    return video, audio, reason


def _score(candidate: MediaCandidate) -> tuple[int, int, int, int, int]:
    area = (candidate.width or 0) * (candidate.height or 0)
    return (
        area,
        candidate.height or 0,
        candidate.width or 0,
        candidate.bitrate or 0,
        candidate.content_length or 0,
    )


def _query_int(query: dict[str, list[str]], *keys: str) -> int | None:
    for key in keys:
        value = (query.get(key) or [None])[0]
        parsed = _safe_int(value)
        if parsed and parsed > 0:
            return parsed
    return None


def _safe_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _total_content_length(value: str | None) -> int | None:
    if not value or "/" not in value:
        return None
    return _safe_int(value.rsplit("/", 1)[-1])

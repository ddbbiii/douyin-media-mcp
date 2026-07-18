from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

MediaKind = Literal["video", "audio"]


@dataclass(frozen=True)
class MediaCandidate:
    kind: MediaKind
    url: str = field(repr=False)
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    bitrate: int | None = None
    content_length: int | None = None
    request_headers: dict[str, str] = field(default_factory=dict, repr=False)

    def public_summary(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "bitrate": self.bitrate,
            "content_length": self.content_length,
        }


@dataclass
class ResolvedMedia:
    canonical_url: str
    aweme_id: str
    resolver_used: str
    title: str | None = None
    duration_seconds: float | None = None
    candidates: list[MediaCandidate] = field(default_factory=list, repr=False)
    warnings: list[str] = field(default_factory=list)
    requires_human_action: bool = False

    def public_payload(self) -> dict[str, Any]:
        resolutions = sorted(
            {
                (candidate.width, candidate.height)
                for candidate in self.candidates
                if candidate.kind == "video" and candidate.width and candidate.height
            },
            key=lambda item: (item[0] * item[1]),
            reverse=True,
        )
        return {
            "status": "resolved",
            "canonical_url": self.canonical_url,
            "aweme_id": self.aweme_id,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "resolution_candidates": [
                {"width": width, "height": height} for width, height in resolutions
            ],
            "stream_candidates": {
                "video": sum(1 for item in self.candidates if item.kind == "video"),
                "audio": sum(1 for item in self.candidates if item.kind == "audio"),
            },
            "resolver_used": self.resolver_used,
            "requires_human_action": self.requires_human_action,
            "warnings": self.warnings,
        }


class DecodeCheck(BaseModel):
    position_seconds: float
    status: Literal["passed", "failed", "skipped"]
    detail: str | None = None


class ProbeResult(BaseModel):
    path: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None
    media_mode: Literal["audio_video", "video_only", "audio_only", "unknown"]
    size_bytes: int = 0
    sha256: str
    decode_checks: list[DecodeCheck] = Field(default_factory=list)
    valid_for_analysis: bool
    issues: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class DownloadedStreams:
    video_path: Path
    audio_path: Path | None = None

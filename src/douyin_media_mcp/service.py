from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal

from .candidates import select_streams
from .config import Settings
from .downloader import StreamDownloader
from .errors import MediaMCPError, safe_error
from .manifest import write_manifest
from .media_tools import (
    extract_audio_stream,
    extract_video_stream,
    mux_streams,
    probe_media_file,
)
from .models import ProbeResult, ResolvedMedia
from .resolvers import BrowserResolver
from .url_utils import expand_share_url

BrowserMode = Literal["auto", "direct", "browser"]
Quality = Literal["best", "1080p", "720p"]


class DouyinMediaService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.browser = BrowserResolver(self.settings)
        self.downloader = StreamDownloader(self.settings)

    async def resolve(self, url: str, browser_mode: BrowserMode = "auto") -> ResolvedMedia:
        if browser_mode not in {"auto", "direct", "browser"}:
            raise MediaMCPError("INVALID_URL", "browser_mode 必须是 auto、direct 或 browser。")
        canonical_url, aweme_id = await expand_share_url(
            url, timeout_seconds=self.settings.request_timeout_seconds
        )
        if browser_mode == "direct":
            return ResolvedMedia(
                canonical_url=canonical_url,
                aweme_id=aweme_id,
                resolver_used="redirect_only",
                warnings=["direct 模式只展开链接，不启动浏览器或返回媒体流。"],
            )
        return await self.browser.resolve(canonical_url, aweme_id)

    async def download(
        self,
        url: str,
        output_dir: str,
        quality: Quality = "best",
        filename: str | None = None,
        overwrite: bool = False,
        keep_separate_streams: bool = False,
    ) -> dict[str, Any]:
        if quality not in {"best", "1080p", "720p"}:
            raise MediaMCPError("INVALID_URL", "quality 必须是 best、1080p 或 720p。")
        resolved = await self.resolve(url, "auto")
        video, audio, selection_reason = select_streams(resolved.candidates, quality)
        target_dir = Path(output_dir).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        output_name = _safe_filename(filename or f"douyin-{resolved.aweme_id}.mp4")
        output_path = target_dir / output_name
        manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
        if output_path.exists() and not overwrite:
            raise MediaMCPError("DOWNLOAD_FAILED", "目标文件已存在，且 overwrite=false。")

        with tempfile.TemporaryDirectory(
            prefix=f".douyin-{resolved.aweme_id}-", dir=target_dir
        ) as raw:
            temporary_dir = Path(raw)
            streams = await self.downloader.download_streams(video, audio, temporary_dir)
            await asyncio.to_thread(
                mux_streams,
                streams.video_path,
                streams.audio_path,
                output_path,
                ffmpeg_path=self.settings.ffmpeg_path,
                overwrite=overwrite,
            )
            probe = await asyncio.to_thread(
                probe_media_file,
                output_path,
                decode_check=True,
                require_audio=audio is not None,
                ffprobe_path=self.settings.ffprobe_path,
                ffmpeg_path=self.settings.ffmpeg_path,
            )
            issues = list(probe.issues)
            if resolved.duration_seconds and probe.duration_seconds:
                tolerance = max(3.0, resolved.duration_seconds * 0.01)
                if abs(resolved.duration_seconds - probe.duration_seconds) > tolerance:
                    issues.append("duration_mismatch")
            if issues:
                output_path.unlink(missing_ok=True)
                raise MediaMCPError(
                    "VALIDATION_FAILED",
                    "媒体封装完成，但验收未通过。",
                    details={"issues": ",".join(issues)},
                )

            separate_paths: dict[str, str] = {}
            if keep_separate_streams:
                video_copy = output_path.with_suffix(".video.mp4")
                await asyncio.to_thread(
                    extract_video_stream,
                    streams.video_path,
                    video_copy,
                    ffmpeg_path=self.settings.ffmpeg_path,
                    overwrite=overwrite,
                )
                separate_paths = {"video_path": str(video_copy)}
                if streams.audio_path is not None:
                    audio_copy = output_path.with_suffix(".audio.m4a")
                    shutil.copy2(streams.audio_path, audio_copy)
                    separate_paths["audio_path"] = str(audio_copy)
                elif probe.audio_codec is not None:
                    audio_copy = output_path.with_suffix(".audio.m4a")
                    await asyncio.to_thread(
                        extract_audio_stream,
                        streams.video_path,
                        audio_copy,
                        ffmpeg_path=self.settings.ffmpeg_path,
                        overwrite=overwrite,
                    )
                    separate_paths["audio_path"] = str(audio_copy)

        warnings = list(resolved.warnings)
        if probe.media_mode == "video_only":
            warnings.append("未捕获到独立音频流，结果为无声视频。")

        manifest = {
            "schema_version": 1,
            "status": "completed",
            "aweme_id": resolved.aweme_id,
            "canonical_url": resolved.canonical_url,
            "output_path": str(output_path),
            "resolver_used": resolved.resolver_used,
            "quality_requested": quality,
            "selection_reason": selection_reason,
            "selected_streams": {
                "video": video.public_summary(),
                "audio": audio.public_summary() if audio else None,
                "audio_source": (
                    "separate_stream"
                    if audio is not None
                    else "embedded_in_video_stream"
                    if probe.audio_codec is not None
                    else "not_found"
                ),
            },
            "probe": probe.model_dump(mode="json"),
            "media_mode": probe.media_mode,
            "warnings": warnings,
            **separate_paths,
        }
        write_manifest(manifest_path, manifest)
        return {
            "status": "completed",
            "output_path": str(output_path),
            "manifest_path": str(manifest_path),
            "aweme_id": resolved.aweme_id,
            "duration_seconds": probe.duration_seconds,
            "width": probe.width,
            "height": probe.height,
            "fps": probe.fps,
            "video_codec": probe.video_codec,
            "audio_codec": probe.audio_codec,
            "media_mode": probe.media_mode,
            "size_bytes": probe.size_bytes,
            "sha256": probe.sha256,
            "resolver_used": resolved.resolver_used,
            "audio_source": (
                "separate_stream"
                if audio is not None
                else "embedded_in_video_stream"
                if probe.audio_codec is not None
                else "not_found"
            ),
            "warnings": warnings,
            **separate_paths,
        }

    async def probe(
        self, path: str, decode_check: bool = True, require_audio: bool = False
    ) -> ProbeResult:
        try:
            return await asyncio.to_thread(
                probe_media_file,
                Path(path),
                decode_check=decode_check,
                require_audio=require_audio,
                ffprobe_path=self.settings.ffprobe_path,
                ffmpeg_path=self.settings.ffmpeg_path,
            )
        except Exception as exc:
            raise safe_error(exc, code="VALIDATION_FAILED") from exc


def _safe_filename(value: str) -> str:
    basename = Path(value).name.strip()
    cleaned = re.sub(r"[^\w.()\[\]-]+", "-", basename, flags=re.UNICODE).strip(".-")
    if not cleaned:
        raise MediaMCPError("INVALID_URL", "输出文件名无效。")
    if not cleaned.lower().endswith(".mp4"):
        cleaned += ".mp4"
    return cleaned

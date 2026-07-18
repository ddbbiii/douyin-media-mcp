from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from .config import Settings
from .errors import MediaMCPError
from .models import DownloadedStreams, MediaCandidate


class StreamDownloader:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._semaphore = asyncio.Semaphore(settings.media_download_concurrency)

    async def download_streams(
        self,
        video: MediaCandidate,
        audio: MediaCandidate | None,
        directory: Path,
    ) -> DownloadedStreams:
        directory.mkdir(parents=True, exist_ok=True)
        video_path = directory / "video.stream.part"
        audio_path = directory / "audio.stream.part" if audio else None
        downloads = [self.download(video, video_path)]
        if audio and audio_path:
            downloads.append(self.download(audio, audio_path))
        await asyncio.gather(*downloads)
        return DownloadedStreams(video_path=video_path, audio_path=audio_path)

    async def download(self, candidate: MediaCandidate, destination: Path) -> Path:
        async with self._semaphore:
            last_error: Exception | None = None
            for attempt in range(1, self.settings.download_retries + 1):
                try:
                    await self._download_once(candidate, destination)
                    if destination.stat().st_size <= 0:
                        raise MediaMCPError("DOWNLOAD_FAILED", "媒体流下载结果为空。")
                    return destination
                except MediaMCPError:
                    raise
                except (httpx.HTTPError, OSError) as exc:
                    last_error = exc
                    if attempt < self.settings.download_retries:
                        await asyncio.sleep(min(2 ** (attempt - 1), 4))
            raise MediaMCPError(
                "DOWNLOAD_FAILED",
                f"媒体流下载失败：{type(last_error).__name__ if last_error else 'unknown'}。",
                retryable=True,
            )

    async def _download_once(self, candidate: MediaCandidate, destination: Path) -> None:
        existing = destination.stat().st_size if destination.exists() else 0
        headers = dict(candidate.request_headers)
        if existing:
            headers["Range"] = f"bytes={existing}-"
        timeout = httpx.Timeout(self.settings.request_timeout_seconds, connect=10, read=60)
        async with (
            httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client,
            client.stream("GET", candidate.url, headers=headers) as response,
        ):
            if response.status_code in {401, 403, 410}:
                raise MediaMCPError(
                    "SIGNED_URL_EXPIRED",
                    "临时媒体地址已失效或需要重新解析。",
                    retryable=True,
                )
            response.raise_for_status()
            append = existing > 0 and response.status_code == 206
            mode = "ab" if append else "wb"
            with destination.open(mode) as handle:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    handle.write(chunk)

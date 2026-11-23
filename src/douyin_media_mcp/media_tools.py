from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import MediaMCPError
from .models import DecodeCheck, ProbeResult


def mux_streams(
    video_path: Path,
    audio_path: Path | None,
    output_path: Path,
    *,
    ffmpeg_path: str = "ffmpeg",
    overwrite: bool = False,
) -> Path:
    binary = shutil.which(ffmpeg_path)
    if binary is None:
        raise MediaMCPError("FFMPEG_NOT_FOUND", "没有找到 FFmpeg 可执行文件。")
    if output_path.exists() and not overwrite:
        raise MediaMCPError("DOWNLOAD_FAILED", "目标文件已存在，且 overwrite=false。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.muxing")
    command = [
        binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
    ]
    if audio_path is not None:
        command.extend(["-i", str(audio_path)])
    command.extend(["-map", "0:v:0"])
    if audio_path is not None:
        command.extend(["-map", "1:a:0"])
    else:
        # Some Douyin candidates are muxed AV files even when the page exposes
        # no separate audio URL. Preserve that in-band soundtrack.
        command.extend(["-map", "0:a:0?"])
    command.extend(
        ["-c", "copy", "-movflags", "+faststart", "-f", "mp4", str(temporary)]
    )
    result = _run(command)
    if result.returncode != 0 or not temporary.exists():
        temporary.unlink(missing_ok=True)
        raise MediaMCPError("MUX_FAILED", f"FFmpeg 封装失败：{_safe_process_error(result)}")
    os.replace(temporary, output_path)
    return output_path


def extract_audio_stream(
    source_path: Path,
    output_path: Path,
    *,
    ffmpeg_path: str = "ffmpeg",
    overwrite: bool = False,
) -> Path:
    binary = shutil.which(ffmpeg_path)
    if binary is None:
        raise MediaMCPError("FFMPEG_NOT_FOUND", "没有找到 FFmpeg 可执行文件。")
    if output_path.exists() and not overwrite:
        raise MediaMCPError("DOWNLOAD_FAILED", "目标文件已存在，且 overwrite=false。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.extracting")
    result = _run(
        [
            binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-f",
            "ipod",
            str(temporary),
        ]
    )
    if result.returncode != 0 or not temporary.exists():
        temporary.unlink(missing_ok=True)
        raise MediaMCPError("MUX_FAILED", f"音轨提取失败：{_safe_process_error(result)}")
    os.replace(temporary, output_path)
    return output_path


def extract_video_stream(
    source_path: Path,
    output_path: Path,
    *,
    ffmpeg_path: str = "ffmpeg",
    overwrite: bool = False,
) -> Path:
    binary = shutil.which(ffmpeg_path)
    if binary is None:
        raise MediaMCPError("FFMPEG_NOT_FOUND", "没有找到 FFmpeg 可执行文件。")
    if output_path.exists() and not overwrite:
        raise MediaMCPError("DOWNLOAD_FAILED", "目标文件已存在，且 overwrite=false。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.extracting")
    result = _run(
        [
            binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(temporary),
        ]
    )
    if result.returncode != 0 or not temporary.exists():
        temporary.unlink(missing_ok=True)
        raise MediaMCPError("MUX_FAILED", f"视频流提取失败：{_safe_process_error(result)}")
    os.replace(temporary, output_path)
    return output_path


def probe_media_file(
    path: Path,
    *,
    decode_check: bool = True,
    require_audio: bool = False,
    ffprobe_path: str = "ffprobe",
    ffmpeg_path: str = "ffmpeg",
) -> ProbeResult:
    source = path.expanduser().resolve()
    if not source.is_file():
        raise MediaMCPError("NOT_FOUND", "待探测的媒体文件不存在。")
    binary = shutil.which(ffprobe_path)
    if binary is None:
        raise MediaMCPError("FFMPEG_NOT_FOUND", "没有找到 FFprobe 可执行文件。")
    result = _run(
        [
            binary,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(source),
        ]
    )
    if result.returncode != 0:
        raise MediaMCPError("VALIDATION_FAILED", f"FFprobe 失败：{_safe_process_error(result)}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaMCPError("VALIDATION_FAILED", "FFprobe 返回了无效 JSON。") from exc
    return normalize_probe_payload(
        payload,
        source,
        decode_check=decode_check,
        require_audio=require_audio,
        ffmpeg_path=ffmpeg_path,
    )


def normalize_probe_payload(
    payload: dict[str, Any],
    path: Path,
    *,
    decode_check: bool,
    require_audio: bool = False,
    ffmpeg_path: str = "ffmpeg",
) -> ProbeResult:
    streams = payload.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    format_payload = payload.get("format") or {}
    duration = _float(format_payload.get("duration"))
    issues: list[str] = []
    if video is None:
        issues.append("missing_video_stream")
    if audio is None and require_audio:
        issues.append("missing_audio_stream")
    checks: list[DecodeCheck] = []
    if decode_check and video is not None:
        checks = _decode_checks(path, duration or 0.0, ffmpeg_path, include_audio=audio is not None)
        if any(item.status == "failed" for item in checks):
            issues.append("decode_check_failed")
    elif not decode_check:
        checks = [DecodeCheck(position_seconds=0, status="skipped")]
    return ProbeResult(
        path=str(path),
        duration_seconds=duration,
        width=_int((video or {}).get("width")),
        height=_int((video or {}).get("height")),
        fps=_fraction((video or {}).get("avg_frame_rate") or (video or {}).get("r_frame_rate")),
        video_codec=(video or {}).get("codec_name"),
        audio_codec=(audio or {}).get("codec_name"),
        audio_sample_rate=_int((audio or {}).get("sample_rate")),
        audio_channels=_int((audio or {}).get("channels")),
        media_mode=(
            "audio_video"
            if video is not None and audio is not None
            else "video_only"
            if video is not None
            else "audio_only"
            if audio is not None
            else "unknown"
        ),
        size_bytes=path.stat().st_size,
        sha256=_sha256(path),
        decode_checks=checks,
        valid_for_analysis=not issues,
        issues=issues,
    )


def _decode_checks(
    path: Path, duration: float, ffmpeg_path: str, *, include_audio: bool
) -> list[DecodeCheck]:
    binary = shutil.which(ffmpeg_path)
    if binary is None:
        raise MediaMCPError("FFMPEG_NOT_FOUND", "没有找到 FFmpeg 可执行文件。")
    end = max(0.0, duration - 1.5)
    positions = sorted({0.0, round(duration / 2, 3), round(end, 3)})
    checks: list[DecodeCheck] = []
    for position in positions:
        command = [
            binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(position),
            "-i",
            str(path),
            "-t",
            "1",
            "-map",
            "0:v:0",
        ]
        if include_audio:
            command.extend(["-map", "0:a:0"])
        command.extend(["-f", "null", "-"])
        result = _run(command)
        checks.append(
            DecodeCheck(
                position_seconds=position,
                status="passed" if result.returncode == 0 else "failed",
                detail=None if result.returncode == 0 else _safe_process_error(result),
            )
        )
    return checks


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=creationflags,
    )


def _safe_process_error(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "unknown error").strip().splitlines()
    return (text[-1] if text else "unknown error")[:500]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fraction(value: Any) -> float | None:
    if value in (None, "", "0/0"):
        return None
    try:
        numerator, denominator = str(value).split("/", 1)
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else None
    except (TypeError, ValueError):
        return _float(value)


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

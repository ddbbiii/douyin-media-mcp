from __future__ import annotations

import hashlib
import shutil
import subprocess

import pytest

from douyin_media_mcp.media_tools import (
    extract_audio_stream,
    extract_video_stream,
    mux_streams,
    normalize_probe_payload,
    probe_media_file,
)


def test_probe_normalization_requires_video_and_audio(tmp_path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"test-media")
    payload = {
        "format": {"duration": "12.5"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30/1",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "44100",
                "channels": 2,
            },
        ],
    }
    result = normalize_probe_payload(payload, media, decode_check=False)
    assert result.valid_for_analysis is True
    assert result.duration_seconds == 12.5
    assert result.fps == 30
    assert result.sha256 == hashlib.sha256(b"test-media").hexdigest()


def test_probe_normalization_accepts_video_only_by_default(tmp_path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"test-media")
    result = normalize_probe_payload(
        {"format": {"duration": "2"}, "streams": [{"codec_type": "video"}]},
        media,
        decode_check=False,
    )
    assert result.valid_for_analysis is True
    assert result.media_mode == "video_only"
    assert result.audio_codec is None


def test_probe_normalization_can_require_audio(tmp_path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"test-media")
    result = normalize_probe_payload(
        {"format": {"duration": "2"}, "streams": [{"codec_type": "video"}]},
        media,
        decode_check=False,
        require_audio=True,
    )
    assert result.valid_for_analysis is False
    assert "missing_audio_stream" in result.issues


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required for the mux integration test.",
)
def test_mux_preserves_audio_embedded_in_video_stream(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "output.mp4"
    audio = tmp_path / "output.audio.m4a"
    video = tmp_path / "output.video.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=10:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(source),
        ],
        check=True,
    )

    mux_streams(source, None, output)
    probe = probe_media_file(output, decode_check=True, require_audio=True)
    extract_audio_stream(source, audio)
    extract_video_stream(source, video)
    audio_probe = probe_media_file(audio, decode_check=False, require_audio=True)
    video_probe = probe_media_file(video, decode_check=True)

    assert probe.media_mode == "audio_video"
    assert probe.audio_codec == "aac"
    assert all(item.status == "passed" for item in probe.decode_checks)
    assert audio_probe.media_mode == "audio_only"
    assert audio_probe.audio_codec == "aac"
    assert video_probe.media_mode == "video_only"
    assert video_probe.video_codec == "h264"

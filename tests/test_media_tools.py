from __future__ import annotations

import hashlib

from douyin_media_mcp.media_tools import normalize_probe_payload


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

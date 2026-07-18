from __future__ import annotations

from douyin_media_mcp.candidates import (
    candidate_from_response,
    deduplicate_candidates,
    select_streams,
)
from douyin_media_mcp.models import MediaCandidate


def test_candidate_detection_uses_mime_and_query_hints() -> None:
    video = candidate_from_response(
        "https://media.example/video/tos/path?mime_type=video_mp4&width=1920&height=1080",
        content_type="video/mp4",
        content_range="bytes 0-99/123456",
        request_headers={"User-Agent": "Browser", "Authorization": "secret"},
    )
    audio = candidate_from_response(
        "https://media.example/audio/tos/path?mime_type=audio_mp4&bitrate=128000",
        content_type="audio/mp4",
    )
    assert video is not None and video.kind == "video"
    assert (video.width, video.height, video.content_length) == (1920, 1080, 123456)
    assert "Authorization" not in video.request_headers
    assert audio is not None and audio.kind == "audio" and audio.bitrate == 128000


def test_explicit_audio_query_wins_over_generic_video_mp4_content_type() -> None:
    audio = candidate_from_response(
        "https://media.example/path?mime_type=audio_mp4&bitrate=128000",
        content_type="video/mp4",
    )
    assert audio is not None
    assert audio.kind == "audio"


def test_audio_cdn_path_wins_over_incorrect_video_query_metadata() -> None:
    audio = candidate_from_response(
        "https://media.example/video/audio_track/path?mime_type=video_mp4",
        content_type="video/mp4",
    )
    assert audio is not None
    assert audio.kind == "audio"


def test_quality_selection_prefers_requested_cap() -> None:
    candidates = [
        MediaCandidate("video", "https://media.example/v720?sig=one", width=1280, height=720),
        MediaCandidate("video", "https://media.example/v1080?sig=two", width=1920, height=1080),
        MediaCandidate("video", "https://media.example/v4k?sig=three", width=3840, height=2160),
        MediaCandidate("audio", "https://media.example/a?sig=four", bitrate=128000),
    ]
    video, audio, reason = select_streams(candidates, "1080p")
    assert video.height == 1080
    assert audio.kind == "audio"
    assert "quality=1080p" in reason


def test_quality_selection_allows_video_only_result() -> None:
    candidates = [
        MediaCandidate("video", "https://media.example/v1080", width=1920, height=1080)
    ]
    video, audio, reason = select_streams(candidates, "best")
    assert video.height == 1080
    assert audio is None
    assert "audio=not_captured" in reason


def test_deduplication_ignores_rotating_query_signature() -> None:
    candidates = [
        MediaCandidate("video", "https://media.example/v/path?signature=old", height=720),
        MediaCandidate("video", "https://media.example/v/path?signature=new", height=1080),
    ]
    result = deduplicate_candidates(candidates)
    assert len(result) == 1
    assert result[0].height == 1080

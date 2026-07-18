from __future__ import annotations

import json

from douyin_media_mcp.errors import MediaMCPError
from douyin_media_mcp.manifest import write_manifest
from douyin_media_mcp.redaction import redact_mapping, redact_text, redact_url


def test_url_redaction_removes_query_and_fragment() -> None:
    raw = "https://media.example/video/path?signature=secret&token=value#fragment"
    assert redact_url(raw) == "https://media.example/video/path"
    assert "secret" not in redact_text(f"download failed: {raw}")


def test_mapping_redacts_headers_and_nested_urls() -> None:
    cleaned = redact_mapping(
        {
            "Cookie": "sessionid=secret",
            "nested": {"signed_url": "https://media.example/v?signature=secret"},
            "message": "Authorization: Bearer top-secret",
        }
    )
    serialized = json.dumps(cleaned)
    assert "sessionid" not in serialized
    assert "signature" not in serialized
    assert "top-secret" not in serialized


def test_manifest_and_error_never_persist_sensitive_values(tmp_path) -> None:
    target = tmp_path / "result.manifest.json"
    write_manifest(
        target,
        {
            "canonical_url": "https://www.douyin.com/video/123",
            "temporary": "https://media.example/v?signature=secret",
            "Cookie": "sid=secret-cookie",
        },
    )
    text = target.read_text(encoding="utf-8")
    assert "signature=secret" not in text
    assert "secret-cookie" not in text

    error = MediaMCPError(
        "DOWNLOAD_FAILED",
        "failed https://media.example/v?signature=secret Authorization: Bearer abc",
    )
    payload = json.dumps(error.payload())
    assert "signature=secret" not in payload
    assert "Bearer abc" not in payload

from __future__ import annotations

import pytest

from douyin_media_mcp.errors import MediaMCPError
from douyin_media_mcp.url_utils import extract_aweme_id, validate_douyin_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.douyin.com/video/7123456789012345678", "7123456789012345678"),
        ("https://www.douyin.com/?modal_id=7123456789012345678", "7123456789012345678"),
        ("https://www.douyin.com/note/7123456789012345678", "7123456789012345678"),
    ],
)
def test_extract_aweme_id(url: str, expected: str) -> None:
    assert extract_aweme_id(url) == expected


def test_validate_only_allows_official_hosts() -> None:
    assert validate_douyin_url("https://v.douyin.com/example/").startswith("https://")
    with pytest.raises(MediaMCPError) as error:
        validate_douyin_url("https://example.com/video/7123456789012345678")
    assert error.value.code == "UNSUPPORTED_URL"

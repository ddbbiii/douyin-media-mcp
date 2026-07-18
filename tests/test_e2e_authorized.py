from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from douyin_media_mcp.service import DouyinMediaService


@pytest.mark.e2e
def test_authorized_live_link_regression() -> None:
    url = os.getenv("DOUYIN_MCP_E2E_URL")
    output_dir = os.getenv("DOUYIN_MCP_E2E_OUTPUT_DIR")
    if not url or not output_dir:
        pytest.skip("Set DOUYIN_MCP_E2E_URL and DOUYIN_MCP_E2E_OUTPUT_DIR explicitly.")
    result = asyncio.run(
        DouyinMediaService().download(
            url=url,
            output_dir=output_dir,
            quality="1080p",
            filename="authorized-regression.mp4",
            overwrite=True,
        )
    )
    assert result["status"] == "completed"
    assert int(result["width"]) >= 1280
    assert int(result["height"]) >= 720
    assert result["video_codec"] == "h264"
    assert result["media_mode"] in {"audio_video", "video_only"}
    if result["media_mode"] == "audio_video":
        assert result["audio_codec"] == "aac"
    else:
        assert result["audio_codec"] is None
        assert "未捕获到独立音频流，结果为无声视频。" in result["warnings"]
    assert abs(float(result["duration_seconds"]) - 1309.675) <= 3.0
    assert Path(result["manifest_path"]).is_file()

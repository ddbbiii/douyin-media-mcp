from __future__ import annotations

import pytest

from douyin_media_mcp.server import mcp


@pytest.mark.asyncio
async def test_required_tools_are_registered() -> None:
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert names == {"resolve_douyin_url", "download_douyin_media", "probe_media"}

    download = next(tool for tool in tools if tool.name == "download_douyin_media")
    properties = download.inputSchema["properties"]
    assert {"url", "output_dir", "quality", "overwrite"}.issubset(properties)

    probe = next(tool for tool in tools if tool.name == "probe_media")
    assert "require_audio" in probe.inputSchema["properties"]

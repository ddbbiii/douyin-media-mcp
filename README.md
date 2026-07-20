# Douyin Media MCP

一个面向本地自动化的轻量 MCP 服务：接收用户提供的抖音分享链接，解析页面中的临时媒体流，将视频流和可选音频流下载到本地，使用 FFmpeg 无损封装，并用 FFprobe 验收结果。

项目只做“链接解析与媒体落盘”，不包含视频笔记 UI、AI 总结、转写、数据库或内容管理系统。

## 目标工具

- `resolve_douyin_url`：展开短链接并返回规范化页面地址、作品 ID 和基础元数据。
- `download_douyin_media`：解析媒体流、下载、合并并返回本地文件与 manifest。
- `probe_media`：检查时长、分辨率、帧率、编码、音轨和文件哈希。

## 已验证的解析链路

```text
分享短链接
  -> 跟随重定向取得 /video/<aweme_id>
  -> 浏览器加载真实作品页
  -> 监听/枚举页面媒体请求
  -> 识别 video_mp4 视频流，并尽力识别独立音频流
  -> 携带页面 Referer、User-Agent（必要时 Cookie）下载临时签名 URL
  -> FFmpeg stream copy 合并
  -> FFprobe + SHA-256 验收
  -> 写入不含 Cookie/临时签名 URL 的 manifest
```

2026-07-19 已在 Windows 上完成两层真实验证：浏览器辅助基线取得 1920×1080 H.264 + AAC 完整媒体；独立 MCP Playwright 流程取得 1280×720 H.264 无声视频，时长约 21 分 50 秒，并通过三点解码与 SHA-256 验收。验证细节见 [docs/VERIFIED_PIPELINE.md](docs/VERIFIED_PIPELINE.md)。

## 设计原则

- 浏览器解析是正式 fallback，不依赖页面 HTML 中存在固定直链。
- 临时签名 URL、Cookie 和浏览器凭据不得写入日志、manifest 或 Git。
- 下载完成后才返回成功；必须验证视频流、时长和可解码性。有音频时同时验证音轨；没有捕获音频时返回 `media_mode=video_only` 和明确警告。
- 支持后台下载和有界并发，但解析阶段默认低并发，避免触发平台风控。
- 不绕过 DRM、验证码、付费墙或权限控制，不提供去水印功能。
- 只处理用户有权访问和保存的内容，并遵守平台条款与适用法律。

## 安装

需要 Python 3.11+、Chrome/Chromium、FFmpeg 和 FFprobe。推荐使用 `uv`：

```powershell
git clone <repository-url>
cd douyin-media-mcp
uv sync --extra dev
uv run douyin-media-mcp
```

如果系统没有 Chrome，可安装 Playwright 自带 Chromium：

```powershell
uv run playwright install chromium
```

## MCP 客户端配置

Codex 的 `config.toml` 示例：

```toml
[mcp_servers.douyin-media]
command = "uv"
args = ["--directory", "<repository-path>", "run", "douyin-media-mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 1800
```

Claude Code：

```powershell
claude mcp add douyin-media -- uv --directory <repository-path> run douyin-media-mcp
```

Claude Desktop 可使用等价的 stdio 配置：

```json
{
  "mcpServers": {
    "douyin-media": {
      "command": "uv",
      "args": ["--directory", "<repository-path>", "run", "douyin-media-mcp"]
    }
  }
}
```

## KeyHub 本机配置

项目包含 [`.keyhub.json`](.keyhub.json)，可以扫描或添加到 KeyHub Project Desk。KeyHub 只管理本机浏览器模式、CDP 附着和是否临时使用 Cookie 等可选运行参数；它不会保存或导出浏览器 Cookie、下载结果或临时签名地址。

这是 stdio MCP，不应在 KeyHub 中孤立常驻启动。应由 Codex、Claude Code 或 Claude Desktop 按上面的 MCP 配置启动，并由 KeyHub 提供已绑定的项目环境变量。具体注册和开关说明见 [docs/KEYHUB.md](docs/KEYHUB.md)。

## 浏览器模式

默认启动本机 Chrome 的独立临时上下文并显示浏览器窗口。可通过环境变量调整：

- `DOUYIN_MCP_BROWSER_HEADLESS=1`：使用无头模式；更容易触发平台风控，不推荐作为默认值。
- `DOUYIN_MCP_BROWSER_PROFILE=<path>`：使用由用户管理的持久化 profile。目录不会被复制或提交。
- `DOUYIN_MCP_CDP_URL=http://127.0.0.1:9222`：附着到用户已启动的 Chromium。
- `DOUYIN_MCP_USE_BROWSER_COOKIES=1`：仅在用户明确允许时，把当前上下文 Cookie 临时用于媒体请求；Cookie 不落盘到 manifest 或日志。
- `DOUYIN_MCP_BROWSER_CHANNEL=`：留空后使用 Playwright 自带 Chromium；默认使用系统 Chrome。

## 工具行为

- `resolve_douyin_url` 的公共结果只包含作品地址、ID、元数据和候选数量，不包含签名媒体 URL。
- `download_douyin_media` 只在下载、无损封装、FFprobe、三点解码和 SHA-256 全部通过后返回成功；独立音频流是可选项。请求的清晰度是选择上限，实际分辨率以当次页面候选和返回字段为准。
- `probe_media` 可单独验证任意本地媒体文件；仅在调用方设置 `require_audio=true` 时把缺少音轨视为失败。
- 遇到登录、验证码或访问限制时返回结构化错误，不自动绕过。

## 当前状态

首个 MCP 实现已经完成。浏览器只能捕获视频流时会保存经过验收的无声视频，不再阻断任务。已验证的长视频基线和仍待补充的测试矩阵见
[docs/VERIFIED_PIPELINE.md](docs/VERIFIED_PIPELINE.md) 与
[docs/MAINTAINER_BACKLOG.md](docs/MAINTAINER_BACKLOG.md)。单条链接成功不代表任意抖音内容都长期可用。

## 许可证

MIT。第三方网站内容、浏览器组件和 FFmpeg 各自遵循其权利与许可证，本许可证不授予下载内容的再分发权。

# MCP 接口

## `resolve_douyin_url`

输入：

- `url: string`：用户提供的抖音分享链接。
- `browser_mode: "auto" | "direct" | "browser" = "auto"`。

输出：

- `canonical_url`
- `aweme_id`
- `title`（可取得时）
- `duration_seconds`（可取得时）
- `resolution_candidates`
- `resolver_used`
- `requires_human_action`
- `warnings`

此工具只解析，不保存完整媒体。

## `download_douyin_media`

输入：

- `url: string`
- `output_dir: string`
- `quality: "best" | "1080p" | "720p" = "best"`
- `filename?: string`
- `overwrite: boolean = false`
- `keep_separate_streams: boolean = false`

输出：

- `status`
- `output_path`
- `manifest_path`
- `aweme_id`
- `duration_seconds`
- `width` / `height` / `fps`
- `video_codec` / `audio_codec`
- `media_mode: "audio_video" | "video_only"`
- `size_bytes`
- `sha256`
- `resolver_used`
- `audio_source: "separate_stream" | "embedded_in_video_stream" | "not_found"`
- `warnings`

设置 `keep_separate_streams=true` 时，若音频嵌在视频流中，MCP 会无损额外导出 `<filename>.audio.m4a`。

只有下载、封装和验收全部完成时才返回 `status: "completed"`。作品可能把 AAC 音轨直接封装在视频候选流中，即使没有独立音频候选也应保留该音轨；只有最终文件确实没有音轨时，才返回 `media_mode: "video_only"`、`audio_codec: null` 并给出警告。

`quality` 是候选选择偏好而不是平台清晰度保证；调用方必须读取返回的 `width` 和 `height` 获取实际结果。

## `probe_media`

输入：

- `path: string`
- `decode_check: boolean = true`
- `require_audio: boolean = false`

输出：

- FFprobe 归一化信息
- SHA-256
- 头/中/尾解码检查结果
- `valid_for_analysis`
- `issues`

默认情况下，无声视频可以通过探测；调用方需要音频时必须显式设置 `require_audio=true`。

## 错误码

- `INVALID_URL`
- `UNSUPPORTED_URL`
- `NOT_FOUND`
- `AUTH_REQUIRED`
- `HUMAN_ACTION_REQUIRED`
- `RESOLVER_CHANGED`
- `SIGNED_URL_EXPIRED`
- `DOWNLOAD_FAILED`
- `FFMPEG_NOT_FOUND`
- `MUX_FAILED`
- `VALIDATION_FAILED`

错误返回不得包含 Cookie、临时签名 URL或完整请求头。

所有工具通过官方 Python MCP SDK 的 FastMCP stdio server 暴露。错误使用统一结构：

```json
{
  "status": "error",
  "error": {
    "code": "HUMAN_ACTION_REQUIRED",
    "message": "页面要求登录或人工验证；服务不会自动绕过。",
    "retryable": false
  }
}
```

`resolve_douyin_url` 的 `resolution_candidates` 和 `stream_candidates` 只包含尺寸与数量，
不会返回浏览器 Cookie、请求头或临时签名媒体 URL。

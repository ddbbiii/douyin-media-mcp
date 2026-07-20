# KeyHub 接入

`Douyin Media MCP` 是标准输入输出（stdio）MCP server，不是 HTTP 服务。它应由 Codex、Claude Code 或 Claude Desktop 在需要时启动并连接；KeyHub 的职责是保存并注入本机配置，不应单独常驻启动一个没有 MCP 客户端的进程。

项目根目录中的 [`.keyhub.json`](../.keyhub.json) 声明了 KeyHub 可管理的可选配置。它不包含 Cookie、浏览器 profile、下载目录或任何密钥值。

## 首次注册

在 KeyHub 的“全部项目”中扫描本仓库目录，或使用 KeyHub CLI：

```powershell
keyhub project add `
  --id douyin-media-mcp `
  --name "Douyin Media MCP" `
  --path "<repository-path>" `
  --command "uv run douyin-media-mcp" `
  --manifest "<repository-path>\.keyhub.json"
```

KeyHub 会检查项目定义、锁文件和 MCP 源码。`.venv` 仅作为可选提示；使用 `uv run` 时可按项目锁文件创建依赖。

## 可管理开关

在 KeyHub 的项目详情中选择“添加环境变量映射”，为需要改变的项目选项新建或绑定“多行文本”凭据。未绑定时，MCP 使用安全默认值。

| 变量 | 默认值 | 何时设置 |
| --- | --- | --- |
| `DOUYIN_MCP_BROWSER_HEADLESS` | `false` | 设为 `1` 才使用无头浏览器。无头模式更容易触发站点风控，默认不要设置。 |
| `DOUYIN_MCP_BROWSER_CHANNEL` | `chrome` | 设为空字符串时改用 Playwright 自带 Chromium。 |
| `DOUYIN_MCP_BROWSER_PROFILE` | 不使用 | 仅在你主动选择复用独立浏览器 profile 时填写本机目录。不要使用日常浏览器 profile 的副本。 |
| `DOUYIN_MCP_CDP_URL` | 不附着 | 需要附着到你已启动的 Chromium 时填写本地地址，例如 `http://127.0.0.1:9222`。 |
| `DOUYIN_MCP_USE_BROWSER_COOKIES` | `false` | 仅在站点确实要求且你同意时设为 `1`；Cookie 只在内存使用，不写入 manifest、日志或 Git。 |

这些值是本机运行参数，不需要部署到服务器，也不需要导出 `.env`。若需要让 Codex 或 Claude 使用同一套设置，由 KeyHub 以项目环境变量注入它们的启动命令即可。

## MCP 客户端配置

KeyHub 不替代 MCP 客户端。客户端仍使用以下命令启动服务器：

```powershell
uv --directory "<repository-path>" run douyin-media-mcp
```

Codex 和 Claude 的配置示例见 [README](../README.md#MCP-客户端配置)。在 KeyHub 中点击“启动项目”只适用于可独立常驻的项目；本项目是 stdio MCP，应该通过上述客户端配置使用，避免启动一个无法接收工具调用的孤立进程。

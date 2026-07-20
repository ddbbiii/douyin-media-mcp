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

这些值是本机运行参数，不需要部署到服务器，也不需要导出 `.env`。用下节的 `keyhub run` 包装命令启动 MCP 后，KeyHub 会把已绑定的值作为子进程环境变量注入；未绑定的变量继续使用上表默认值。

## MCP 客户端配置

KeyHub 不替代 MCP 客户端。不要点击 KeyHub 的普通“启动项目”按钮启动这个 stdio 服务；改为让客户端通过 `keyhub run` 包装启动服务器。这样 KeyHub 才能在启动时注入项目开关。

先确保 `keyhub` CLI 已在系统 `PATH` 中；否则在下面的 `command` 位置填写 KeyHub CLI 的绝对路径。

Codex 的 `config.toml`：

```toml
[mcp_servers.douyin-media]
command = "keyhub"
args = ["run", "--project", "douyin-media-mcp", "--", "uv", "--directory", "<repository-path>", "run", "douyin-media-mcp"]
startup_timeout_sec = 30
tool_timeout_sec = 1800
```

Claude Code：

```powershell
claude mcp add douyin-media -- keyhub run --project douyin-media-mcp -- uv --directory <repository-path> run douyin-media-mcp
```

Claude Desktop 可使用等价的 stdio 配置：

```json
{
  "mcpServers": {
    "douyin-media": {
      "command": "keyhub",
      "args": ["run", "--project", "douyin-media-mcp", "--", "uv", "--directory", "<repository-path>", "run", "douyin-media-mcp"]
    }
  }
}
```

不使用 KeyHub 时，客户端也可以直接使用以下命令启动服务器：

```powershell
uv --directory "<repository-path>" run douyin-media-mcp
```

包装方式不写入任何 Cookie、临时签名 URL 或下载媒体；KeyHub 只向 MCP 子进程传递用户显式绑定的配置值。

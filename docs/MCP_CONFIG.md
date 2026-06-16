# WeKnora MCP Server 配置

本服务器仅支持**网络传输**（`http` 默认，或 `sse`），不再支持 stdio。

## 1. 启动服务器

```bash
# 安装依赖（uv，复现 uv.lock）
uv sync --frozen

# 启动（默认 http，监听 0.0.0.0:8000）
uv run weknora-mcp-server

# 等价于显式指定
uv run weknora-mcp-server --transport http --host 0.0.0.0 --port 8000

# 或用环境变量覆盖
MCP_TRANSPORT=http MCP_HOST=0.0.0.0 MCP_PORT=8000 uv run weknora-mcp-server
```

API Key 与后端地址通过环境变量注入：

```bash
export WEKNORA_BASE_URL="http://<weknora-host>:8080/api/v1"
export WEKNORA_API_KEY="your_api_key"
```

默认 MCP 端点：`http://<host>:8000/mcp`

## 2. MCP 客户端配置

所有客户端连同一个 HTTP 端点。API Key 通过 `X-Api-Key` 请求头传递；若服务端已用 `WEKNORA_API_KEY` 环境变量注入（如 Docker），客户端可省略 `headers`。

### Claude Desktop / Cursor / KiloCode / 通用 MCP 客户端

```json
{
  "mcpServers": {
    "weknora": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "X-Api-Key": "your_api_key"
      }
    }
  }
}
```

### Docker 部署

见仓库 `Dockerfile`。运行时注入环境变量：

```bash
docker run -p 8000:8000 \
  -e WEKNORA_API_KEY=your_api_key \
  -e WEKNORA_BASE_URL=http://<weknora-host>:8080/api/v1 \
  weknora-mcp-server
```

## 3. 传输方式

| Transport   | 用途                                            | 端点   |
| ----------- | ----------------------------------------------- | ------ |
| `http`（默认） | Streamable HTTP（MCP 2025-03-26 规范），推荐    | `/mcp` |
| `sse`       | Server-Sent Events，兼容旧客户端                | `/sse` |
| ~~stdio~~   | 已移除                                          | —      |

## 4. 命令行选项

```bash
uv run weknora-mcp-server --help
uv run weknora-mcp-server --version
uv run weknora-mcp-server --transport sse --port 8001   # 切换 SSE
```

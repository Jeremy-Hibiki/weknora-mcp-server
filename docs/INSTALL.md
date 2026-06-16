# WeKnora MCP Server 安装指南

只读检索 MCP 服务器，提供对 WeKnora 知识库的查询能力（8 个工具）。仅支持网络传输（`http` 默认 / `sse`），不支持 stdio。

## 环境要求

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip
- 可访问的 WeKnora 后端（`WEKNORA_BASE_URL`）与 API Key（`WEKNORA_API_KEY`）

## 安装

```bash
# uv（推荐，复现 uv.lock）
uv sync --frozen

# 或 pip
pip install -e .   # 开发模式
pip install .       # 生产模式
```

安装后提供命令行入口 `weknora-mcp-server`。

## 配置环境变量

```bash
# Linux/macOS
export WEKNORA_BASE_URL="http://<weknora-host>:8080/api/v1"
export WEKNORA_API_KEY="your_api_key"

# Windows PowerShell
$env:WEKNORA_BASE_URL="http://<weknora-host>:8080/api/v1"
$env:WEKNORA_API_KEY="your_api_key"
```

## 启动

```bash
# 默认 http，监听 0.0.0.0:8000，MCP 端点 /mcp
uv run weknora-mcp-server

# SSE 传输（兼容旧客户端）
uv run weknora-mcp-server --transport sse
```

> stdio 传输已移除。客户端连接配置见 [MCP_CONFIG.md](./MCP_CONFIG.md)。

## 命令行选项

```bash
uv run weknora-mcp-server --help
uv run weknora-mcp-server --version
```

| 选项          | 默认（env）                | 说明            |
| ------------- | -------------------------- | --------------- |
| `--transport` | `http`（`MCP_TRANSPORT`）  | `http` 或 `sse` |
| `--host`      | `0.0.0.0`（`MCP_HOST`）    | 绑定地址        |
| `--port`      | `8000`（`MCP_PORT`）       | 绑定端口        |

## Docker

见仓库 `Dockerfile`：

```bash
docker build -t weknora-mcp-server .
docker run -p 8000:8000 \
  -e WEKNORA_API_KEY=your_api_key \
  -e WEKNORA_BASE_URL=http://<weknora-host>:8080/api/v1 \
  weknora-mcp-server
```

## 测试与质量

```bash
uv run pytest                       # 单元测试（inline-snapshot 校验 8 个工具）
uv run mypy src/weknora_mcp_server  # 严格类型检查
uv run ruff check src tests         # lint
```

## 故障排除

- **连接错误**：检查 `WEKNORA_BASE_URL` 与 WeKnora 后端可达性。
- **认证错误（401）**：检查 `WEKNORA_API_KEY` 或客户端 `X-Api-Key` 请求头。
- **导入错误**：`uv sync --frozen` 重装依赖；确认 Python ≥ 3.10。

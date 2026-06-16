# WeKnora MCP Server - 项目总结

只读检索 MCP 服务器，基于 FastMCP，提供对 WeKnora 知识库的查询能力。

## 项目结构

```
weknora-mcp-server/
├── src/weknora_mcp_server/
│   ├── main.py                  # HTTP/SSE 入口（ASGI app + CLI）
│   ├── weknora_mcp_server.py    # MCP server + 8 个只读 tool
│   ├── _client.py               # WeKnoraClient（只读）
│   └── _types/
│       ├── weknora.py           # openapi 生成的业务模型（TypedDict）
│       ├── responses.py         # 响应 / 精简视图 TypedDict
│       └── openapi.json         # WeKnora API 定义
├── tests/test_fastmcp.py        # inline-snapshot 工具测试
├── docs/                        # 文档
├── Dockerfile                   # uv 镜像（http）
├── pyproject.toml / uv.lock     # uv 项目配置
└── README.md / CHANGELOG.md
```

## 功能特性

### MCP 工具（8 个，只读检索）
- **知识库**：`list_knowledge_bases`、`get_knowledge_base`、`hybrid_search`
- **知识**：`list_knowledge`、`get_knowledge`
- **Wiki**：`wiki_search`、`wiki_read_page`、`wiki_index_view`

所有工具标注 MCP `annotations`（`readOnlyHint=True` / `destructiveHint=False` / `idempotentHint=True` / `openWorldHint=True`），返回经精简投影（剥离协议包裹与内部字段）。

### 技术特性
- 网络传输：`http`（默认）/ `sse`（不支持 stdio）
- 类型严格：mypy strict + ruff 全绿
- TypedDict 描述响应与精简视图结构
- uv 管理依赖，可复现构建

## 安装与运行

详见 [INSTALL.md](./INSTALL.md) 与 [MCP_CONFIG.md](./MCP_CONFIG.md)。

```bash
uv sync --frozen
uv run weknora-mcp-server            # http://0.0.0.0:8000/mcp
```

## 兼容性

- Python 3.10+
- 跨平台（Windows / macOS / Linux）
- 依赖：`fastmcp`、`pydantic`、`requests`

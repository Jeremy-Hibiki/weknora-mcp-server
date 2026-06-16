# WeKnora MCP Server 只读化 + Typing 精确化 + 返回精简

- 日期：2026-06-15
- 状态：待实现
- 关联代码：`src/weknora_mcp_server/`

## 1. 背景与目标

当前 WeKnora MCP Server 暴露 28 个 tool，覆盖增/删/改/查/聊天全操作。作为给 LLM 使用的只读知识检索入口，写操作（删/改/增）带来误操作风险，chat 类 tool 的返回也携带大量调试噪音。同时 `WeKnoraClient` 的类型注解普遍使用裸 `Dict`/`list`，可读性与静态检查支持不足。

本次重构三个目标：

1. **去除破坏性 tool**：删除所有增/删/改 tool，并按决策一并删除 `chat`/`agent_chat`，使 MCP 退化为纯只读检索服务器。
2. **优化 Client Typing**：参考 API 接口定义（`openapi.json`）与已有业务模型（`_types/weknora.py`），用 TypedDict 精确化 `WeKnoraClient` 的参数与返回类型，运行时行为不变。
3. **精简返回结果**：解包 API 响应的 `data` 字段、剥离 `code`/`message` 协议包裹，去除对 LLM 无意义的返回信息。

## 2. 关键决策

| 决策点 | 选择 |
|---|---|
| Tool 边界 | 删除全部增/删/改 + `chat`/`agent_chat`，保留 16 个只读 tool |
| Typing 深度 | TypedDict 精确化（参数精确类型 + 返回 TypedDict，运行时不解析） |
| 返回精简 | 解包 `data` + 剥离 `code`/`message`/`msg` 包裹 |
| Typing 组织 | 新建 `_types/responses.py` 集中放响应 TypedDict |
| 只读 client 方法 | 保留所有只读查询方法（如 `get_tenant`），仅删破坏性与 chat 相关 |
| 文档 | 同步更新 README / docs / CHANGELOG |

## 3. Tool 精简（28 → 16）

### 3.1 删除的 12 个 tool

- 增（6）：`create_tenant`、`create_knowledge_base`、`create_knowledge_from_file`、`create_knowledge_from_url`、`create_model`、`create_session`
- 删（4）：`delete_knowledge_base`、`delete_knowledge`、`delete_session`、`delete_chunk`
- 聊天（2）：`chat`、`agent_chat`

### 3.2 保留的 16 个只读 tool

| 分组 | Tool |
|---|---|
| 租户 | `list_tenants` |
| 知识库 | `list_knowledge_bases`、`get_knowledge_base`、`hybrid_search` |
| 知识 | `list_knowledge`、`get_knowledge` |
| 模型 | `list_models`、`get_model` |
| 会话 | `list_sessions`、`get_session` |
| Agent | `list_agents`、`get_agent` |
| Chunk | `list_chunks` |
| Wiki | `wiki_search`、`wiki_read_page`、`wiki_index_view` |

## 4. Client 清理

### 4.1 删除的方法（破坏性 + chat）

`create_tenant`、`create_knowledge_base`、`update_knowledge_base`、`delete_knowledge_base`、`create_knowledge_from_file`、`create_knowledge_from_url`、`delete_knowledge`、`create_model`、`create_session`、`delete_session`、`delete_chunk`、`chat`、`agent_chat`、`_consume_sse_stream`。

同时移除仅被 `_consume_sse_stream` 使用的 `WEKNORA_CHAT_TIMEOUT` 常量及其环境变量解析块，以及 SSE 流处理相关的全部逻辑。

### 4.2 保留的方法

- 只读查询：`get_tenant`、`list_tenants`、`list_knowledge_bases`、`get_knowledge_base`、`hybrid_search`、`list_knowledge`、`get_knowledge`、`list_models`、`get_model`、`get_session`、`list_sessions`、`list_agents`、`get_agent`、`list_chunks`、`wiki_search`、`wiki_read_page`、`wiki_index_view`
- 辅助：`_request`、`_resolve_uuid`、`resolve_kb_id`（`hybrid_search` 使用）、`resolve_agent_id`（`get_agent` 使用）

依据：`__init__.py` 仅导出包元信息，不导出 `WeKnoraClient`，client 无外部消费者，可安全删改。

## 5. Typing 精确化

### 5.1 新建 `_types/responses.py`

集中定义响应 TypedDict，复用 `_types/weknora.py` 的业务模型作为 `data` 字段类型注解（仅静态类型，运行时不解析）。

```python
from typing import Any, TypedDict
from ._types.weknora import (
    Tenant, KnowledgeBase, Knowledge, Session, SearchResult,
    WikiPage, WikiIndexResponse,
)

class WeKnoraResponse(TypedDict):
    """WeKnora API 通用响应包装（基于 client 运行时线索，openapi 为泛型 object）。"""
    code: int
    message: str
    data: Any
```

为列表类端点补充具体响应 TypedDict，`data` 指向业务模型或 `{"list": [...], "total": int}` 形式：

- `TenantListResponse`、`KnowledgeBaseListResponse`、`KnowledgeBaseDetailResponse`
- `KnowledgeListResponse`、`KnowledgeDetailResponse`
- `ModelListResponse`、`ModelDetailResponse`
- `SessionListResponse`、`SessionDetailResponse`
- `AgentListResponse`、`AgentDetailResponse`
- `ChunkListResponse`
- `HybridSearchResponse`（`data` 为 `list[SearchResult]`）
- wiki 端点 openapi 已有精确 schema，直接用 `list[WikiPage]` / `WikiPage` / `WikiIndexResponse`

### 5.2 规避泛型 TypedDict

mypy 配置 `python_version = "3.8"`（与 `requires-python>=3.10` 不一致，但本次不修改该配置以缩小范围），泛型 TypedDict 在该版本受限。因此不为列表响应定义 `WeKnoraListResponse[T]`，而是为每个端点写具体的响应 TypedDict。

### 5.3 client 签名改造

- 参数：`Dict` → 具体类型（`str`/`int`/`bool`/`list[str]`/具体 TypedDict）
- 返回：裸 `Dict` → 对应响应 TypedDict（见 5.1）
- 运行时行为不变：仍返回 `response.json()` 原始 dict，类型注解仅供 mypy 静态检查与可读性

### 5.4 业务模型字段依据（openapi 已确认）

- `Tenant`：`id:int`、`name`、`business`、`api_key`、`status`、`created_at`、`updated_at`
- `KnowledgeBase`：`id`、`name`、`description`、`chunk_count`、`knowledge_count`、`embedding_model_id`、`summary_model_id`、`tenant_id`、`created_at`
- `Knowledge`：`id`、`title`、`knowledge_base_id`、`source`、`file_name`、`parse_status`、`created_at`
- `Session`：`id`、`title`、`description`、`tenant_id`、`created_at`
- `SearchResult`：`id`、`content`、`score`、`knowledge_id`、`knowledge_title`、`match_type`、`chunk_index`
- `WikiPage`：`id`、`slug`、`title`、`summary`、`content`、`in_links`、`out_links`、`chunk_refs`
- `WikiIndexResponse`：`groups`、`intro`、`version`

模型/Agent 响应实体的精确类型名在实现阶段于 `_types/weknora.py` 内核对（概览中存在 `Llm`、`CustomAgentConfig` 等候选），如无完全匹配实体则 `data` 退化为 `Any` 并加注释。

## 6. 返回精简

### 6.1 `_unwrap` helper

在 `weknora_mcp_server.py` 增加：

```python
def _unwrap(resp: Any) -> Any:
    """剥离 WeKnora 响应的 code/message 包装，返回 data；非标准结构则原样返回。"""
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp
```

### 6.2 应用到 16 个保留 tool

每个保留 tool 的返回改为 `json.dumps(_unwrap(client.xxx(...)), indent=2, ensure_ascii=False)`。

### 6.3 不受影响的部分

`resolve_kb_id` / `resolve_agent_id` 内部读取 `data` / `list` 的逻辑保持不变（属于解析过程，不对外返回）。`_unwrap` 仅作用于最终对 LLM 的返回。

## 7. 测试影响

- `tests/test_fastmcp.py::test_tools_registered` 的 `inline_snapshot` 固化了完整 28-tool 列表及其 inputSchema。删 tool 后需运行 `pytest --inline-snapshot=update` 重生成快照，确保剩余 16 个 tool 的 schema 与新签名一致。
- `test_tool_schemas_have_descriptions` 对 16 个保留 tool 仍成立。

## 8. 文档同步

- `README.md`：「功能特性」章节 tool 列表改为 16 个只读 tool。
- `docs/PROJECT_SUMMARY.md`：「MCP 工具」列表同步更新。
- `docs/EXAMPLES.md`：移除涉及删除 tool 的示例，补充只读检索用法。
- `docs/MCP_CONFIG.md`：核对是否引用被删 tool，相应更新。
- `CHANGELOG.md`：新增条目记录本次只读化、typing 精确化、返回精简。

## 9. 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/weknora_mcp_server/weknora_mcp_server.py` | 删 12 tool、删 `functools`/`asyncio` 中仅 chat 用的导入、加 `_unwrap`、16 个 tool 改返回 |
| `src/weknora_mcp_server/_client.py` | 删破坏性 + chat 方法、移除 `WEKNORA_CHAT_TIMEOUT`、所有方法补 TypedDict typing |
| `src/weknora_mcp_server/_types/responses.py` | 新建：响应 TypedDict 集中定义 |
| `src/weknora_mcp_server/_types/__init__.py` | 导出 responses（按需） |
| `tests/test_fastmcp.py` | 更新 inline_snapshot |
| `README.md`、`docs/*.md`、`CHANGELOG.md` | 同步 tool 列表与说明 |

## 10. 风险与验证

- **响应包裹结构**：openapi 对大多数 GET 响应为泛型 `object`（`additionalProperties: true`），`_unwrap` 与 TypedDict 的 `data` 形态基于 client 现有 `resp.get("data", resp)` / `kbs.get("list", kbs.get("items", []))` 运行时线索推断。实现时无法调用真实 WeKnora API 验证，将以现有 client 解析模式为准并在 `_unwrap` 与 TypedDict 处加注释说明依据。
- **mypy 通过**：改动需满足 `pyproject.toml` 的 mypy strict 配置（`disallow_untyped_defs` 等）。
- **ruff 通过**：删除 chat 后 `functools`、`asyncio.get_running_loop` 等若不再使用需同步移除导入，避免 ruff 报未使用导入。
- **启动链路不受影响**：`main.py` → `run_stdio/run_sse/run_http`（来自 `weknora_mcp_server.py`），删 tool 不触及传输层。

## 11. 非目标（Out of Scope）

- 不修改 mypy `python_version=3.8` 配置。
- 不重构 `_types/weknora.py`（仅复用其模型）。
- 不引入 Pydantic 响应解析（保持运行时返回原始 dict）。
- 不修改鉴权 middleware（`InjectApiKeyMiddleware` / `ApiKeyASGIMiddleware`）。
- 不调整传输层与 CLI 入口。

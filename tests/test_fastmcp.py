"""FastMCP refactor tests."""

from pydantic import TypeAdapter
from typing import Sequence


from inline_snapshot import snapshot

from mcp.types import Tool
import pytest
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from weknora_mcp_server.weknora_mcp_server import (
    mcp,
)

ToolList = TypeAdapter(Sequence[Tool])


@pytest.fixture
async def mcp_client(monkeypatch: pytest.MonkeyPatch):
    # ApiKeyMiddleware falls back to WEKNORA_API_KEY for in-process / stdio transport.
    monkeypatch.setenv("WEKNORA_API_KEY", "test-key")
    async with Client(transport=mcp) as mcp_client:
        yield mcp_client


async def test_tools_registered(mcp_client: Client[FastMCPTransport]) -> None:
    tools = await mcp_client.list_tools()
    assert ToolList.dump_python(tools) == snapshot(
        [
            {
                "name": "create_tenant",
                "title": None,
                "description": "Create a new tenant in WeKnora.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "name": {"description": "Tenant name", "type": "string"},
                        "description": {"description": "Tenant description", "type": "string"},
                        "business": {"description": "Business type", "type": "string"},
                        "retriever_engines": {
                            "anyOf": [{"additionalProperties": True, "type": "object"}, {"type": "null"}],
                            "default": None,
                            "description": "Retriever engine configuration",
                        },
                    },
                    "required": ["name", "description", "business"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_tenants",
                "title": None,
                "description": "List all tenants.",
                "inputSchema": {"additionalProperties": False, "properties": {}, "type": "object"},
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "create_knowledge_base",
                "title": None,
                "description": "Create a new knowledge base.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "name": {"description": "Knowledge base name", "type": "string"},
                        "description": {"description": "Knowledge base description", "type": "string"},
                        "embedding_model_id": {"default": "", "description": "Embedding model ID", "type": "string"},
                        "summary_model_id": {"default": "", "description": "Summary model ID", "type": "string"},
                    },
                    "required": ["name", "description"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_knowledge_bases",
                "title": None,
                "description": "List all knowledge bases.",
                "inputSchema": {"additionalProperties": False, "properties": {}, "type": "object"},
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "get_knowledge_base",
                "title": None,
                "description": "Get knowledge base details.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"kb_id": {"description": "Knowledge base ID", "type": "string"}},
                    "required": ["kb_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "delete_knowledge_base",
                "title": None,
                "description": "Delete a knowledge base.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"kb_id": {"description": "Knowledge base ID", "type": "string"}},
                    "required": ["kb_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "hybrid_search",
                "title": None,
                "description": "Perform hybrid search in knowledge base.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {
                            "description": "Knowledge base UUID (e.g. 'a1b2c3d4-e5f6-7890-abcd-ef1234567890') OR name (e.g. 'my-knowledge-base'). Use list_knowledge_bases to discover available knowledge bases.",
                            "type": "string",
                        },
                        "query": {"description": "Search query", "type": "string"},
                        "vector_threshold": {
                            "default": 0.5,
                            "description": "Vector similarity threshold",
                            "type": "number",
                        },
                        "keyword_threshold": {
                            "default": 0.3,
                            "description": "Keyword match threshold",
                            "type": "number",
                        },
                        "match_count": {"default": 5, "description": "Number of results to return", "type": "integer"},
                    },
                    "required": ["kb_id", "query"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "create_knowledge_from_file",
                "title": None,
                "description": "Create knowledge from a local file on the server filesystem.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "file_path": {
                            "description": "Absolute path to the local file on the server",
                            "type": "string",
                        },
                        "enable_multimodel": {
                            "default": True,
                            "description": "Enable multimodal processing",
                            "type": "boolean",
                        },
                    },
                    "required": ["kb_id", "file_path"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "create_knowledge_from_url",
                "title": None,
                "description": "Create knowledge from URL.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "url": {"description": "URL to create knowledge from", "type": "string"},
                        "enable_multimodel": {
                            "default": True,
                            "description": "Enable multimodal processing",
                            "type": "boolean",
                        },
                    },
                    "required": ["kb_id", "url"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_knowledge",
                "title": None,
                "description": "List knowledge in a knowledge base.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "page": {"default": 1, "description": "Page number", "type": "integer"},
                        "page_size": {"default": 20, "description": "Page size", "type": "integer"},
                    },
                    "required": ["kb_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "get_knowledge",
                "title": None,
                "description": "Get knowledge details.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"knowledge_id": {"description": "Knowledge ID", "type": "string"}},
                    "required": ["knowledge_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "delete_knowledge",
                "title": None,
                "description": "Delete knowledge.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"knowledge_id": {"description": "Knowledge ID", "type": "string"}},
                    "required": ["knowledge_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "create_model",
                "title": None,
                "description": "Create a new model.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "name": {"description": "Model name", "type": "string"},
                        "model_type": {"description": "Model type (KnowledgeQA, Embedding, Rerank)", "type": "string"},
                        "description": {"description": "Model description", "type": "string"},
                        "source": {"default": "local", "description": "Model source", "type": "string"},
                        "base_url": {"default": "", "description": "Model API base URL", "type": "string"},
                        "api_key": {"default": "", "description": "Model API key", "type": "string"},
                        "is_default": {"default": False, "description": "Set as default model", "type": "boolean"},
                    },
                    "required": ["name", "model_type", "description"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_models",
                "title": None,
                "description": "List all models.",
                "inputSchema": {"additionalProperties": False, "properties": {}, "type": "object"},
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "get_model",
                "title": None,
                "description": "Get model details.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"model_id": {"description": "Model ID", "type": "string"}},
                    "required": ["model_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "create_session",
                "title": None,
                "description": "Create a new chat session with conversation strategy for a knowledge base.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "max_rounds": {"default": 5, "description": "Maximum conversation rounds", "type": "integer"},
                        "enable_rewrite": {
                            "default": True,
                            "description": "Enable query rewriting",
                            "type": "boolean",
                        },
                        "fallback_response": {
                            "default": "Sorry, I cannot answer this question.",
                            "description": "Fallback response when no answer found",
                            "type": "string",
                        },
                        "summary_model_id": {
                            "default": "",
                            "description": "Model ID for response summarization (optional)",
                            "type": "string",
                        },
                        "title": {"default": "", "description": "Session title (optional)", "type": "string"},
                        "description": {
                            "default": "",
                            "description": "Session description (optional)",
                            "type": "string",
                        },
                    },
                    "required": ["kb_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "get_session",
                "title": None,
                "description": "Get session details.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"session_id": {"description": "Session ID", "type": "string"}},
                    "required": ["session_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_sessions",
                "title": None,
                "description": "List chat sessions.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "page": {"default": 1, "description": "Page number", "type": "integer"},
                        "page_size": {"default": 20, "description": "Page size", "type": "integer"},
                    },
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "delete_session",
                "title": None,
                "description": "Delete a session.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"session_id": {"description": "Session ID", "type": "string"}},
                    "required": ["session_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "chat",
                "title": None,
                "description": """\
RAG pipeline chat: retrieve relevant chunks from knowledge bases, then summarise with LLM.

ALWAYS provide knowledge_base_ids (names like 'my-knowledge-base' or UUIDs) so retrieval
can run — without them the answer is based on LLM knowledge only.
Use list_knowledge_bases to discover available knowledge bases.
For multi-step reasoning or tool-calling use agent_chat instead.\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "session_id": {
                            "description": "Session ID (from create_session or list_sessions)",
                            "type": "string",
                        },
                        "query": {"description": "User query", "type": "string"},
                        "knowledge_base_ids": {
                            "anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}],
                            "default": None,
                            "description": "Knowledge base names OR UUIDs to search. Strongly recommended for RAG — without them the answer falls back to LLM knowledge only. E.g. ['my-knowledge-base'] or ['a1b2c3d4-...']. Use list_knowledge_bases to find them.",
                        },
                        "web_search_enabled": {
                            "default": False,
                            "description": "Enable web search alongside KB retrieval.",
                            "type": "boolean",
                        },
                        "enable_memory": {
                            "default": False,
                            "description": "Enable cross-session memory.",
                            "type": "boolean",
                        },
                    },
                    "required": ["session_id", "query"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "agent_chat",
                "title": None,
                "description": """\
Agentic pipeline chat: the agent autonomously calls tools to answer the query.

Use this for complex multi-step questions or comparative analysis.
REQUIRED: agent_id (name or UUID) — use list_agents to discover agents.
IMPORTANT: many agents have KBSelectionMode=none and NO built-in knowledge bases.
In that case you MUST pass knowledge_base_ids, otherwise the agent will fail with
'no search targets available'.
Use get_agent to inspect an agent's kb_selection_mode and knowledge_bases before calling.
If kb_selection_mode is 'none' or 'selected' with an empty list, always provide knowledge_base_ids.\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "session_id": {
                            "description": "Session ID (from create_session or list_sessions)",
                            "type": "string",
                        },
                        "query": {"description": "User query", "type": "string"},
                        "agent_id": {
                            "description": "REQUIRED. Custom agent UUID or name. Use list_agents to discover agents. Use get_agent to check its kb_selection_mode.",
                            "type": "string",
                        },
                        "knowledge_base_ids": {
                            "anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}],
                            "default": None,
                            "description": "Names or UUIDs of knowledge bases to search. REQUIRED when the agent's kb_selection_mode is 'none' or 'selected' with no built-in KBs. Use list_knowledge_bases to find them.",
                        },
                        "web_search_enabled": {
                            "default": False,
                            "description": "Enable web search.",
                            "type": "boolean",
                        },
                        "enable_memory": {
                            "default": False,
                            "description": "Enable cross-session memory.",
                            "type": "boolean",
                        },
                    },
                    "required": ["session_id", "query", "agent_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_agents",
                "title": None,
                "description": """\
List all custom agents available to the current tenant.

Use this to discover agent IDs, names, and their KB selection mode before calling agent_chat.\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "page": {"default": 1, "description": "Page number", "type": "integer"},
                        "page_size": {"default": 50, "description": "Page size", "type": "integer"},
                    },
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "get_agent",
                "title": None,
                "description": """\
Get full configuration of a single agent by UUID or name.

Check kb_selection_mode and knowledge_bases fields:
if kb_selection_mode is 'none' or 'selected' with an empty knowledge_bases list,
you MUST pass knowledge_base_ids when calling agent_chat.\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {"agent_id": {"description": "Agent UUID or name", "type": "string"}},
                    "required": ["agent_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "list_chunks",
                "title": None,
                "description": "List chunks of knowledge.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "knowledge_id": {"description": "Knowledge ID", "type": "string"},
                        "page": {"default": 1, "description": "Page number", "type": "integer"},
                        "page_size": {"default": 20, "description": "Page size", "type": "integer"},
                    },
                    "required": ["knowledge_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "delete_chunk",
                "title": None,
                "description": "Delete a chunk.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "knowledge_id": {"description": "Knowledge ID", "type": "string"},
                        "chunk_id": {"description": "Chunk ID", "type": "string"},
                    },
                    "required": ["knowledge_id", "chunk_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "wiki_search",
                "title": None,
                "description": """\
Search wiki pages by full-text query.

Returns matching wiki pages with title, slug, summary, and content snippets.\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "query": {"description": "Search query text", "type": "string"},
                        "limit": {
                            "default": 10,
                            "description": "Maximum number of results to return",
                            "type": "integer",
                        },
                    },
                    "required": ["kb_id", "query"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "wiki_read_page",
                "title": None,
                "description": """\
Read a wiki page by its slug.

Returns full markdown content, metadata, inbound/outbound links, and source references.\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "slug": {
                            "description": "Page slug (e.g. 'entity/acme-corp', 'concept/rag')",
                            "type": "string",
                        },
                    },
                    "required": ["kb_id", "slug"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "wiki_index_view",
                "title": None,
                "description": """\
Get a structured wiki index with per-type directory groups.

Returns an overview of all wiki pages organized by type (entity, concept, summary, etc.).\
""",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "limit": {"default": 50, "description": "Maximum items per type group", "type": "integer"},
                    },
                    "required": ["kb_id"],
                    "type": "object",
                },
                "outputSchema": {
                    "properties": {"result": {"type": "string"}},
                    "required": ["result"],
                    "type": "object",
                    "x-fastmcp-wrap-result": True,
                },
                "icons": None,
                "annotations": None,
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
        ]
    )


async def test_tool_schemas_have_descriptions(mcp_client: Client[FastMCPTransport]) -> None:
    tools = await mcp_client.list_tools()
    for tool in tools:
        assert tool.description, f"Tool '{tool.name}' has no description"

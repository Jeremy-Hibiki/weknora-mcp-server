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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "wiki_search",
                "title": None,
                "description": "Search wiki pages by full-text query.\n\nReturns matching wiki pages with title, slug, and summary.",
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "wiki_read_page",
                "title": None,
                "description": "Read a wiki page by its slug.\n\nReturns full markdown content, metadata, inbound/outbound links.",
                "inputSchema": {
                    "additionalProperties": False,
                    "properties": {
                        "kb_id": {"description": "Knowledge base ID", "type": "string"},
                        "slug": {"description": "Page slug (e.g. 'entity/acme-corp', 'concept/rag')", "type": "string"},
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
            {
                "name": "wiki_index_view",
                "title": None,
                "description": "Get a structured wiki index with per-type directory groups.\n\nReturns an overview of all wiki pages organized by type (entity, concept, summary, etc.).",
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
                "annotations": {
                    "title": None,
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": True,
                },
                "meta": {"fastmcp": {"tags": []}},
                "execution": None,
            },
        ]
    )


async def test_tool_schemas_have_descriptions(mcp_client: Client[FastMCPTransport]) -> None:
    tools = await mcp_client.list_tools()
    for tool in tools:
        assert tool.description, f"Tool '{tool.name}' has no description"

#!/usr/bin/env python3
"""
WeKnora MCP Server

A Model Context Protocol server that provides access to the WeKnora knowledge management API.
"""

from ._client import WeKnoraClient

from fastmcp.exceptions import AuthorizationError

from fastmcp.client.dependencies import get_http_headers


from starlette.responses import JSONResponse

import argparse
import asyncio
import functools
import json
import logging
import os
from typing import Annotated, Any, Dict

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp import FastMCP
from pydantic import Field

# Set up logging configuration for the MCP server
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Configuration - Load from environment variables with defaults
WEKNORA_BASE_URL = os.getenv("WEKNORA_BASE_URL", "http://localhost:8080/api/v1")


async def get_client(ctx: Context = CurrentContext()) -> "WeKnoraClient":
    """Return a WeKnoraClient for the current request.

    Reads the API key from ``ctx._request_state[_API_KEY_FIELD]``, which
    ``ApiKeyMiddleware`` writes before dispatching any MCP request.  All
    ``Context`` objects within the same MCP request share that dict by
    reference (see ``Context.__aenter__``), so the key set by the middleware
    is visible here without any extra ContextVar.
    """
    api_key: str = await ctx.get_state(_API_KEY_FIELD)
    return WeKnoraClient(WEKNORA_BASE_URL, api_key)


ClientDependency = Depends(get_client)

# -- Api Key Middleware -----------------------

# Key used to store the resolved API key inside FastMCP's per-request state dict.
# Context._request_state is a plain dict that FastMCP shares (by reference) across
# all Context objects for the same MCP request, so anything written here by the
# middleware is visible to every tool dependency executed within that request.
_API_KEY_FIELD = "__weknora_api_key"


class InjectApiKeyMiddleware(Middleware):
    """FastMCP protocol-level middleware: injects the X-Api-Key header.

    Intercepts every MCP *request* (``initialize``, ``tools/call``,
    ``resources/read``, …) via the ``on_request`` hook.

    * **HTTP / SSE transports** — reads the ``X-Api-Key`` header through
      FastMCP's ``get_http_request()`` helper, which returns the Starlette
      ``Request`` object stored in a ContextVar by ``RequestContextMiddleware``
      before any MCP processing begins.
    * **stdio transport** — ``get_http_request()`` raises ``RuntimeError``
      (no HTTP request exists); the middleware falls back to the
      ``WEKNORA_API_KEY`` environment variable.

    The resolved key is written into ``context.fastmcp_context._request_state``
    under ``_API_KEY_FIELD``.  FastMCP propagates that dict (by reference) to
    every ``Context`` created for the same MCP request, so ``get_client()`` can
    read it without any separate ContextVar.

    On failure a ``AuthorizationError`` is raised, which FastMCP converts into a
    JSON-RPC error response sent back to the client.
    """

    async def on_request(
        self,
        context: MiddlewareContext,
        call_next: CallNext,
    ) -> Any:
        api_key = get_http_headers().get("x-api-key", os.getenv("WEKNORA_API_KEY", "")).strip()
        if not api_key:
            raise AuthorizationError("Missing API key. Provide it via the X-Api-Key request header.")
        # Write into FastMCP's request-scoped state dict.  All Context objects
        # for this MCP request share the same dict by reference.
        if context.fastmcp_context is not None:
            await context.fastmcp_context.set_state(_API_KEY_FIELD, api_key)
        return await call_next(context)


mcp = FastMCP(
    "weknora-server",
    middleware=[InjectApiKeyMiddleware()],
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "mcp-server"})


# ── Tenant Management ─────────────────────────────────────────────────────────


@mcp.tool()
async def create_tenant(
    name: Annotated[str, Field(description="Tenant name")],
    description: Annotated[str, Field(description="Tenant description")],
    business: Annotated[str, Field(description="Business type")],
    retriever_engines: Annotated[
        Dict[str, Any] | None,
        Field(description="Retriever engine configuration"),
    ] = None,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Create a new tenant in WeKnora."""
    result = client.create_tenant(
        name,
        description,
        business,
        retriever_engines
        or {
            "engines": [
                {"retriever_type": "keywords", "retriever_engine_type": "postgres"},
                {"retriever_type": "vector", "retriever_engine_type": "postgres"},
            ]
        },
    )
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_tenants(client: WeKnoraClient = ClientDependency) -> str:
    """List all tenants."""
    return json.dumps(client.list_tenants(), indent=2, ensure_ascii=False)


# ── Knowledge Base Management ─────────────────────────────────────────────────


@mcp.tool()
async def create_knowledge_base(
    name: Annotated[str, Field(description="Knowledge base name")],
    description: Annotated[str, Field(description="Knowledge base description")],
    embedding_model_id: Annotated[str, Field(description="Embedding model ID")] = "",
    summary_model_id: Annotated[str, Field(description="Summary model ID")] = "",
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Create a new knowledge base."""
    config = {
        "chunking_config": {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "separators": ["."],
            "enable_multimodal": True,
        },
        "embedding_model_id": embedding_model_id,
        "summary_model_id": summary_model_id,
    }
    return json.dumps(
        client.create_knowledge_base(name, description, config),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def list_knowledge_bases(client: WeKnoraClient = ClientDependency) -> str:
    """List all knowledge bases."""
    return json.dumps(client.list_knowledge_bases(), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_knowledge_base(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get knowledge base details."""
    return json.dumps(client.get_knowledge_base(kb_id), indent=2, ensure_ascii=False)


@mcp.tool()
async def delete_knowledge_base(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Delete a knowledge base."""
    return json.dumps(client.delete_knowledge_base(kb_id), indent=2, ensure_ascii=False)


@mcp.tool()
async def hybrid_search(
    kb_id: Annotated[
        str,
        Field(
            description=(
                "Knowledge base UUID (e.g. 'a1b2c3d4-e5f6-7890-abcd-ef1234567890') OR name "
                "(e.g. 'my-knowledge-base'). Use list_knowledge_bases to discover available knowledge bases."
            )
        ),
    ],
    query: Annotated[str, Field(description="Search query")],
    vector_threshold: Annotated[float, Field(description="Vector similarity threshold")] = 0.5,
    keyword_threshold: Annotated[float, Field(description="Keyword match threshold")] = 0.3,
    match_count: Annotated[int, Field(description="Number of results to return")] = 5,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Perform hybrid search in knowledge base."""
    config = {
        "vector_threshold": vector_threshold,
        "keyword_threshold": keyword_threshold,
        "match_count": match_count,
    }
    return json.dumps(
        client.hybrid_search(client.resolve_kb_id(kb_id), query, config),
        indent=2,
        ensure_ascii=False,
    )


# ── Knowledge Management ──────────────────────────────────────────────────────


@mcp.tool()
async def create_knowledge_from_file(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    file_path: Annotated[str, Field(description="Absolute path to the local file on the server")],
    enable_multimodel: Annotated[bool, Field(description="Enable multimodal processing")] = True,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Create knowledge from a local file on the server filesystem."""
    return json.dumps(
        client.create_knowledge_from_file(kb_id, file_path, enable_multimodel),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def create_knowledge_from_url(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    url: Annotated[str, Field(description="URL to create knowledge from")],
    enable_multimodel: Annotated[bool, Field(description="Enable multimodal processing")] = True,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Create knowledge from URL."""
    return json.dumps(
        client.create_knowledge_from_url(kb_id, url, enable_multimodel),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def list_knowledge(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    page: Annotated[int, Field(description="Page number")] = 1,
    page_size: Annotated[int, Field(description="Page size")] = 20,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """List knowledge in a knowledge base."""
    return json.dumps(
        client.list_knowledge(kb_id, page, page_size),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def get_knowledge(
    knowledge_id: Annotated[str, Field(description="Knowledge ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get knowledge details."""
    return json.dumps(client.get_knowledge(knowledge_id), indent=2, ensure_ascii=False)


@mcp.tool()
async def delete_knowledge(
    knowledge_id: Annotated[str, Field(description="Knowledge ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Delete knowledge."""
    return json.dumps(client.delete_knowledge(knowledge_id), indent=2, ensure_ascii=False)


# ── Model Management ──────────────────────────────────────────────────────────


@mcp.tool()
async def create_model(
    name: Annotated[str, Field(description="Model name")],
    model_type: Annotated[str, Field(description="Model type (KnowledgeQA, Embedding, Rerank)")],
    description: Annotated[str, Field(description="Model description")],
    source: Annotated[str, Field(description="Model source")] = "local",
    base_url: Annotated[str, Field(description="Model API base URL")] = "",
    api_key: Annotated[str, Field(description="Model API key")] = "",
    is_default: Annotated[bool, Field(description="Set as default model")] = False,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Create a new model."""
    return json.dumps(
        client.create_model(
            name,
            model_type,
            source,
            description,
            {"base_url": base_url, "api_key": api_key},
            is_default,
        ),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def list_models(client: WeKnoraClient = ClientDependency) -> str:
    """List all models."""
    return json.dumps(client.list_models(), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_model(
    model_id: Annotated[str, Field(description="Model ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get model details."""
    return json.dumps(client.get_model(model_id), indent=2, ensure_ascii=False)


# ── Session Management ────────────────────────────────────────────────────────


@mcp.tool()
async def create_session(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    max_rounds: Annotated[int, Field(description="Maximum conversation rounds")] = 5,
    enable_rewrite: Annotated[bool, Field(description="Enable query rewriting")] = True,
    fallback_response: Annotated[
        str, Field(description="Fallback response when no answer found")
    ] = "Sorry, I cannot answer this question.",
    summary_model_id: Annotated[str, Field(description="Model ID for response summarization (optional)")] = "",
    title: Annotated[str, Field(description="Session title (optional)")] = "",
    description: Annotated[str, Field(description="Session description (optional)")] = "",
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Create a new chat session with conversation strategy for a knowledge base."""
    return json.dumps(
        client.create_session(
            kb_id=client.resolve_kb_id(kb_id),
            max_rounds=max_rounds,
            enable_rewrite=enable_rewrite,
            fallback_response=fallback_response,
            summary_model_id=summary_model_id,
            title=title,
            description=description,
        ),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def get_session(
    session_id: Annotated[str, Field(description="Session ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get session details."""
    return json.dumps(client.get_session(session_id), indent=2, ensure_ascii=False)


@mcp.tool()
async def list_sessions(
    page: Annotated[int, Field(description="Page number")] = 1,
    page_size: Annotated[int, Field(description="Page size")] = 20,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """List chat sessions."""
    return json.dumps(client.list_sessions(page, page_size), indent=2, ensure_ascii=False)


@mcp.tool()
async def delete_session(
    session_id: Annotated[str, Field(description="Session ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Delete a session."""
    return json.dumps(client.delete_session(session_id), indent=2, ensure_ascii=False)


# ── Chat Functionality ────────────────────────────────────────────────────────


@mcp.tool()
async def chat(
    session_id: Annotated[str, Field(description="Session ID (from create_session or list_sessions)")],
    query: Annotated[str, Field(description="User query")],
    knowledge_base_ids: Annotated[
        list[str] | None,
        Field(
            description=(
                "Knowledge base names OR UUIDs to search. Strongly recommended for RAG — "
                "without them the answer falls back to LLM knowledge only. "
                "E.g. ['my-knowledge-base'] or ['a1b2c3d4-...']. Use list_knowledge_bases to find them."
            )
        ),
    ] = None,
    web_search_enabled: Annotated[bool, Field(description="Enable web search alongside KB retrieval.")] = False,
    enable_memory: Annotated[bool, Field(description="Enable cross-session memory.")] = False,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """RAG pipeline chat: retrieve relevant chunks from knowledge bases, then summarise with LLM.

    ALWAYS provide knowledge_base_ids (names like 'my-knowledge-base' or UUIDs) so retrieval
    can run — without them the answer is based on LLM knowledge only.
    Use list_knowledge_bases to discover available knowledge bases.
    For multi-step reasoning or tool-calling use agent_chat instead.
    """
    raw_kb_ids = knowledge_base_ids or []
    kb_ids = [client.resolve_kb_id(k) for k in raw_kb_ids] if raw_kb_ids else None
    # client.chat() does blocking SSE streaming; run in a thread to avoid blocking the event loop.
    fn = functools.partial(
        client.chat,
        session_id,
        query,
        knowledge_base_ids=kb_ids,
        web_search_enabled=web_search_enabled,
        enable_memory=enable_memory,
    )
    result = await asyncio.get_running_loop().run_in_executor(None, fn)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def agent_chat(
    session_id: Annotated[str, Field(description="Session ID (from create_session or list_sessions)")],
    query: Annotated[str, Field(description="User query")],
    agent_id: Annotated[
        str,
        Field(
            description=(
                "REQUIRED. Custom agent UUID or name. Use list_agents to discover agents. "
                "Use get_agent to check its kb_selection_mode."
            )
        ),
    ],
    knowledge_base_ids: Annotated[
        list[str] | None,
        Field(
            description=(
                "Names or UUIDs of knowledge bases to search. REQUIRED when the agent's "
                "kb_selection_mode is 'none' or 'selected' with no built-in KBs. "
                "Use list_knowledge_bases to find them."
            )
        ),
    ] = None,
    web_search_enabled: Annotated[bool, Field(description="Enable web search.")] = False,
    enable_memory: Annotated[bool, Field(description="Enable cross-session memory.")] = False,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Agentic pipeline chat: the agent autonomously calls tools to answer the query.

    Use this for complex multi-step questions or comparative analysis.
    REQUIRED: agent_id (name or UUID) — use list_agents to discover agents.
    IMPORTANT: many agents have KBSelectionMode=none and NO built-in knowledge bases.
    In that case you MUST pass knowledge_base_ids, otherwise the agent will fail with
    'no search targets available'.
    Use get_agent to inspect an agent's kb_selection_mode and knowledge_bases before calling.
    If kb_selection_mode is 'none' or 'selected' with an empty list, always provide knowledge_base_ids.
    """
    resolved_agent_id = client.resolve_agent_id(agent_id)
    raw_kb_ids = knowledge_base_ids or []
    kb_ids = [client.resolve_kb_id(k) for k in raw_kb_ids] if raw_kb_ids else None
    # Pre-check: if no KB IDs provided, inspect agent config to detect
    # kb_selection_mode=none/selected-empty so we fail fast with a clear message
    # instead of the cryptic backend error "no search targets available".
    if not kb_ids:
        try:
            agent_info = client.get_agent(resolved_agent_id)
            cfg = (agent_info.get("data") or agent_info).get("config") or {}
            mode = cfg.get("kb_selection_mode", "selected")
            built_in_kbs = cfg.get("knowledge_bases") or []
            needs_kbs = (mode == "none") or (mode in ("selected", "") and not built_in_kbs)
            if needs_kbs:
                kb_list = client.list_knowledge_bases()
                kbs = kb_list.get("data") or kb_list
                if isinstance(kbs, dict):
                    kbs = kbs.get("list", kbs.get("items", []))
                kb_summary = ", ".join(
                    f"{kb.get('name')} ({kb.get('id')})" for kb in (kbs or [])[:10] if isinstance(kb, dict)
                )
                raise ValueError(
                    f"Agent '{agent_id}' has kb_selection_mode='{mode}' with no built-in "
                    f"knowledge bases. You must provide knowledge_base_ids. "
                    f"Available knowledge bases: [{kb_summary}]"
                )
        except ValueError:
            raise
        except Exception as preflight_err:
            logger.warning(f"agent_chat preflight KB check failed (non-fatal): {preflight_err}")
    fn = functools.partial(
        client.agent_chat,
        session_id,
        query,
        resolved_agent_id,
        knowledge_base_ids=kb_ids,
        web_search_enabled=web_search_enabled,
        enable_memory=enable_memory,
    )
    result = await asyncio.get_running_loop().run_in_executor(None, fn)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_agents(
    page: Annotated[int, Field(description="Page number")] = 1,
    page_size: Annotated[int, Field(description="Page size")] = 50,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """List all custom agents available to the current tenant.

    Use this to discover agent IDs, names, and their KB selection mode before calling agent_chat.
    """
    return json.dumps(
        client.list_agents(page=page, page_size=page_size),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def get_agent(
    agent_id: Annotated[str, Field(description="Agent UUID or name")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get full configuration of a single agent by UUID or name.

    Check kb_selection_mode and knowledge_bases fields:
    if kb_selection_mode is 'none' or 'selected' with an empty knowledge_bases list,
    you MUST pass knowledge_base_ids when calling agent_chat.
    """
    return json.dumps(client.get_agent(client.resolve_agent_id(agent_id)), indent=2, ensure_ascii=False)


# ── Chunk Management ──────────────────────────────────────────────────────────


@mcp.tool()
async def list_chunks(
    knowledge_id: Annotated[str, Field(description="Knowledge ID")],
    page: Annotated[int, Field(description="Page number")] = 1,
    page_size: Annotated[int, Field(description="Page size")] = 20,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """List chunks of knowledge."""
    return json.dumps(
        client.list_chunks(knowledge_id, page, page_size),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def delete_chunk(
    knowledge_id: Annotated[str, Field(description="Knowledge ID")],
    chunk_id: Annotated[str, Field(description="Chunk ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Delete a chunk."""
    return json.dumps(client.delete_chunk(knowledge_id, chunk_id), indent=2, ensure_ascii=False)


# ── Wiki Read-Only ────────────────────────────────────────────────────────────


@mcp.tool()
async def wiki_search(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    query: Annotated[str, Field(description="Search query text")],
    limit: Annotated[int, Field(description="Maximum number of results to return")] = 10,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Search wiki pages by full-text query.

    Returns matching wiki pages with title, slug, summary, and content snippets.
    """
    return json.dumps(client.wiki_search(kb_id, query, limit), indent=2, ensure_ascii=False)


@mcp.tool()
async def wiki_read_page(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    slug: Annotated[str, Field(description="Page slug (e.g. 'entity/acme-corp', 'concept/rag')")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Read a wiki page by its slug.

    Returns full markdown content, metadata, inbound/outbound links, and source references.
    """
    return json.dumps(client.wiki_read_page(kb_id, slug), indent=2, ensure_ascii=False)


@mcp.tool()
async def wiki_index_view(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    limit: Annotated[int, Field(description="Maximum items per type group")] = 50,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get a structured wiki index with per-type directory groups.

    Returns an overview of all wiki pages organized by type (entity, concept, summary, etc.).
    """
    return json.dumps(client.wiki_index_view(kb_id, limit), indent=2, ensure_ascii=False)


# ── Transport helpers ─────────────────────────────────────────────────────────


async def run_stdio():
    """Run the MCP server using stdio transport"""
    await mcp.run_async(transport="stdio", show_banner=False)


async def run_sse(host: str, port: int):
    """Run the MCP server using SSE transport (legacy MCP clients)."""
    await mcp.run_async(transport="sse", host=host, port=port, show_banner=False)


async def run_http(host: str, port: int):
    """Run the MCP server using Streamable HTTP transport."""
    await mcp.run_async(transport="http", host=host, port=port, show_banner=False)


def main():
    """Main entry point — supports stdio, sse, and http transports.

    Transport selection (in priority order):
      1. --transport CLI flag
      2. MCP_TRANSPORT environment variable
      3. Default: stdio
    """
    parser = argparse.ArgumentParser(description="WeKnora MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport type: stdio (default), sse, or http",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "0.0.0.0"),
        help="Bind host for network transports (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Bind port for network transports (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(run_stdio())
    elif args.transport == "sse":
        asyncio.run(run_sse(args.host, args.port))
    elif args.transport == "http":
        asyncio.run(run_http(args.host, args.port))


if __name__ == "__main__":
    main()

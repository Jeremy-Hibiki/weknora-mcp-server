#!/usr/bin/env python3
"""
WeKnora MCP Server

A read-only Model Context Protocol server that exposes the retrieval surface of
the WeKnora knowledge management API (list / get / search / wiki). Mutating
operations and chat pipelines are intentionally not exposed.
"""

from ._client import WeKnoraClient
from ._types.responses import KBSummary

from fastmcp.exceptions import AuthorizationError

from fastmcp.client.dependencies import get_http_headers


from starlette.responses import JSONResponse

import argparse
import asyncio
import json
import logging
import os
from typing import Annotated, Any

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
async def health_check(request: Any) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "mcp-server"})


def _unwrap(resp: Any) -> Any:
    """Strip WeKnora's ``code``/``message`` envelope, returning the ``data`` payload.

    Most retrieval endpoints respond as ``{"code", "message", "data"}``; this
    collapses such responses to their ``data`` value so the LLM receives only
    the business payload. Responses without a ``data`` key (e.g. the wiki
    endpoints, which return bare entities or lists) are returned unchanged.
    """
    if isinstance(resp, dict) and "data" in resp:
        return resp["data"]
    return resp


def _kb_summary(kb: Any) -> KBSummary:
    """Project a full KB payload to the LLM-facing summary fields."""
    return {
        "id": kb.get("id", ""),
        "name": kb.get("name", ""),
        "description": kb.get("description", ""),
        "type": kb.get("type", ""),
        "knowledge_count": kb.get("knowledge_count", 0),
        "capabilities": kb.get("capabilities") or {},
        "created_at": kb.get("created_at", ""),
        "updated_at": kb.get("updated_at", ""),
    }


# ── Knowledge Base Management ─────────────────────────────────────────────────


@mcp.tool()
async def list_knowledge_bases(client: WeKnoraClient = ClientDependency) -> str:
    """List all knowledge bases (slim summary per KB)."""
    data = _unwrap(client.list_knowledge_bases())
    return json.dumps([_kb_summary(kb) for kb in (data or [])], indent=2, ensure_ascii=False)


@mcp.tool()
async def get_knowledge_base(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get knowledge base details (slim summary)."""
    return json.dumps(_kb_summary(_unwrap(client.get_knowledge_base(client.resolve_kb_id(kb_id)))), indent=2, ensure_ascii=False)


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
        _unwrap(client.hybrid_search(client.resolve_kb_id(kb_id), query, config)),
        indent=2,
        ensure_ascii=False,
    )


# ── Knowledge Management ──────────────────────────────────────────────────────


@mcp.tool()
async def list_knowledge(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    page: Annotated[int, Field(description="Page number")] = 1,
    page_size: Annotated[int, Field(description="Page size")] = 20,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """List knowledge in a knowledge base."""
    return json.dumps(
        _unwrap(client.list_knowledge(client.resolve_kb_id(kb_id), page, page_size)),
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
async def get_knowledge(
    knowledge_id: Annotated[str, Field(description="Knowledge ID")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get knowledge details."""
    return json.dumps(_unwrap(client.get_knowledge(knowledge_id)), indent=2, ensure_ascii=False)


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
    return json.dumps(_unwrap(client.wiki_search(client.resolve_kb_id(kb_id), query, limit)), indent=2, ensure_ascii=False)


@mcp.tool()
async def wiki_read_page(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    slug: Annotated[str, Field(description="Page slug (e.g. 'entity/acme-corp', 'concept/rag')")],
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Read a wiki page by its slug.

    Returns full markdown content, metadata, inbound/outbound links, and source references.
    """
    return json.dumps(_unwrap(client.wiki_read_page(client.resolve_kb_id(kb_id), slug)), indent=2, ensure_ascii=False)


@mcp.tool()
async def wiki_index_view(
    kb_id: Annotated[str, Field(description="Knowledge base ID")],
    limit: Annotated[int, Field(description="Maximum items per type group")] = 50,
    client: WeKnoraClient = ClientDependency,
) -> str:
    """Get a structured wiki index with per-type directory groups.

    Returns an overview of all wiki pages organized by type (entity, concept, summary, etc.).
    """
    return json.dumps(_unwrap(client.wiki_index_view(client.resolve_kb_id(kb_id), limit)), indent=2, ensure_ascii=False)


# ── Transport helpers ─────────────────────────────────────────────────────────


async def run_stdio() -> None:
    """Run the MCP server using stdio transport"""
    await mcp.run_async(transport="stdio", show_banner=False)


async def run_sse(host: str, port: int) -> None:
    """Run the MCP server using SSE transport (legacy MCP clients)."""
    await mcp.run_async(transport="sse", host=host, port=port, show_banner=False)


async def run_http(host: str, port: int) -> None:
    """Run the MCP server using Streamable HTTP transport."""
    await mcp.run_async(transport="http", host=host, port=port, show_banner=False)


def main() -> None:
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

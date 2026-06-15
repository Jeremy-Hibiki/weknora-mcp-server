#!/usr/bin/env python3
"""
WeKnora MCP Server

A Model Context Protocol server that provides access to the WeKnora knowledge management API.
"""

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
from uuid import UUID

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
import urllib3
import requests
from fastmcp import FastMCP
from pydantic import Field
from requests.exceptions import RequestException

# Set up logging configuration for the MCP server
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Load from environment variables with defaults
WEKNORA_BASE_URL = os.getenv("WEKNORA_BASE_URL", "http://localhost:8080/api/v1")
# Chat SSE read timeout in seconds. LLM responses can be slow; default 300s.
try:
    WEKNORA_CHAT_TIMEOUT = int(os.getenv("WEKNORA_CHAT_TIMEOUT", "300"))
except ValueError:
    logger.warning("WEKNORA_CHAT_TIMEOUT is not a valid integer; falling back to 300s.")
    WEKNORA_CHAT_TIMEOUT = 300


class WeKnoraClient:
    """Client for interacting with WeKnora API"""

    def __init__(self, base_url: str, api_key: str):
        """Initialize the WeKnora API client with base URL and authentication"""
        self.base_url = base_url
        self.api_key = api_key
        # SSL verification: enabled by default. Set WEKNORA_VERIFY_SSL=false to disable
        # (e.g. for self-signed certs in dev environments — NOT recommended for production).
        self.verify_ssl = os.getenv("WEKNORA_VERIFY_SSL", "true").lower() != "false"
        if not self.verify_ssl:
            logger.warning(
                "SSL certificate verification is DISABLED (WEKNORA_VERIFY_SSL=false). "
                "This is insecure and should not be used in production."
            )
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Create a persistent session for connection pooling and performance
        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        # Set default headers for all requests
        self.session.headers.update(
            {
                "X-API-Key": api_key,  # API key for authentication
                "Content-Type": "application/json",  # Default content type
            }
        )

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the WeKnora API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests

        Returns:
            JSON response as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def _resolve_uuid(self, uuid: str | UUID) -> str | None:
        """Resolve a UUID or string to a UUID"""
        if isinstance(uuid, UUID):
            return str(uuid)
        try:
            return str(UUID(uuid))
        except ValueError:
            return None

    # Tenant Management - Methods for managing multi-tenant configurations
    def create_tenant(self, name: str, description: str, business: str, retriever_engines: Dict) -> Dict:
        """Create a new tenant with specified configuration"""
        data = {
            "name": name,
            "description": description,
            "business": business,
            "retriever_engines": retriever_engines,  # Configuration for search engines
        }
        return self._request("POST", "/tenants", json=data)

    def get_tenant(self, tenant_id: str) -> Dict:
        """Get tenant information"""
        return self._request("GET", f"/tenants/{tenant_id}")

    def list_tenants(self) -> Dict:
        """List all tenants"""
        return self._request("GET", "/tenants")

    # Knowledge Base Management - Methods for managing knowledge bases
    def create_knowledge_base(self, name: str, description: str, config: Dict) -> Dict:
        """Create a new knowledge base with chunking and model configuration"""
        data = {
            "name": name,
            "description": description,
            **config,  # Merge additional configuration (chunking, models, etc.)
        }
        return self._request("POST", "/knowledge-bases", json=data)

    def list_knowledge_bases(self) -> Dict:
        """List all knowledge bases"""
        return self._request("GET", "/knowledge-bases")

    def get_knowledge_base(self, kb_id: str) -> Dict:
        """Get knowledge base details"""
        return self._request("GET", f"/knowledge-bases/{kb_id}")

    def update_knowledge_base(self, kb_id: str, updates: Dict) -> Dict:
        """Update knowledge base"""
        return self._request("PUT", f"/knowledge-bases/{kb_id}", json=updates)

    def delete_knowledge_base(self, kb_id: str) -> Dict:
        """Delete knowledge base"""
        return self._request("DELETE", f"/knowledge-bases/{kb_id}")

    def resolve_agent_id(self, agent_id_or_name: str) -> str:
        """Resolve an agent name to its UUID if needed.

        If *agent_id_or_name* is already a UUID it is returned unchanged.
        Otherwise all agents are listed and the first one whose
        ``name`` matches (case-insensitive) is returned.
        Raises ValueError when no match is found.
        """
        if agent_id := self._resolve_uuid(agent_id_or_name):
            return agent_id
        resp = self._request("GET", "/agents")
        agents = resp.get("data", resp) if isinstance(resp, dict) else resp
        if isinstance(agents, dict):
            agents = agents.get("list", agents.get("items", []))
        needle = agent_id_or_name.lower()
        for agent in agents or []:
            if isinstance(agent, dict) and agent.get("name", "").lower() == needle:
                return agent["id"]
        raise ValueError(
            f"Agent {agent_id_or_name!r} not found. Use list_agents to see available agent IDs and names."
        )

    def resolve_kb_id(self, kb_id_or_name: str) -> str:
        """Resolve a knowledge base name to its UUID if needed.

        If *kb_id_or_name* is already a UUID it is returned unchanged.
        Otherwise all knowledge bases are listed and the first one whose
        ``name`` matches (case-insensitive) is returned.
        Raises ValueError when no match is found.
        """
        if kb_id := self._resolve_uuid(kb_id_or_name):
            return kb_id
        resp = self.list_knowledge_bases()
        kbs = resp.get("data", resp) if isinstance(resp, dict) else resp
        if isinstance(kbs, dict):
            kbs = kbs.get("list", kbs.get("items", []))
        needle = kb_id_or_name.lower()
        for kb in kbs or []:
            if isinstance(kb, dict) and kb.get("name", "").lower() == needle:
                return kb["id"]
        raise ValueError(
            f"Knowledge base {kb_id_or_name!r} not found. Use list_knowledge_bases to see available IDs and names."
        )

    def hybrid_search(self, kb_id: str, query: str, config: Dict) -> Dict:
        """Perform hybrid search combining vector and keyword search"""
        data = {
            "query_text": query,
            **config,  # Include thresholds and match count
        }
        return self._request("GET", f"/knowledge-bases/{kb_id}/hybrid-search", json=data)

    # Knowledge Management - Methods for creating and managing knowledge entries
    def create_knowledge_from_file(self, kb_id: str, file_path: str, enable_multimodel: bool = True) -> Dict:
        """Create knowledge from a local file with optional multimodal processing"""
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"enable_multimodel": str(enable_multimodel).lower()}
            # Temporarily remove Content-Type header for multipart/form-data request
            # (requests will set it automatically with boundary)
            headers = self.session.headers.copy()
            del headers["Content-Type"]
            # Use requests.post directly instead of session to avoid header conflicts
            response = requests.post(
                f"{self.base_url}/knowledge-bases/{kb_id}/knowledge/file",
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
            return response.json()

    def create_knowledge_from_url(self, kb_id: str, url: str, enable_multimodel: bool = True) -> Dict:
        """Create knowledge from a web URL with optional multimodal processing"""
        data = {
            "url": url,  # Web URL to fetch and process
            "enable_multimodel": enable_multimodel,  # Enable image/multimodal extraction
        }
        return self._request("POST", f"/knowledge-bases/{kb_id}/knowledge/url", json=data)

    def list_knowledge(self, kb_id: str, page: int = 1, page_size: int = 20) -> Dict:
        """List knowledge in a knowledge base"""
        params = {"page": page, "page_size": page_size}
        return self._request("GET", f"/knowledge-bases/{kb_id}/knowledge", params=params)

    def get_knowledge(self, knowledge_id: str) -> Dict:
        """Get knowledge details"""
        return self._request("GET", f"/knowledge/{knowledge_id}")

    def delete_knowledge(self, knowledge_id: str) -> Dict:
        """Delete knowledge"""
        return self._request("DELETE", f"/knowledge/{knowledge_id}")

    # Model Management - Methods for managing AI models (LLM, Embedding, Rerank)
    def create_model(
        self,
        name: str,
        model_type: str,
        source: str,
        description: str,
        parameters: Dict,
        is_default: bool = False,
    ) -> Dict:
        """Create a new AI model configuration"""
        data = {
            "name": name,
            "type": model_type,  # KnowledgeQA, Embedding, or Rerank
            "source": source,  # local, openai, etc.
            "description": description,
            "parameters": parameters,  # API keys, base URLs, etc.
            "is_default": is_default,  # Set as default model for this type
        }
        return self._request("POST", "/models", json=data)

    def list_models(self) -> Dict:
        """List all models"""
        return self._request("GET", "/models")

    def get_model(self, model_id: str) -> Dict:
        """Get model details"""
        return self._request("GET", f"/models/{model_id}")

    # Session Management - Methods for managing chat sessions
    def create_session(
        self,
        kb_id: str,
        max_rounds: int = 5,
        enable_rewrite: bool = True,
        fallback_response: str = "Sorry, I cannot answer this question.",
        summary_model_id: str = "",
        title: str = "",
        description: str = "",
    ) -> Dict:
        """Create a new chat session with strategy configuration"""
        strategy = {
            "max_rounds": max_rounds,
            "enable_rewrite": enable_rewrite,
            "fallback_strategy": "FIXED_RESPONSE",
            "fallback_response": fallback_response,
            "embedding_top_k": 10,
            "keyword_threshold": 0.5,
            "vector_threshold": 0.7,
            "summary_model_id": summary_model_id,
        }
        data = {
            "knowledge_base_id": kb_id,
            "session_strategy": strategy,
        }
        if title:
            data["title"] = title
        if description:
            data["description"] = description
        return self._request("POST", "/sessions", json=data)

    def get_session(self, session_id: str) -> Dict:
        """Get session details"""
        return self._request("GET", f"/sessions/{session_id}")

    def list_sessions(self, page: int = 1, page_size: int = 20) -> Dict:
        """List sessions"""
        params = {"page": page, "page_size": page_size}
        return self._request("GET", "/sessions", params=params)

    def delete_session(self, session_id: str) -> Dict:
        """Delete session"""
        return self._request("DELETE", f"/sessions/{session_id}")

    # Chat Functionality - Methods for conversational interactions
    def _consume_sse_stream(self, url: str, body: Dict[str, Any]) -> Dict:
        """POST to *url* with *body*, consume the SSE stream, and return the assembled result.

        Centralised helper used by both chat() and agent_chat().
        Timeout: (10s connect, WEKNORA_CHAT_TIMEOUT read) — configurable via env var.

        Server-Sent Events (SSE) stream format:
          data: {"response_type": "answer", "content": "..."}
          data: {"response_type": "references", "knowledge_references": [...]}
          data: {"response_type": "complete"}

        We accumulate answer chunks and extract references, returning them as a dict.
        """
        try:
            # POST with stream=True to receive server-sent events incrementally
            # Timeout: 10s to establish connection, WEKNORA_CHAT_TIMEOUT for reading response
            response = self.session.post(
                url,
                json=body,
                stream=True,
                timeout=(10, WEKNORA_CHAT_TIMEOUT),
            )
            response.raise_for_status()

            answer_chunks: list = []
            references: list = []
            debug_events: list = []

            # Use context manager to ensure the connection is returned to the pool
            # even when breaking early on a 'complete' event.
            with response:
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    if isinstance(raw_line, bytes):
                        raw_line = raw_line.decode("utf-8")
                    # Each SSE event is prefixed with "data: " followed by JSON payload
                    if not raw_line.startswith("data:"):
                        continue
                    payload = raw_line[5:].lstrip(" ")
                    try:
                        event_data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    response_type = event_data.get("response_type", "")
                    debug_events.append(
                        {
                            "type": response_type,
                            "content": event_data.get("content", "")[:80],
                        }
                    )

                    # Parse different SSE event types: answer chunks, references, errors, completion
                    if response_type == "answer":
                        chunk = event_data.get("content", "")
                        if chunk:
                            answer_chunks.append(chunk)
                    elif response_type == "references":
                        references = event_data.get("knowledge_references") or []
                    elif response_type == "error":
                        raise RequestException(f"Server error: {event_data.get('content', 'unknown error')}")
                    elif response_type == "complete":
                        break

            return {
                "answer": "".join(answer_chunks),
                "references": references,
                "_debug_events": debug_events,
            }
        except RequestException as e:
            logger.error(f"SSE stream request failed ({url}): {e}")
            raise

    def chat(
        self,
        session_id: str,
        query: str,
        knowledge_base_ids: list | None = None,
        web_search_enabled: bool = False,
        enable_memory: bool = False,
    ) -> Dict:
        """Send a message to the RAG pipeline (knowledge-chat) and return the assembled answer.

        Provide *knowledge_base_ids* (UUID or name) so the backend can retrieve
        relevant chunks before summarising with the LLM.
        For agentic tool-calling use agent_chat() instead.
        """
        url = f"{self.base_url}/knowledge-chat/{session_id}"
        body: Dict[str, Any] = {"query": query, "channel": "api"}
        if knowledge_base_ids:
            body["knowledge_base_ids"] = knowledge_base_ids
        if web_search_enabled:
            body["web_search_enabled"] = True
        if enable_memory:
            body["enable_memory"] = True
        result = self._consume_sse_stream(url, body)
        result["session_id"] = session_id
        return result

    def agent_chat(
        self,
        session_id: str,
        query: str,
        agent_id: str,
        knowledge_base_ids: list | None = None,
        web_search_enabled: bool = False,
        enable_memory: bool = False,
    ) -> Dict:
        """Send a message to the agentic pipeline (agent-chat) and return the assembled answer.

        *agent_id* is required — the backend uses the CustomAgent config for
        tool selection (knowledge_search, web_search, SQL, etc.).
        The agent autonomously decides which knowledge bases to query;
        pass *knowledge_base_ids* to override or supplement the agent's default KBs.
        """
        url = f"{self.base_url}/agent-chat/{session_id}"
        body: Dict[str, Any] = {"query": query, "agent_id": agent_id, "channel": "api"}
        if knowledge_base_ids:
            body["knowledge_base_ids"] = knowledge_base_ids
        if web_search_enabled:
            body["web_search_enabled"] = True
        if enable_memory:
            body["enable_memory"] = True
        result = self._consume_sse_stream(url, body)
        result["session_id"] = session_id
        return result

    def list_agents(self, page: int = 1, page_size: int = 50) -> Dict:
        """List all custom agents available to the current tenant."""
        return self._request("GET", "/agents", params={"page": page, "page_size": page_size})

    def get_agent(self, agent_id: str) -> Dict:
        """Get full config of a single agent by UUID."""
        return self._request("GET", f"/agents/{agent_id}")

    # Chunk Management - Methods for managing knowledge chunks (text segments)
    def list_chunks(self, knowledge_id: str, page: int = 1, page_size: int = 20) -> Dict:
        """List text chunks of a knowledge entry with pagination"""
        params = {"page": page, "page_size": page_size}
        return self._request("GET", f"/chunks/{knowledge_id}", params=params)

    def delete_chunk(self, knowledge_id: str, chunk_id: str) -> Dict:
        """Delete a chunk"""
        return self._request("DELETE", f"/chunks/{knowledge_id}/{chunk_id}")

    # Wiki Read-Only - Methods for querying LLM-generated wiki pages
    def wiki_search(self, kb_id: str, query: str, limit: int = 10) -> Dict:
        """Search wiki pages by full-text query"""
        return self._request(
            "GET",
            f"/knowledgebase/{kb_id}/wiki/search",
            params={"q": query, "limit": limit},
        )

    def wiki_read_page(self, kb_id: str, slug: str) -> Dict:
        """Read a wiki page by slug, returns full markdown + metadata + links"""
        return self._request("GET", f"/knowledgebase/{kb_id}/wiki/pages/{slug}")

    def wiki_index_view(self, kb_id: str, limit: int = 50) -> Dict:
        """Get structured wiki index with per-type directory groups"""
        return self._request(
            "GET",
            f"/knowledgebase/{kb_id}/wiki/index",
            params={"limit": limit},
        )


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

from __future__ import annotations

import logging
import os
from typing import Any, cast
from uuid import UUID

import urllib3
import requests
from requests.exceptions import RequestException

from ._types.responses import (
    HybridSearchResponse,
    KnowledgeBaseDetailResponse,
    KnowledgeBaseListResponse,
    KnowledgeDetailResponse,
    KnowledgeListResponse,
)
from ._types.weknora import WikiIndexResponse

# Set up logging configuration for the MCP server
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeKnoraClient:
    """Read-only client for interacting with the WeKnora API.

    Only exposes retrieval endpoints (list / get / search / wiki). Mutating
    operations (create / update / delete) and chat pipelines are intentionally
    omitted — the MCP server built on top of this client is read-only.
    """

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

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """Make a request to the WeKnora API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests

        Returns:
            JSON response as dictionary

        Note:
            Returns ``Any``; callers ``cast`` it to the concrete response TypedDict
            declared by their signature. The runtime payload is the raw JSON dict.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def _resolve_uuid(self, value: str | UUID) -> str | None:
        """Resolve a UUID or string to a UUID string, or None if not parseable."""
        if isinstance(value, UUID):
            return str(value)
        try:
            return str(UUID(value))
        except ValueError:
            return None

    # Knowledge Base Management - Read-only access to knowledge bases
    def list_knowledge_bases(self) -> KnowledgeBaseListResponse:
        """List all knowledge bases"""
        return cast(KnowledgeBaseListResponse, self._request("GET", "/knowledge-bases"))

    def get_knowledge_base(self, kb_id: str) -> KnowledgeBaseDetailResponse:
        """Get knowledge base details"""
        return cast(KnowledgeBaseDetailResponse, self._request("GET", f"/knowledge-bases/{kb_id}"))

    def resolve_kb_id(self, kb_id_or_name: str) -> str:
        """Resolve a knowledge base name to its UUID if needed.

        If *kb_id_or_name* is already a UUID it is returned unchanged.
        Otherwise all knowledge bases are listed and the first one whose
        ``name`` matches (case-insensitive) is returned.
        Raises ValueError when no match is found.
        """
        if kb_id := self._resolve_uuid(kb_id_or_name):
            return kb_id
        resp: Any = self._request("GET", "/knowledge-bases")
        kbs = resp.get("data", resp) if isinstance(resp, dict) else resp
        if isinstance(kbs, dict):
            kbs = kbs.get("list", kbs.get("items", []))
        needle = kb_id_or_name.lower()
        for kb in kbs or []:
            if isinstance(kb, dict) and str(kb.get("name", "")).lower() == needle:
                return str(kb["id"])
        raise ValueError(
            f"Knowledge base {kb_id_or_name!r} not found. Use list_knowledge_bases to see available IDs and names."
        )

    def hybrid_search(self, kb_id: str, query: str, config: dict[str, Any]) -> HybridSearchResponse:
        """Perform hybrid search combining vector and keyword search"""
        data = {
            "query_text": query,
            **config,  # Include thresholds and match count
        }
        return cast(
            HybridSearchResponse,
            self._request("GET", f"/knowledge-bases/{kb_id}/hybrid-search", json=data),
        )

    # Knowledge Management - Read-only access to knowledge entries
    def list_knowledge(self, kb_id: str, page: int = 1, page_size: int = 20) -> KnowledgeListResponse:
        """List knowledge in a knowledge base"""
        params = {"page": page, "page_size": page_size}
        return cast(
            KnowledgeListResponse,
            self._request("GET", f"/knowledge-bases/{kb_id}/knowledge", params=params),
        )

    def get_knowledge(self, knowledge_id: str) -> KnowledgeDetailResponse:
        """Get knowledge details"""
        return cast(KnowledgeDetailResponse, self._request("GET", f"/knowledge/{knowledge_id}"))

    # Wiki Read-Only - Methods for querying LLM-generated wiki pages.
    # These endpoints return entities directly (no code/message envelope).
    def wiki_search(self, kb_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        """Search wiki pages by full-text query. Returns ``{"pages": [...]}``."""
        return cast(
            dict[str, Any],
            self._request(
                "GET",
                f"/knowledgebase/{kb_id}/wiki/search",
                params={"q": query, "limit": limit},
            ),
        )

    def wiki_read_page(self, kb_id: str, slug: str) -> dict[str, Any]:
        """Read a wiki page by slug (full markdown + metadata + links)."""
        return cast(dict[str, Any], self._request("GET", f"/knowledgebase/{kb_id}/wiki/pages/{slug}"))

    def wiki_index_view(self, kb_id: str, limit: int = 50) -> WikiIndexResponse:
        """Get structured wiki index with per-type directory groups"""
        return cast(
            WikiIndexResponse,
            self._request(
                "GET",
                f"/knowledgebase/{kb_id}/wiki/index",
                params={"limit": limit},
            ),
        )

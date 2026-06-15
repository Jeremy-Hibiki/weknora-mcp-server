"""WeKnora API 响应类型定义。

集中定义知识库检索 / 查询类只读端点的响应 TypedDict，复用 :mod:`weknora`
中的业务模型作为 ``data`` 字段类型注解（仅用于静态类型检查，运行时不解析）。

响应包装结构（``code`` / ``message`` / ``data``）基于 :class:`WeKnoraClient`
运行时线索（``resp.get("data", resp)``）推断；``openapi.json`` 对大多数 GET
响应仅声明为泛型 ``object``，未提供精确 schema。

wiki 系列端点例外：按 ``openapi.json`` 直接返回实体（``list[WikiPage]`` /
``WikiPage`` / ``WikiIndexResponse``），不带 ``code``/``message`` 包装。

注：mypy 不允许子类 TypedDict 重定义父类字段的类型，故每个响应独立声明
``code`` / ``message`` / ``data``，不复用基类继承。
"""

from __future__ import annotations

from typing import TypedDict

from .weknora import (
    Knowledge,
    KnowledgeBase,
    SearchResult,
)


# ── Knowledge Base ────────────────────────────────────────────────────────────


class KnowledgeBaseListResponse(TypedDict):
    code: int
    message: str
    data: list[KnowledgeBase]


class KnowledgeBaseDetailResponse(TypedDict):
    code: int
    message: str
    data: KnowledgeBase


class HybridSearchResponse(TypedDict):
    code: int
    message: str
    data: list[SearchResult]


# ── Knowledge ─────────────────────────────────────────────────────────────────


class KnowledgeListResponse(TypedDict):
    code: int
    message: str
    data: list[Knowledge]


class KnowledgeDetailResponse(TypedDict):
    code: int
    message: str
    data: Knowledge


# ── Slim views (tool-facing, LLM-friendly projections) ────────────────────────


class KBSummary(TypedDict):
    """list_knowledge_bases 的精简视图，只保留对检索决策有用的字段。"""

    id: str
    name: str
    description: str
    type: str
    knowledge_count: int
    capabilities: dict[str, bool]
    created_at: str
    updated_at: str

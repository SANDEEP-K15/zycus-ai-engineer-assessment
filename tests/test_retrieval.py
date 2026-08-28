from pathlib import Path

import pytest

from support_ai.retrieval import KnowledgeBase

ROOT = Path(__file__).parents[1]


def test_kb_loads_all_documents() -> None:
    kb = KnowledgeBase(ROOT / "knowledge-base")
    assert len({c.document for c in kb.chunks}) == 9


def test_timeout_retrieval() -> None:
    kb = KnowledgeBase(ROOT / "knowledge-base")
    results = kb.search("ERR_CONNECTION_TIMEOUT after 30s")
    assert results
    assert any("performance-and-integrations.md" in c.document for c, _ in results)


def test_scope_error_retrieval() -> None:
    kb = KnowledgeBase(ROOT / "knowledge-base")
    results = kb.search("403 Forbidden insufficient_scope")
    assert any("authentication-sso.md" in c.document for c, _ in results)


def test_empty_query_is_safe() -> None:
    kb = KnowledgeBase(ROOT / "knowledge-base")
    assert kb.search("   ") == []


def test_non_positive_top_k_is_safe() -> None:
    kb = KnowledgeBase(ROOT / "knowledge-base")
    assert kb.search("billing", top_k=0) == []


def test_missing_kb_fails_clearly() -> None:
    with pytest.raises(FileNotFoundError, match="Knowledge-base directory"):
        KnowledgeBase(ROOT / "does-not-exist")

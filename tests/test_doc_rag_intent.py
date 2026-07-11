from agent.policies.doc_rag_intent import decide_doc_rag_preload


def test_strong_doc_intent_preloads_search_docs_only() -> None:
    decision = decide_doc_rag_preload("请从文档知识库中检索 agent runtime 负责什么")

    assert decision.preload_search_docs is True
    assert decision.preload_fetch_doc_chunk is False
    assert decision.suppress_doc_rag_lru is False
    assert decision.confidence == "high"
    assert decision.reason == "strong_doc_intent"
    assert "文档知识库" in decision.matched_terms


def test_strong_doc_with_evidence_intent_preloads_fetch_doc_chunk() -> None:
    decision = decide_doc_rag_preload("根据项目文档回答，并展开原文证据")

    assert decision.preload_search_docs is True
    assert decision.preload_fetch_doc_chunk is True
    assert decision.suppress_doc_rag_lru is False
    assert decision.confidence == "high"
    assert decision.reason == "strong_doc_with_fetch_intent"
    assert "项目文档" in decision.matched_terms
    assert "原文" in decision.matched_terms


def test_fetch_doc_chunk_name_preloads_fetch_even_without_other_fetch_terms() -> None:
    decision = decide_doc_rag_preload("请使用 fetch_doc_chunk 查看文档引用")

    assert decision.preload_search_docs is True
    assert decision.preload_fetch_doc_chunk is True
    assert decision.reason == "strong_doc_with_fetch_intent"


def test_explicit_no_doc_suppresses_doc_rag_lru() -> None:
    decision = decide_doc_rag_preload("不要查文档，只从长期记忆回答")

    assert decision.preload_search_docs is False
    assert decision.preload_fetch_doc_chunk is False
    assert decision.suppress_doc_rag_lru is True
    assert decision.confidence == "high"
    assert decision.reason == "blocked_by_explicit_no_doc"


def test_memory_intent_without_doc_suppresses_doc_rag_lru() -> None:
    decision = decide_doc_rag_preload("你还记得我之前说过我的偏好吗？")

    assert decision.preload_search_docs is False
    assert decision.preload_fetch_doc_chunk is False
    assert decision.suppress_doc_rag_lru is True
    assert decision.confidence == "high"
    assert decision.reason == "blocked_by_memory_intent"


def test_ambiguous_question_does_not_preload_doc_rag() -> None:
    decision = decide_doc_rag_preload("agent runtime 是什么？")

    assert decision.preload_search_docs is False
    assert decision.preload_fetch_doc_chunk is False
    assert decision.suppress_doc_rag_lru is False
    assert decision.confidence == "none"
    assert decision.reason == "no_doc_intent"

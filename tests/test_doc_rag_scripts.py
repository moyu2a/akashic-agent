from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent.config_models import Config
from core.net.http import (
    clear_default_shared_http_resources,
    get_default_shared_http_resources,
)
from scripts import doc_rag_index_check


def _config(repo: Path, db_path: Path) -> Config:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="main-key",
        base_url="https://main.example/v1",
        system_prompt="test",
    )
    cfg.doc_rag.source_root = str(repo)
    cfg.doc_rag.store_path = str(db_path)
    cfg.doc_rag.embedding.mode = "custom"
    cfg.doc_rag.embedding.model = "fake-embedding"
    cfg.doc_rag.embedding.api_key = "doc-key"
    cfg.doc_rag.embedding.base_url = "https://embedding.example/v1"
    cfg.doc_rag.embedding.dim = 2
    return cfg


@pytest.mark.anyio
async def test_index_check_configures_http_resources_for_standalone_run(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        doc_rag_index_check,
        "load_config",
        lambda _path: _config(tmp_path / "repo", tmp_path / "doc_rag.db"),
    )
    monkeypatch.setattr(sys, "argv", ["doc_rag_index_check", "--rebuild"])

    try:
        await doc_rag_index_check._main()

        output = capsys.readouterr().out
        assert "status: succeeded" in output
        with pytest.raises(RuntimeError, match="shared http resources not configured"):
            get_default_shared_http_resources()
    finally:
        clear_default_shared_http_resources()

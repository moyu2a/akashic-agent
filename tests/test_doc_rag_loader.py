from __future__ import annotations

from pathlib import Path

from agent.config_models import DocRagConfig
from doc_rag.loader import MarkdownLoader


def test_loader_scans_only_configured_corpus(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "a.md").write_text("# Title A\n\nBody", encoding="utf-8")
    other = repo / "my_md" / "rag"
    other.mkdir(parents=True)
    (other / "ignore.md").write_text("# Ignore", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert [doc.source_path for doc in result.documents] == [
        "my_md/doc_rag_corpus/a.md"
    ]
    assert result.documents[0].title == "Title A"
    assert result.errors == []


def test_loader_reports_empty_and_decode_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "empty.md").write_text("   \n", encoding="utf-8")
    (corpus / "bad.md").write_bytes(b"\xff\xfe\x00")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents == []
    assert {err.error_type for err in result.errors} == {"skip_empty", "decode_error"}


def test_loader_uses_repo_relative_posix_source_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested = repo / "my_md" / "doc_rag_corpus" / "nested"
    nested.mkdir(parents=True)
    (nested / "b.md").write_text("## Subtitle\ncontent", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents[0].source_path == "my_md/doc_rag_corpus/nested/b.md"
    assert "\\" not in result.documents[0].source_path


def test_loader_reports_non_markdown_when_include_matches(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "note.txt").write_text("not markdown", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    cfg.sources.include_globs = ["my_md/doc_rag_corpus/**/*"]
    result = MarkdownLoader(cfg).load_all()

    assert result.documents == []
    assert [(err.source_path, err.error_type) for err in result.errors] == [
        ("my_md/doc_rag_corpus/note.txt", "not_markdown")
    ]


def test_loader_reports_too_large_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "large.md").write_text("# Large\n\nabcdef", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    cfg.sources.max_file_size_bytes = 4
    result = MarkdownLoader(cfg).load_all()

    assert result.errors[0].error_type == "skip_too_large"


def test_loader_internal_symlink_keeps_symlink_source_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    target_dir = repo / "docs"
    corpus.mkdir(parents=True)
    target_dir.mkdir()
    (target_dir / "target.md").write_text("# Target\n\nBody", encoding="utf-8")
    (corpus / "linked.md").symlink_to(target_dir / "target.md")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents[0].source_path == "my_md/doc_rag_corpus/linked.md"


def test_loader_external_symlink_is_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    outside = tmp_path / "outside.md"
    corpus.mkdir(parents=True)
    outside.write_text("# Outside", encoding="utf-8")
    (corpus / "outside.md").symlink_to(outside)

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents == []
    assert result.errors[0].source_path == "my_md/doc_rag_corpus/outside.md"
    assert result.errors[0].error_type == "external_symlink"

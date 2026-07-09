from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from agent.config_models import DocRagConfig
from doc_rag.models import (
    LoadedDocument,
    LoaderError,
    LoaderResult,
    build_doc_id,
    stable_sha256,
)


class MarkdownLoader:
    def __init__(self, config: DocRagConfig) -> None:
        self.config = config
        self.source_root = Path(config.source_root).expanduser().resolve()

    def load_all(self) -> LoaderResult:
        result = LoaderResult()
        for path in self.scan():
            item = self.load_path(path)
            if isinstance(item, LoadedDocument):
                result.documents.append(item)
            else:
                result.errors.append(item)
        result.documents.sort(key=lambda doc: doc.source_path)
        result.errors.sort(key=lambda err: err.source_path or err.raw_path)
        return result

    def scan(self) -> list[Path]:
        candidates: set[Path] = set()
        for pattern in self.config.sources.include_globs:
            candidates.update(self.source_root.glob(pattern))
        paths = []
        for path in candidates:
            if not path.is_file():
                continue
            source_path = self._source_path(path)
            if self._is_excluded(source_path):
                continue
            paths.append(path)
        return sorted(paths, key=lambda p: self._source_path(p))

    def load_path(self, path: Path) -> LoadedDocument | LoaderError:
        raw_path = str(path)
        source_path = ""
        try:
            source_path = self._source_path(path)
            resolved = path.resolve()
            if path.is_symlink() and not self.config.sources.allow_external_symlink:
                if not self._is_within_root(resolved):
                    return LoaderError(
                        raw_path,
                        source_path,
                        "external_symlink",
                        "symlink 指向 repo 外",
                    )
            if not self._is_within_root(path.parent.resolve()):
                return LoaderError(
                    raw_path,
                    source_path,
                    "outside_source_root",
                    "文件不在 source_root 内",
                )
            if path.suffix.lower() not in self.config.sources.allowed_extensions:
                return LoaderError(
                    raw_path, source_path, "not_markdown", "不是 Markdown 文件"
                )
            size = path.stat().st_size
            if size > self.config.sources.max_file_size_bytes:
                return LoaderError(
                    raw_path, source_path, "skip_too_large", "文件超过大小限制"
                )
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    return LoaderError(
                        raw_path, source_path, "decode_error", "文件不是 UTF-8"
                    )
            if not content.strip():
                return LoaderError(
                    raw_path, source_path, "skip_empty", "空 Markdown 文件"
                )
            return LoadedDocument(
                doc_id=build_doc_id(source_path),
                source_path=source_path,
                title=self._extract_title(content, path),
                content=content,
                content_hash=stable_sha256(content),
                file_mtime=path.stat().st_mtime,
                file_size=size,
                metadata={},
            )
        except OSError as exc:
            return LoaderError(raw_path, source_path, "read_error", str(exc))

    def _source_path(self, path: Path) -> str:
        return path.relative_to(self.source_root).as_posix()

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.source_root)
            return True
        except ValueError:
            return False

    def _is_excluded(self, source_path: str) -> bool:
        return any(
            fnmatch(source_path, pattern)
            for pattern in self.config.sources.exclude_globs
        )

    def _extract_title(self, content: str, path: Path) -> str:
        first_heading = ""
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            title = stripped.lstrip("#").strip()
            if stripped.startswith("# ") and title:
                return title
            if title and not first_heading:
                first_heading = title
        return first_heading or path.stem

from __future__ import annotations

from dataclasses import dataclass

from agent.config_models import DocRagChunkingConfig
from doc_rag.models import (
    ChunkRecord,
    LoadedDocument,
    build_chunk_id,
    build_chunk_key,
    stable_sha256,
)


@dataclass
class _Block:
    heading_path: str
    text: str
    block_type: str
    start_line: int
    end_line: int


class MarkdownChunker:
    def __init__(self, config: DocRagChunkingConfig) -> None:
        self.config = config

    def chunk(self, document: LoadedDocument) -> list[ChunkRecord]:
        blocks = self._parse_blocks(document)
        chunks: list[ChunkRecord] = []
        current: list[_Block] = []
        current_heading = ""

        def flush() -> None:
            nonlocal current, current_heading
            if not current:
                return
            text = "\n\n".join(block.text for block in current).strip()
            if text:
                chunks.append(
                    self._make_chunk(
                        document,
                        current_heading,
                        text,
                        len(chunks),
                        current,
                        "heading_block",
                    )
                )
            current = []
            current_heading = ""

        for block in blocks:
            if len(block.text) > self.config.max_chunk_chars:
                flush()
                chunks.extend(self._split_large_block(document, block, len(chunks)))
                continue
            if current and block.heading_path != current_heading:
                flush()
            candidate_text = "\n\n".join(
                [item.text for item in current] + [block.text]
            ).strip()
            if current and len(candidate_text) > self.config.max_chunk_chars:
                flush()
            current.append(block)
            current_heading = block.heading_path
        flush()
        return chunks

    def _parse_blocks(self, document: LoadedDocument) -> list[_Block]:
        lines = document.content.splitlines()
        headings: list[tuple[int, str]] = []
        blocks: list[_Block] = []
        pending: list[str] = []
        pending_start = 1
        in_code = False
        code_lines: list[str] = []
        code_start = 1

        def heading_path() -> str:
            return " > ".join(title for _, title in headings) or document.title

        def flush_pending(end_line: int) -> None:
            nonlocal pending, pending_start
            text = "\n".join(pending).strip()
            if text:
                blocks.append(
                    _Block(
                        heading_path(),
                        text,
                        self._classify_block(text),
                        pending_start,
                        end_line,
                    )
                )
            pending = []
            pending_start = end_line + 1

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_code:
                    code_lines.append(line)
                    blocks.append(
                        _Block(
                            heading_path(),
                            "\n".join(code_lines),
                            "code_block",
                            code_start,
                            line_number,
                        )
                    )
                    code_lines = []
                    in_code = False
                else:
                    flush_pending(line_number - 1)
                    in_code = True
                    code_lines = [line]
                    code_start = line_number
                continue
            if in_code:
                code_lines.append(line)
                continue
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    flush_pending(line_number - 1)
                    level = len(stripped) - len(stripped.lstrip("#"))
                    headings = [(lvl, val) for lvl, val in headings if lvl < level]
                    headings.append((level, title))
                    pending = [line]
                    pending_start = line_number
                    continue
            if not stripped:
                flush_pending(line_number - 1)
                continue
            if not pending:
                pending_start = line_number
            pending.append(line)
        if in_code and code_lines:
            blocks.append(
                _Block(
                    heading_path(),
                    "\n".join(code_lines),
                    "code_block",
                    code_start,
                    len(lines),
                )
            )
        flush_pending(len(lines))
        return blocks

    def _classify_block(self, text: str) -> str:
        lines = text.splitlines()
        non_empty = [line for line in lines if line.strip()]
        if text.startswith("```"):
            return "code_block"
        if non_empty and all(line.strip().startswith("|") for line in non_empty):
            return "table"
        if non_empty and all(
            line.lstrip().startswith(("-", "*", "+")) for line in non_empty
        ):
            return "list"
        if text.startswith("#"):
            return "heading"
        return "paragraph"

    def _split_large_block(
        self,
        document: LoadedDocument,
        block: _Block,
        start_index: int,
    ) -> list[ChunkRecord]:
        if block.block_type == "table":
            parts = self._split_table(block.text)
        else:
            parts = self._split_text(block.text)
        chunks: list[ChunkRecord] = []
        for offset, (content, reason) in enumerate(parts):
            chunks.append(
                self._make_chunk(
                    document,
                    block.heading_path,
                    content,
                    start_index + offset,
                    [block],
                    reason,
                )
            )
        return chunks

    def _split_text(self, text: str) -> list[tuple[str, str]]:
        max_chars = self.config.max_chunk_chars
        target = min(self.config.target_chunk_chars, max_chars)
        overlap = max(0, min(self.config.chunk_overlap_chars, target // 2))
        parts: list[tuple[str, str]] = []
        start = 0
        text_len = len(text)
        while start < text_len:
            hard_end = min(start + max_chars, text_len)
            end = min(start + target, text_len)
            if end < text_len:
                boundary = text.rfind(" ", start, end)
                if boundary <= start:
                    boundary = text.rfind("\n", start, hard_end)
                if boundary > start:
                    end = boundary
                else:
                    end = hard_end
            part = text[start:end].strip()
            if part:
                reason = "fallback_split"
                if len(part) > max_chars:
                    reason = "unbreakable_too_large"
                parts.append((part, reason))
            if end >= text_len:
                break
            next_start = max(0, end - overlap)
            if next_start <= start:
                next_start = end
            start = next_start
        return parts

    def _split_table(self, text: str) -> list[tuple[str, str]]:
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) < 3:
            return self._split_text(text)
        header = lines[:2]
        rows = lines[2:]
        max_chars = self.config.max_chunk_chars
        parts: list[tuple[str, str]] = []
        current_rows: list[str] = []

        def table_text(rows_to_emit: list[str]) -> str:
            return "\n".join(header + rows_to_emit)

        def flush() -> None:
            nonlocal current_rows
            if current_rows:
                parts.append((table_text(current_rows), "fallback_split"))
                current_rows = []

        for row in rows:
            candidate = table_text(current_rows + [row])
            if current_rows and len(candidate) > max_chars:
                flush()
            single = table_text([row])
            if len(single) > max_chars:
                parts.append((single, "unbreakable_too_large"))
            else:
                current_rows.append(row)
        flush()
        return parts

    def _make_chunk(
        self,
        document: LoadedDocument,
        heading_path: str,
        content: str,
        chunk_index: int,
        blocks: list[_Block],
        split_reason: str,
    ) -> ChunkRecord:
        chunk_hash = stable_sha256(content)
        block_types = sorted({block.block_type for block in blocks})
        metadata = {
            "block_types": block_types,
            "has_code": "code_block" in block_types,
            "has_table": "table" in block_types,
            "has_list": "list" in block_types,
            "split_reason": split_reason,
            "start_line": min(block.start_line for block in blocks),
            "end_line": max(block.end_line for block in blocks),
        }
        return ChunkRecord(
            chunk_id=build_chunk_id(
                document.source_path, heading_path, chunk_index, chunk_hash
            ),
            chunk_key=build_chunk_key(document.source_path, heading_path, chunk_index),
            doc_id=document.doc_id,
            source_path=document.source_path,
            title=document.title,
            heading_path=heading_path,
            chunk_index=chunk_index,
            content=content,
            chunk_content_hash=chunk_hash,
            document_content_hash=document.content_hash,
            token_count=max(1, len(content) // 4),
            char_count=len(content),
            metadata=metadata,
        )

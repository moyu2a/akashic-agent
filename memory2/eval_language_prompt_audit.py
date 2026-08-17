from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_LANGUAGE_PATTERNS = (
    "English only",
    "Answer in English",
    "Respond in English",
    "Answer concisely in English",
    "用中文回答",
    "中文回答",
    "same language",
    "用户语言",
)

_ANSWER_FORCING_PATTERNS = (
    re.compile(r"\bAnswer\s+(?:concisely\s+)?in\s+English\b", re.I),
    re.compile(r"\bEnglish\s+only\b", re.I),
    re.compile(r"\bRespond\s+in\s+English\b", re.I),
    re.compile(r"用中文回答|中文回答"),
)

_SCAN_SUFFIXES = {".py", ".toml", ".md", ".json", ".jsonl", ".txt"}
_SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    ".planning",
    "docs",
    "my_md",
    "node_modules",
    "private_runtime",
}
_SCAN_ROOTS = (
    "agent",
    "prompts",
    "memory2",
    "scripts",
    "eval/longmemeval",
    "tests",
    "config.example.toml",
)


def audit_language_prompt_sources(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in sorted(_iter_scan_files(root)):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel_path = path.relative_to(root).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            matched = [pattern for pattern in _LANGUAGE_PATTERNS if pattern in line]
            if not matched:
                continue
            classification = _classify_path(rel_path)
            risk = _risk_for_line(line, classification)
            findings.append(
                {
                    "path": rel_path,
                    "line": line_no,
                    "classification": classification,
                    "risk": risk,
                    "patterns": matched,
                    "text": line.strip(),
                }
            )
    return {
        "metrics": _metrics(findings),
        "findings": findings,
    }


def _iter_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for scan_root in _SCAN_ROOTS:
        base = root / scan_root
        if base.is_file():
            candidates = [base]
        elif base.is_dir():
            candidates = list(base.rglob("*"))
        else:
            candidates = []
        for path in candidates:
            if not path.is_file():
                continue
            parts = set(path.relative_to(root).parts)
            if parts & _SKIP_DIRS:
                continue
            if path.suffix not in _SCAN_SUFFIXES:
                continue
            files.append(path)
    return files


def _classify_path(rel_path: str) -> str:
    if rel_path.startswith("eval/longmemeval/"):
        return "legacy_benchmark"
    if rel_path.startswith("tests/") or rel_path.startswith("scripts/run_memory"):
        return "fixture"
    if rel_path in {
        "scripts/run_public_long_memory_eval.py",
        "memory2/eval_public_long_memory.py",
        "memory2/eval_comprehensive_online.py",
        "memory2/eval_answer_contract.py",
    }:
        return "public_p5"
    if rel_path.startswith(("agent/", "prompts/", "config.example.toml")):
        return "production"
    return "other"


def _risk_for_line(line: str, classification: str) -> str:
    if "长期偏好" in line or "用户偏好" in line:
        return "preference_memory_example"
    if not any(pattern.search(line) for pattern in _ANSWER_FORCING_PATTERNS):
        return "same_language_policy"
    if classification in {"legacy_benchmark", "fixture"}:
        return "isolated_answer_language_bias"
    if classification in {"production", "public_p5"}:
        return "hidden_answer_language_bias"
    return "answer_language_bias_review"


def _metrics(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "finding_count": len(findings),
        "production_hidden_answer_language_bias_count": _count(
            findings,
            classification="production",
            risk="hidden_answer_language_bias",
        ),
        "public_p5_hidden_answer_language_bias_count": _count(
            findings,
            classification="public_p5",
            risk="hidden_answer_language_bias",
        ),
        "legacy_benchmark_answer_language_bias_count": _count(
            findings,
            classification="legacy_benchmark",
            risk="isolated_answer_language_bias",
        ),
        "fixture_answer_language_bias_count": _count(
            findings,
            classification="fixture",
            risk="isolated_answer_language_bias",
        ),
    }


def _count(
    findings: list[dict[str, Any]],
    *,
    classification: str,
    risk: str,
) -> int:
    return sum(
        1
        for finding in findings
        if finding["classification"] == classification and finding["risk"] == risk
    )

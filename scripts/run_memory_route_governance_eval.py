from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.memory.engine import MemoryEngineRetrieveRequest, MemoryScope
from memory2.eval_cases import EvalCase, load_eval_cases
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_quantitative_uplift import build_quantitative_uplift_report
from memory2.eval_route_governance import (
    build_route_governance_report,
    write_route_governance_json,
    write_route_governance_markdown,
)
from memory2.retriever import Retriever
from memory2.store import MemoryStore2
from plugins.default_memory.engine import DefaultMemoryEngine


class _StaticEmbedder:
    async def embed(self, _text: str) -> list[float]:
        return [1.0, 0.0]


async def _run_live_smoke(
    *,
    workspace: Path,
    case_root: Path,
) -> list[dict[str, object]]:
    cases = load_eval_cases(case_root)
    results: list[dict[str, object]] = []
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="memory-route-governance-",
        dir=str(workspace),
    ) as temp_dir:
        for case in cases:
            store = MemoryStore2(Path(temp_dir) / f"{case.id}.db", vec_dim=2)
            try:
                _seed_case(store, case)
                engine = _build_engine(store)
                scope = _scope(case)
                result = await engine.retrieve(
                    MemoryEngineRetrieveRequest(
                        query=_query(case),
                        scope=MemoryScope(
                            session_key=scope["session_key"],
                            channel=scope["channel"],
                            chat_id=scope["chat_id"],
                        ),
                        hints={"require_scope_match": True},
                        top_k=8,
                    )
                )
                route_trace = result.raw.get("route_trace", {})
                trace = route_trace if isinstance(route_trace, dict) else {}
                results.append(
                    {
                        "case_id": case.id,
                        "scene": str(trace.get("scene") or "unknown"),
                        "candidate_accept_rate": _float(trace.get("route_hit_rate")),
                        "candidate_drop_rate": _candidate_drop_rate(trace),
                        "graph_used": bool(trace.get("graph_used", False)),
                        "note": f"ok hits={len(result.hits)}",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "case_id": case.id,
                        "scene": "unavailable",
                        "candidate_accept_rate": 0.0,
                        "candidate_drop_rate": 0.0,
                        "graph_used": False,
                        "note": f"unavailable: {type(exc).__name__}",
                    }
                )
            finally:
                store.close()
    return results


def _seed_case(store: MemoryStore2, case: EvalCase) -> None:
    setup = dict(case.setup)
    scope = _scope(case)
    for item in setup.get("memory_items", []):
        if not isinstance(item, dict):
            continue
        extra = dict(item.get("extra_json") or {})
        extra.setdefault("scope_channel", str(item.get("scope_channel") or scope["channel"]))
        extra.setdefault("scope_chat_id", str(item.get("scope_chat_id") or scope["chat_id"]))
        if "active_topics" not in extra:
            extra["active_topics"] = _active_topics(str(item.get("summary") or ""))
        store.upsert_item(
            str(item.get("memory_type") or "event"),
            str(item.get("summary") or ""),
            [1.0, 0.0],
            source_ref=str(item.get("source_ref") or ""),
            extra=extra,
            happened_at=str(item.get("happened_at") or "") or None,
        )


def _build_engine(store: MemoryStore2) -> DefaultMemoryEngine:
    engine = DefaultMemoryEngine.__new__(DefaultMemoryEngine)
    engine._config = SimpleNamespace(model="route-smoke")
    engine._workspace = Path(".")
    engine._provider = None
    engine._light_provider = None
    engine._light_model = ""
    engine._v2_store = store
    engine._embedder = _StaticEmbedder()
    engine._memorizer = None
    engine._retriever = Retriever(store, engine._embedder, top_k=8, score_threshold=0.1)
    engine._tagger = None
    engine._post_response_worker = None
    engine._experiment_runner = None
    engine._event_bus = None
    engine.closeables = [store]
    return engine


def _scope(case: EvalCase) -> dict[str, str]:
    raw = dict(case.setup).get("scope", {})
    scope = raw if isinstance(raw, dict) else {}
    return {
        "session_key": str(scope.get("session_key") or ""),
        "channel": str(scope.get("channel") or ""),
        "chat_id": str(scope.get("chat_id") or ""),
    }


def _query(case: EvalCase) -> str:
    setup = dict(case.setup)
    query = str(setup.get("query") or "").strip()
    if query:
        return query
    conversation = setup.get("conversation", [])
    if not isinstance(conversation, list):
        return ""
    return "\n".join(
        str(message.get("content") or "")
        for message in conversation
        if isinstance(message, dict)
    ).strip()


def _active_topics(summary: str) -> list[str]:
    words = [part for part in summary.replace("，", " ").replace("。", " ").split() if part]
    return words[:4] or [summary[:12]]


def _candidate_drop_rate(trace: dict[str, object]) -> float:
    input_counts = trace.get("input_counts")
    dropped_by_reason = trace.get("dropped_by_reason")
    if not isinstance(input_counts, dict) or not isinstance(dropped_by_reason, dict):
        return 0.0
    total = sum(int(value or 0) for value in input_counts.values())
    dropped = sum(int(value or 0) for value in dropped_by_reason.values())
    return round(dropped / total, 4) if total else 0.0


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="workspace")
    parser.add_argument("--case-root", default="tests/fixtures/memory_eval_cases")
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument(
        "--case-pack",
        choices=("standard", "comprehensive", "answer_comprehensive_v2"),
        default="comprehensive",
    )
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    quantitative_cases = build_quantitative_eval_cases(
        case_set=str(args.case_set),
        limit=int(args.limit),
        case_pack=str(args.case_pack),
    )
    quantitative_report = build_quantitative_uplift_report(quantitative_cases)
    live_results = await _run_live_smoke(
        workspace=Path(args.workspace),
        case_root=Path(args.case_root),
    )
    report = build_route_governance_report(
        quantitative_report=quantitative_report,
        live_route_results=live_results,
    )
    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_route_governance_eval.json"
    md_path = out_dir / "memory_route_governance_eval.md"
    write_route_governance_json(report, json_path)
    write_route_governance_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0


def main() -> int:
    import asyncio

    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())

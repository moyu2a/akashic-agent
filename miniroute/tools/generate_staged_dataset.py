from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from miniroute.routing import (
    IntentDecision,
    operation_for_intent,
)
from miniroute.v1_schema import TrainingRecord, parse_training_record


INTENT_OPERATION_INSTRUCTION = """你是 MnemoAgent 的意图路由分类器，只根据用户请求分类，不要执行请求。

intent 只能是：
chat, memory_query, profile_update, task_plan, content_save, file_read, tool_execution, status_query

operation 只能是：
none, query, update, read, write, execute, plan

request_mode 只能是：
single, compound

只输出 JSON，字段固定为：intent, operation, request_mode。"""

PROPERTY_INSTRUCTION = """你是 MnemoAgent 的路由属性分类器，只根据用户请求和阶段一结果分类，不要执行请求。

need_memory 表示是否需要长期记忆或用户历史。
tool_scope 是粗粒度能力范围，不是具体工具授权，可以同时包含多个工具域。
tool_scope 只能是：
none, memory_tools, content_tools, file_read_tools, file_write_tools, shell_tools, task_tools, observe_tools, unknown_tools

unknown_tools 表示明确需要工具，但无法归入当前已知工具域。
risk_level 只能是：none, read_only, write, high_risk

只输出 JSON，字段固定为：need_memory, tool_scope, risk_level。"""


def _json_row(user_content: str, assistant_payload: dict[str, object]) -> dict[str, object]:
    return {
        "conversations": [
            {"role": "user", "content": user_content},
            {
                "role": "assistant",
                "content": json.dumps(
                    assistant_payload,
                    ensure_ascii=False,
                    separators=(", ", ": "),
                ),
            },
        ]
    }


def _intent_decision(record: TrainingRecord) -> IntentDecision:
    return IntentDecision(
        intent=record.label.intent,
        operation=operation_for_intent(record.label.intent),
        request_mode="compound" if len(record.label.tool_scope) > 1 else "single",
    )


def build_intent_record(record: TrainingRecord) -> dict[str, object]:
    decision = _intent_decision(record)
    return _json_row(
        f"{INTENT_OPERATION_INSTRUCTION}\n\n用户请求：{record.input}",
        decision.to_dict(),
    )


def build_property_record(record: TrainingRecord) -> dict[str, object]:
    decision = _intent_decision(record)
    payload = {
        "need_memory": record.label.need_memory,
        "tool_scope": record.label.tool_scope,
        "risk_level": record.label.risk_level,
    }
    stage_one = json.dumps(decision.to_dict(), ensure_ascii=False, separators=(", ", ": "))
    return _json_row(
        f"{PROPERTY_INSTRUCTION}\n\n"
        f"用户请求：{record.input}\n\n"
        f"阶段一结果：{stage_one}",
        payload,
    )


def _load_records(path: Path) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        parsed = parse_training_record(payload, source=f"{path.name}:{line_no}")
        if not parsed.ok or parsed.record is None:
            raise ValueError(f"{path}:{line_no}: {parsed.errors}")
        records.append(parsed.record)
    return records


def _write_rows(path: Path, rows: Iterable[dict[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_staged_dataset_files(
    source_dir: Path,
    out_dir: Path,
    source_prefix: str = "route_v3_1",
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for split in ("train", "valid", "test"):
        records = _load_records(source_dir / f"{source_prefix}_{split}.jsonl")
        counts[split] = len(records)
        _write_rows(
            out_dir / f"{source_prefix}_intent_{split}.jsonl",
            (build_intent_record(record) for record in records),
        )
        _write_rows(
            out_dir / f"{source_prefix}_property_{split}.jsonl",
            (build_property_record(record) for record in records),
        )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate MiniRoute two-stage SFT JSONL datasets."
    )
    default_data_dir = Path(__file__).resolve().parents[1] / "data"
    parser.add_argument("--source-dir", type=Path, default=default_data_dir)
    parser.add_argument("--out-dir", type=Path, default=default_data_dir)
    parser.add_argument("--source-prefix", default="route_v3_1")
    args = parser.parse_args(argv)

    counts = write_staged_dataset_files(
        args.source_dir,
        args.out_dir,
        args.source_prefix,
    )
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

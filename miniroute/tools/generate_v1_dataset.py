from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from miniroute.v1_schema import (
    DEFAULT_INSTRUCTION,
    INTENTS,
    RISK_LEVELS,
    TOOL_SCOPES,
    RouteLabel,
    TrainingRecord,
)


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    train: list[TrainingRecord]
    valid: list[TrainingRecord]
    test: list[TrainingRecord]


def _make_records_for_intent(
    intent: str,
    *,
    count: int,
    risk_level: str,
    need_memory: bool,
    need_tools: bool,
    tool_scope: list[str],
    templates: list[str],
) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    for index in range(count):
        template = templates[index % len(templates)]
        slot = index // len(templates)
        text = template.format(n=index + 1, slot=slot + 1)
        records.append(
            TrainingRecord(
                instruction=DEFAULT_INSTRUCTION,
                input=text,
                label=RouteLabel(
                    intent=intent,
                    need_memory=need_memory,
                    need_tools=need_tools,
                    tool_scope=list(tool_scope),
                    risk_level=risk_level,
                ),
                source=f"template:{intent}",
            )
        )
    return records


def build_v1_records() -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    records.extend(
        _make_records_for_intent(
            "chat",
            count=150,
            risk_level="none",
            need_memory=False,
            need_tools=False,
            tool_scope=["none"],
            templates=[
                "帮我解释一下这个概念，第{n}版。",
                "你觉得这个项目怎么介绍更好？第{n}种说法。",
                "把这段话改得更自然一点，版本 {n}。",
                "如果只用一句话，怎么回答这件事？第{n}条。",
                "我只是想听你分析一下，不需要工具。第{n}轮。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "memory_query",
            count=150,
            risk_level="read_only",
            need_memory=True,
            need_tools=False,
            tool_scope=["memory_tools"],
            templates=[
                "你还记得我上次说的回答偏好吗？第{n}次。",
                "之前我提过的那个项目方向是什么？第{n}条。",
                "你能回忆一下我喜欢的回复风格吗？第{n}个问法。",
                "我前面说过的长期目标是什么？第{n}版。",
                "把我之前提到的重点再总结一下，第{n}条。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "profile_update",
            count=150,
            risk_level="write",
            need_memory=True,
            need_tools=False,
            tool_scope=["memory_tools"],
            templates=[
                "以后回答我尽量简洁一点，第{n}次提醒。",
                "请把我的偏好记成先给结论，第{n}条。",
                "我希望你后面都用条目式回答，第{n}次。",
                "记住我不喜欢太多英文，第{n}版。",
                "我更偏好工作模式的语气，第{n}条。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "task_plan",
            count=150,
            risk_level="write",
            need_memory=False,
            need_tools=True,
            tool_scope=["task_tools"],
            templates=[
                "帮我把这个功能拆成三个步骤，第{n}版。",
                "请给我一个执行计划，第{n}条。",
                "我想安排一下接下来的任务，第{n}次。",
                "把这个需求整理成里程碑，第{n}轮。",
                "帮我列一个待办清单，第{n}条。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "content_save",
            count=150,
            risk_level="write",
            need_memory=False,
            need_tools=True,
            tool_scope=["content_tools"],
            templates=[
                "帮我保存这个 B 站视频，第{n}条。",
                "把这个链接记下来，晚点我再看，第{n}版。",
                "请收藏这篇文章，第{n}次。",
                "把这条资料加到收藏里，第{n}轮。",
                "帮我记录这个内容来源，第{n}条。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "file_read",
            count=150,
            risk_level="read_only",
            need_memory=False,
            need_tools=True,
            tool_scope=["file_read_tools"],
            templates=[
                "帮我看看 README 里写了什么，第{n}版。",
                "读取这个文件并总结一下，第{n}条。",
                "给我解释一下这个目录里的内容，第{n}次。",
                "请查看这个配置文件，第{n}轮。",
                "把这个文档的重点提炼出来，第{n}条。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "tool_execution",
            count=200,
            risk_level="high_risk",
            need_memory=False,
            need_tools=True,
            tool_scope=["shell_tools"],
            templates=[
                "帮我删除这个目录，第{n}条。",
                "执行这个命令，第{n}次。",
                "把这个文件覆盖掉，第{n}版。",
                "请安装这个软件，第{n}轮。",
                "清空这个目录里的内容，第{n}条。",
                "用 shell 去处理这个路径，第{n}版。",
            ],
        )
    )
    records.extend(
        _make_records_for_intent(
            "status_query",
            count=150,
            risk_level="read_only",
            need_memory=False,
            need_tools=True,
            tool_scope=["observe_tools"],
            templates=[
                "刚才用了哪些工具？第{n}条。",
                "帮我看一下当前运行状态，第{n}版。",
                "现在的会话记录是什么？第{n}次。",
                "检查一下最近的任务结果，第{n}轮。",
                "查看一下 trace 里有什么信息，第{n}条。",
            ],
        )
    )
    return records


def split_v1_records(records: Iterable[TrainingRecord]) -> DatasetSplits:
    buckets = {"train": [], "valid": [], "test": []}
    by_intent: dict[str, list[TrainingRecord]] = {intent: [] for intent in INTENTS}
    for record in records:
        by_intent[record.label.intent].append(record)

    for intent in INTENTS:
        items = by_intent[intent]
        train_count = int(len(items) * 0.70)
        valid_count = int(len(items) * 0.15)
        test_count = len(items) - train_count - valid_count
        buckets["train"].extend(items[:train_count])
        buckets["valid"].extend(items[train_count : train_count + valid_count])
        buckets["test"].extend(items[train_count + valid_count : train_count + valid_count + test_count])

    return DatasetSplits(
        train=buckets["train"],
        valid=buckets["valid"],
        test=buckets["test"],
    )


def write_jsonl(path: Path, records: Iterable[TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v1_dataset_files(out_dir: Path) -> DatasetSplits:
    records = build_v1_records()
    splits = split_v1_records(records)
    write_jsonl(out_dir / "route_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_test.jsonl", splits.test)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V1 JSONL data.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
        help="Directory for route_train.jsonl, route_valid.jsonl, route_test.jsonl.",
    )
    args = parser.parse_args(argv)
    splits = write_v1_dataset_files(args.out_dir)
    summary = {
        "train": len(splits.train),
        "valid": len(splits.valid),
        "test": len(splits.test),
        "total": len(splits.train) + len(splits.valid) + len(splits.test),
        "out_dir": str(args.out_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

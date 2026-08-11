from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Iterable

from miniroute.v1_schema import ROUTE_PROMPT_V2, RouteLabel, TrainingRecord

SHUFFLE_SEED = 20260805


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    train: list[TrainingRecord]
    valid: list[TrainingRecord]
    test: list[TrainingRecord]


def _record(
    text: str,
    *,
    intent: str,
    need_memory: bool,
    need_tools: bool,
    tool_scope: list[str],
    risk_level: str,
    source: str,
) -> TrainingRecord:
    return TrainingRecord(
        instruction=ROUTE_PROMPT_V2,
        input=text,
        label=RouteLabel(
            intent=intent,
            need_memory=need_memory,
            need_tools=need_tools,
            tool_scope=tool_scope,
            risk_level=risk_level,
        ),
        source=source,
    )


def _expand(base: list[str], count: int) -> list[str]:
    out: list[str] = []
    for index in range(count):
        text = base[index % len(base)]
        out.append(text.format(n=index + 1))
    return out


def _records_from_texts(
    texts: list[str],
    *,
    intent: str,
    need_memory: bool,
    need_tools: bool,
    tool_scope: list[str],
    risk_level: str,
    source: str,
) -> list[TrainingRecord]:
    return [
        _record(
            text,
            intent=intent,
            need_memory=need_memory,
            need_tools=need_tools,
            tool_scope=tool_scope,
            risk_level=risk_level,
            source=source,
        )
        for text in texts
    ]


def build_v2_records() -> list[TrainingRecord]:
    records: list[TrainingRecord] = []

    records += _records_from_texts(
        _expand(
            [
                "解释一下工具调用的原理。",
                "保存机制是什么意思？",
                "帮我记一下这个概念是什么意思。",
                "你觉得这种表达偏好吗？",
                "总结一下这个观点的优缺点。",
                "说明一下 rm 命令会做什么，不要执行。",
                "这个项目应该怎么介绍更清楚？",
                "帮我把这段话改得自然一点。",
                "我只是想让你分析，不需要查文件。",
                "这里的记忆治理概念怎么理解？",
            ],
            220,
        ),
        intent="chat",
        need_memory=False,
        need_tools=False,
        tool_scope=["none"],
        risk_level="none",
        source="v2:chat_hard_negative",
    )

    records += _records_from_texts(
        _expand(
            [
                "你还记得我喜欢什么回答风格吗？",
                "我之前说过的项目重点是什么？",
                "上次我提到的回答偏好是什么？",
                "帮我回忆一下我关注哪些技术方向。",
                "之前那个长期目标你还记得吗？",
                "我以前说过不喜欢什么表达方式？",
                "按我之前说过的偏好，这里应该怎么写？",
                "你能查一下我历史里提到的学习重点吗？",
            ],
            180,
        ),
        intent="memory_query",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="read_only",
        source="v2:memory_query",
    )

    records += _records_from_texts(
        _expand(
            [
                "请记住我以后喜欢简洁回答。",
                "以后默认先给结论再解释。",
                "把我的偏好更新成少用英文。",
                "记住我更喜欢条目式输出。",
                "以后和我讨论项目时使用工作模式。",
                "请把这个作为我的长期偏好保存。",
                "我之后希望你回答时不要加太多背景铺垫。",
                "把我的用户画像补充为偏好直接、清晰的表达。",
            ],
            180,
        ),
        intent="profile_update",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="write",
        source="v2:profile_update",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我把这个功能拆成几个步骤。",
                "给我制定一个实现计划。",
                "把接下来的工作排一下优先级。",
                "帮我整理一个任务清单。",
                "把这个需求拆成可执行阶段。",
                "为 MiniRoute V2 写一个迭代计划。",
                "安排一下明天要完成的训练准备工作。",
            ],
            160,
        ),
        intent="task_plan",
        need_memory=False,
        need_tools=True,
        tool_scope=["task_tools"],
        risk_level="write",
        source="v2:task_plan",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我保存这个 B 站视频。",
                "把这个链接加入收藏。",
                "记录一下这篇文章，晚点回顾。",
                "请收藏这条资料。",
                "保存这个内容来源和备注。",
                "把这个视频放到 AI 工具标签里。",
                "这个链接对项目有用，帮我记到内容库。",
            ],
            160,
        ),
        intent="content_save",
        need_memory=False,
        need_tools=True,
        tool_scope=["content_tools"],
        risk_level="write",
        source="v2:content_save",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我看看 README 里写了什么。",
                "读取这个配置文件并总结。",
                "列一下这个目录里的主要文件。",
                "查看这份文档的重点。",
                "帮我分析这个日志文件。",
                "看一下这个测试文件覆盖了什么。",
                "请打开这个 markdown 看看结构。",
            ],
            180,
        ),
        intent="file_read",
        need_memory=False,
        need_tools=True,
        tool_scope=["file_read_tools"],
        risk_level="read_only",
        source="v2:file_read",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我删除这个目录。",
                "覆盖这个配置文件。",
                "执行 rm 命令。",
                "安装这个软件包。",
                "清空这个目录里的内容。",
                "运行这条 shell 命令。",
                "把这个文件移动到系统目录。",
                "用命令行修改这个路径下的文件。",
                "删除旧的训练输出。",
                "执行 sudo apt install。",
            ],
            220,
        ),
        intent="tool_execution",
        need_memory=False,
        need_tools=True,
        tool_scope=["shell_tools"],
        risk_level="high_risk",
        source="v2:tool_execution_high_risk",
    )

    records += _records_from_texts(
        _expand(
            [
                "刚才用了哪些工具？",
                "查看上一轮工具调用链。",
                "帮我看一下当前运行状态。",
                "查询最近的 trace。",
                "看一下上次模型调用消耗了多少 token。",
                "检查最近的记忆召回记录。",
                "刚才为什么调用了文件工具？",
            ],
            150,
        ),
        intent="status_query",
        need_memory=False,
        need_tools=True,
        tool_scope=["observe_tools"],
        risk_level="read_only",
        source="v2:status_query",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我把这段音频转成文字。",
                "把这张图片里的文字识别出来。",
                "帮我生成一张流程图图片。",
                "连接数据库查一下这个表。",
                "把这个网页当前状态检查一下。",
                "调用 OCR 看看截图里有什么。",
                "把这段视频提取成字幕。",
            ],
            70,
        ),
        intent="tool_execution",
        need_memory=False,
        need_tools=True,
        tool_scope=["unknown_tools"],
        risk_level="read_only",
        source="v2:unknown_tools",
    )

    return records


def split_v2_records(records: Iterable[TrainingRecord]) -> DatasetSplits:
    by_intent: dict[str, list[TrainingRecord]] = {}
    for record in records:
        by_intent.setdefault(record.label.intent, []).append(record)

    train: list[TrainingRecord] = []
    valid: list[TrainingRecord] = []
    test: list[TrainingRecord] = []
    for intent in sorted(by_intent):
        items = list(by_intent[intent])
        rng = random.Random(f"{SHUFFLE_SEED}:{intent}")
        rng.shuffle(items)
        train_count = int(len(items) * 0.70)
        valid_count = int(len(items) * 0.15)
        train.extend(items[:train_count])
        valid.extend(items[train_count : train_count + valid_count])
        test.extend(items[train_count + valid_count :])

    random.Random(f"{SHUFFLE_SEED}:train").shuffle(train)
    random.Random(f"{SHUFFLE_SEED}:valid").shuffle(valid)
    random.Random(f"{SHUFFLE_SEED}:test").shuffle(test)
    return DatasetSplits(train=train, valid=valid, test=test)


def write_jsonl(path: Path, records: Iterable[TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v2_dataset_files(out_dir: Path) -> DatasetSplits:
    splits = split_v2_records(build_v2_records())
    write_jsonl(out_dir / "route_v2_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_v2_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_v2_test.jsonl", splits.test)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V2 JSONL data.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args(argv)
    splits = write_v2_dataset_files(args.out_dir)
    summary = {
        "train": len(splits.train),
        "valid": len(splits.valid),
        "test": len(splits.test),
        "total": len(splits.train) + len(splits.valid) + len(splits.test),
        "shuffle_seed": SHUFFLE_SEED,
        "out_dir": str(args.out_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

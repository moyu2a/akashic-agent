from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Iterable

from miniroute.tools.generate_v2_dataset import build_v2_records
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


def build_v3_records() -> list[TrainingRecord]:
    records = list(build_v2_records())

    records += _records_from_texts(
        _expand(
            [
                "查看刚才的工具调用记录，不要执行任何命令。",
                "帮我看一下上一轮 trace 里调用了哪些工具。",
                "查询最近一次模型调用用了多少 token。",
                "检查当前会话状态，不需要运行 shell。",
                "看一下最近有没有工具被拒绝执行。",
                "查看后台任务运行状态，只读查询即可。",
                "帮我确认刚才为什么没有调用记忆工具。",
                "列出上一轮工具链路和风险判断结果。",
            ],
            120,
        ),
        intent="status_query",
        need_memory=False,
        need_tools=True,
        tool_scope=["observe_tools"],
        risk_level="read_only",
        source="v3:status_query_vs_tool_execution",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我读取 README 并总结，不要执行命令。",
                "看一下这个日志文件里有什么异常。",
                "查看配置文件内容并解释字段含义。",
                "列一下目录结构，只需要读取文件信息。",
                "打开这个 markdown 看看标题层级。",
                "分析测试文件覆盖了哪些场景，不要修改文件。",
                "读取这份训练记录，帮我总结结论。",
                "看一下这个 JSONL 文件前几条数据格式。",
            ],
            120,
        ),
        intent="file_read",
        need_memory=False,
        need_tools=True,
        tool_scope=["file_read_tools"],
        risk_level="read_only",
        source="v3:file_read_vs_tool_execution",
    )

    records += _records_from_texts(
        _expand(
            [
                "把这个链接保存到内容库，不要执行 shell。",
                "收藏这篇文章，标记为后续阅读。",
                "保存这个 B 站视频并加上 AI 标签。",
                "把这条资料记录到内容列表里。",
                "帮我存一下这个网页地址和备注。",
                "这个视频对项目有用，加入收藏即可。",
                "把这篇博客保存起来，晚点复盘。",
                "记录这个资料来源，不需要读本地文件。",
            ],
            110,
        ),
        intent="content_save",
        need_memory=False,
        need_tools=True,
        tool_scope=["content_tools"],
        risk_level="write",
        source="v3:content_save_vs_tool_execution",
    )

    records += _records_from_texts(
        _expand(
            [
                "解释一下长期记忆和短期上下文的区别。",
                "保存机制这个概念是什么意思？",
                "说明一下 rm 命令的风险，不要执行。",
                "什么叫用户画像？这里只是问概念。",
                "帮我分析一下工具治理为什么重要。",
                "偏好学习在个人 AI 里有什么作用？",
                "记忆召回失败通常有哪些原因？",
                "解释一下 trace，不需要查看真实记录。",
            ],
            140,
        ),
        intent="chat",
        need_memory=False,
        need_tools=False,
        tool_scope=["none"],
        risk_level="none",
        source="v3:chat_memory_profile_hard_negative",
    )

    records += _records_from_texts(
        _expand(
            [
                "以后回答我先给结论，再给原因。",
                "记住我不喜欢太多英文缩写。",
                "把我的偏好改成回答更短一点。",
                "以后讨论简历时多写数据结果。",
                "请把我的长期偏好更新为少用口号。",
                "之后讲技术方案时先说取舍。",
            ],
            90,
        ),
        intent="profile_update",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="write",
        source="v3:profile_memory_content_boundary",
    )
    records += _records_from_texts(
        _expand(
            [
                "我之前说过喜欢什么回答风格？",
                "查一下我上次提到的项目重点。",
                "回忆一下我之前不喜欢哪种表达。",
                "根据我过去的偏好，这段话应该怎么改？",
                "我以前让你记住的简历重点是什么？",
                "看一下历史记忆里我的学习方向。",
            ],
            90,
        ),
        intent="memory_query",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="read_only",
        source="v3:profile_memory_content_boundary",
    )
    records += _records_from_texts(
        _expand(
            [
                "保存这个链接，不是更新我的个人偏好。",
                "把这篇文章加入收藏，不是记到用户画像。",
                "记录这个视频地址，晚点看。",
                "收藏这份资料，不需要查询我的历史记忆。",
                "把这个网页保存到内容库。",
                "存一下这个 GitHub 项目链接。",
            ],
            90,
        ),
        intent="content_save",
        need_memory=False,
        need_tools=True,
        tool_scope=["content_tools"],
        risk_level="write",
        source="v3:profile_memory_content_boundary",
    )

    records += _records_from_texts(
        _expand(
            [
                "帮我识别截图里的文字。",
                "把这段音频转写成文本。",
                "检查这张图片里有没有表格。",
                "连接数据库查询这张业务表。",
                "把视频里的字幕提取出来。",
                "调用 OCR 看一下图片内容。",
                "分析上传图片中的错误提示。",
                "把语音消息转成文字摘要。",
            ],
            100,
        ),
        intent="tool_execution",
        need_memory=False,
        need_tools=True,
        tool_scope=["unknown_tools"],
        risk_level="read_only",
        source="v3:unknown_tools_vs_shell_tools",
    )

    return records


def split_v3_records(records: Iterable[TrainingRecord]) -> DatasetSplits:
    by_intent: dict[str, list[TrainingRecord]] = {}
    for record in records:
        by_intent.setdefault(record.label.intent, []).append(record)

    train: list[TrainingRecord] = []
    valid: list[TrainingRecord] = []
    test: list[TrainingRecord] = []
    for intent in sorted(by_intent):
        items = list(by_intent[intent])
        rng = random.Random(f"{SHUFFLE_SEED}:v3:{intent}")
        rng.shuffle(items)
        train_count = int(len(items) * 0.70)
        valid_count = int(len(items) * 0.15)
        train.extend(items[:train_count])
        valid.extend(items[train_count : train_count + valid_count])
        test.extend(items[train_count + valid_count :])

    random.Random(f"{SHUFFLE_SEED}:v3:train").shuffle(train)
    random.Random(f"{SHUFFLE_SEED}:v3:valid").shuffle(valid)
    random.Random(f"{SHUFFLE_SEED}:v3:test").shuffle(test)
    return DatasetSplits(train=train, valid=valid, test=test)


def write_jsonl(path: Path, records: Iterable[TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v3_dataset_files(out_dir: Path) -> DatasetSplits:
    splits = split_v3_records(build_v3_records())
    write_jsonl(out_dir / "route_v3_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_v3_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_v3_test.jsonl", splits.test)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V3 JSONL data.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args(argv)
    splits = write_v3_dataset_files(args.out_dir)
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

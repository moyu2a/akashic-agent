from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Iterable, Mapping

from miniroute.v1_schema import (
    ROUTE_PROMPT_V2,
    RouteLabel,
    TrainingRecord,
    parse_training_record,
)

SHUFFLE_SEED = 20260805
MAX_DELTA_RECORDS = 360
MAX_SOURCE_RECORDS = 80


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


def _dedupe_records(records: list[TrainingRecord]) -> list[TrainingRecord]:
    seen: set[str] = set()
    out: list[TrainingRecord] = []
    for record in records:
        if record.input in seen:
            raise ValueError(f"duplicate V3.1 delta input: {record.input}")
        seen.add(record.input)
        out.append(record)
    return out


def build_v3_1_delta_records() -> list[TrainingRecord]:
    records: list[TrainingRecord] = []

    records += _records_from_texts(
        [
            "查询最近的 trace，不要把 trace 当成 intent。",
            "查看上一轮 trace。",
            "看一下 trace 里记录了哪些工具。",
            "帮我分析最近一次 trace，不要执行工具。",
            "查询 trace 不是新的 intent，属于状态查询。",
            "trace 只是运行记录，不是 intent 标签。",
            "查看 trace 中的模型调用轮次。",
            "列出最近 trace 里的 token 消耗。",
            "检查 trace 里有没有工具被拒绝。",
            "看一下当前会话 trace 的状态。",
            "查询最近一次运行记录 trace。",
            "分析 trace 日志中的工具选择原因。",
        ],
        intent="status_query",
        need_memory=False,
        need_tools=True,
        tool_scope=["observe_tools"],
        risk_level="read_only",
        source="v3_1:trace_status_query_schema_fix",
    )

    records += _records_from_texts(
        [
            "把接下来的工作排一下优先级。",
            "帮我拆一下这个需求。",
            "给我列一个实现步骤。",
            "安排一下下一轮训练计划。",
            "把 V3.1 的工作拆成阶段。",
            "制定一个小修数据的执行计划。",
            "把测试、训练、复盘分成几个任务。",
            "规划一下明天先做哪些实验。",
            "解释一下任务拆分是什么意思。",
            "这个计划写得是否清楚？",
            "帮我分析这个方案是否合理。",
            "什么叫按优先级排序？",
            "这里只是解释计划概念，不要创建任务。",
            "分析任务规划和普通聊天的区别。",
            "以后帮我排计划时先给优先级。",
            "以后讨论任务时先列步骤。",
            "记住我喜欢按阶段拆任务。",
            "以后做计划时先给风险再给步骤。",
            "以后安排工作时先列最关键的三件事。",
            "记住我喜欢任务计划里带验收标准。",
        ],
        intent="task_plan",
        need_memory=False,
        need_tools=True,
        tool_scope=["task_tools"],
        risk_level="write",
        source="v3_1:task_plan_chat_profile_boundary",
    )
    # Correct the labels for the chat/profile contrast rows in the same source.
    records[-12:-6] = _records_from_texts(
        [record.input for record in records[-12:-6]],
        intent="chat",
        need_memory=False,
        need_tools=False,
        tool_scope=["none"],
        risk_level="none",
        source="v3_1:task_plan_chat_profile_boundary",
    )
    records[-6:] = _records_from_texts(
        [record.input for record in records[-6:]],
        intent="profile_update",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="write",
        source="v3_1:task_plan_chat_profile_boundary",
    )

    records += _records_from_texts(
        [
            "记住我更喜欢条目式输出。",
            "以后默认先给结论。",
            "把我的偏好改成回答更短一点。",
            "之后讲技术方案时先说取舍。",
            "以后写简历内容时多保留测试数据。",
            "请把我的长期偏好改为少用口号。",
            "我之前说过喜欢什么输出方式？",
            "查一下我上次提到的回答偏好。",
            "我以前让你记住什么简历重点？",
            "看一下历史记忆里我的学习方向。",
            "回忆一下我之前说过的项目命名偏好。",
            "根据过去记忆，我更喜欢哪种回答方式？",
            "保存这个链接，不是更新我的个人偏好。",
            "把这篇文章加入收藏，不是记到用户画像。",
            "记录这个视频地址，晚点看。",
            "把这个网页保存到内容库。",
            "收藏这份资料，不需要查询我的历史记忆。",
            "存一下这个 GitHub 项目链接。",
        ],
        intent="profile_update",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="write",
        source="v3_1:profile_memory_content_boundary",
    )
    records[-12:-6] = _records_from_texts(
        [record.input for record in records[-12:-6]],
        intent="memory_query",
        need_memory=True,
        need_tools=True,
        tool_scope=["memory_tools"],
        risk_level="read_only",
        source="v3_1:profile_memory_content_boundary",
    )
    records[-6:] = _records_from_texts(
        [record.input for record in records[-6:]],
        intent="content_save",
        need_memory=False,
        need_tools=True,
        tool_scope=["content_tools"],
        risk_level="write",
        source="v3_1:profile_memory_content_boundary",
    )

    records += _records_from_texts(
        [
            "打开 README 看看结构。",
            "查看这个 markdown 的标题。",
            "读取日志并总结异常。",
            "帮我看看配置文件写了什么，不要修改。",
            "只读查看这个 JSONL 的前几行。",
            "分析测试文件覆盖了什么场景。",
            "覆盖这个配置文件，这是高风险执行。",
            "删除这个目录，这是不可逆操作。",
            "运行这条 shell 命令。",
            "安装这个软件包。",
            "把文件移动到系统目录。",
            "清空旧的训练输出目录。",
        ],
        intent="file_read",
        need_memory=False,
        need_tools=True,
        tool_scope=["file_read_tools"],
        risk_level="read_only",
        source="v3_1:file_read_tool_execution_boundary",
    )
    records[-6:] = _records_from_texts(
        [record.input for record in records[-6:]],
        intent="tool_execution",
        need_memory=False,
        need_tools=True,
        tool_scope=["shell_tools"],
        risk_level="high_risk",
        source="v3_1:file_read_tool_execution_boundary",
    )

    records += _records_from_texts(
        [
            "识别图片文字不是读取本地 markdown。",
            "音频转写不是保存内容。",
            "视频字幕提取不是内容收藏。",
            "图片表格识别不是文件读取。",
            "OCR 是未知工具域，不是 shell。",
            "把语音消息转成文字摘要。",
            "检查截图里有没有错误提示。",
            "识别上传图片里的表格内容。",
            "从视频里抽取字幕文本。",
            "把这段音频转写成会议纪要。",
            "保存这个 OCR 结果链接到内容库。",
            "把这篇图片识别教程加入收藏。",
        ],
        intent="tool_execution",
        need_memory=False,
        need_tools=True,
        tool_scope=["unknown_tools"],
        risk_level="read_only",
        source="v3_1:unknown_tools_boundary",
    )
    records[-2:] = _records_from_texts(
        [record.input for record in records[-2:]],
        intent="content_save",
        need_memory=False,
        need_tools=True,
        tool_scope=["content_tools"],
        risk_level="write",
        source="v3_1:unknown_tools_boundary",
    )

    records = _dedupe_records(records)
    if len(records) > MAX_DELTA_RECORDS:
        raise ValueError(f"too many V3.1 delta records: {len(records)}")
    source_counts = _source_counts(records)
    too_large = {
        source: count
        for source, count in source_counts.items()
        if count > MAX_SOURCE_RECORDS
    }
    if too_large:
        raise ValueError(f"V3.1 source counts exceed cap: {too_large}")
    return records


def _source_counts(records: Iterable[TrainingRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.source] = counts.get(record.source, 0) + 1
    return dict(sorted(counts.items()))


def _read_jsonl_records(path: Path, *, split_name: str) -> list[TrainingRecord]:
    rows: list[TrainingRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        parsed = parse_training_record(payload, source=f"{split_name}:{line_no}")
        if not parsed.ok or parsed.record is None:
            raise ValueError(f"{path}:{line_no}: {parsed.errors}")
        rows.append(parsed.record)
    return rows


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _load_frozen_v3_splits(data_dir: Path) -> DatasetSplits:
    return DatasetSplits(
        train=_read_jsonl_records(data_dir / "route_v3_train.jsonl", split_name="train"),
        valid=_read_jsonl_records(data_dir / "route_v3_valid.jsonl", split_name="valid"),
        test=_read_jsonl_records(data_dir / "route_v3_test.jsonl", split_name="test"),
    )


def split_v3_1_records(records: Iterable[TrainingRecord]) -> DatasetSplits:
    by_intent: dict[str, list[TrainingRecord]] = {}
    for record in records:
        by_intent.setdefault(record.label.intent, []).append(record)

    train: list[TrainingRecord] = []
    valid: list[TrainingRecord] = []
    test: list[TrainingRecord] = []
    for intent in sorted(by_intent):
        items = list(by_intent[intent])
        rng = random.Random(f"{SHUFFLE_SEED}:v3_1_delta:{intent}")
        rng.shuffle(items)
        train_count = int(len(items) * 0.70)
        valid_count = int(len(items) * 0.15)
        train.extend(items[:train_count])
        valid.extend(items[train_count : train_count + valid_count])
        test.extend(items[train_count + valid_count :])

    random.Random(f"{SHUFFLE_SEED}:v3_1_delta:train").shuffle(train)
    random.Random(f"{SHUFFLE_SEED}:v3_1_delta:valid").shuffle(valid)
    random.Random(f"{SHUFFLE_SEED}:v3_1_delta:test").shuffle(test)
    return DatasetSplits(train=train, valid=valid, test=test)


def build_v3_1_records(data_dir: Path | None = None) -> list[TrainingRecord]:
    base_dir = data_dir or _default_data_dir()
    frozen = _load_frozen_v3_splits(base_dir)
    delta = split_v3_1_records(build_v3_1_delta_records())
    return (
        list(frozen.train)
        + list(delta.train)
        + list(frozen.valid)
        + list(delta.valid)
        + list(frozen.test)
        + list(delta.test)
    )


def write_jsonl(path: Path, records: Iterable[TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v3_1_dataset_files(
    out_dir: Path, *, frozen_data_dir: Path | None = None
) -> DatasetSplits:
    base_dir = frozen_data_dir or _default_data_dir()
    frozen = _load_frozen_v3_splits(base_dir)
    delta = split_v3_1_records(build_v3_1_delta_records())
    splits = DatasetSplits(
        train=list(frozen.train) + list(delta.train),
        valid=list(frozen.valid) + list(delta.valid),
        test=list(frozen.test) + list(delta.test),
    )
    write_jsonl(out_dir / "route_v3_1_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_v3_1_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_v3_1_test.jsonl", splits.test)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V3.1 JSONL data.")
    parser.add_argument("--out-dir", type=Path, default=_default_data_dir())
    args = parser.parse_args(argv)

    delta = build_v3_1_delta_records()
    delta_splits = split_v3_1_records(delta)
    splits = write_v3_1_dataset_files(args.out_dir)
    summary: Mapping[str, object] = {
        "train": len(splits.train),
        "valid": len(splits.valid),
        "test": len(splits.test),
        "total": len(splits.train) + len(splits.valid) + len(splits.test),
        "delta_train": len(delta_splits.train),
        "delta_valid": len(delta_splits.valid),
        "delta_test": len(delta_splits.test),
        "delta_total": len(delta),
        "delta_source_counts": _source_counts(delta),
        "shuffle_seed": SHUFFLE_SEED,
        "out_dir": str(args.out_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

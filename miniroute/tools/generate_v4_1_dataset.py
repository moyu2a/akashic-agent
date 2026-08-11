from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Iterable

from miniroute.v4_schema import V4RouteLabel, V4TrainingRecord

SHUFFLE_SEED = 20260806
SPLITS = ("train", "valid", "test")
SCENES = (
    "chat",
    "memory",
    "profile",
    "task",
    "file",
    "status",
    "content",
    "action",
    "unknown",
)
SCENE_OPERATIONS = {
    "chat": "answer",
    "memory": "query",
    "profile": "update",
    "task": "plan",
    "file": "read",
    "status": "query",
    "content": "save",
    "action": "execute",
    "unknown": "unknown",
}
SPLIT_SCENE_COUNTS: dict[str, dict[str, int]] = {
    "train": {
        "chat": 360,
        "memory": 288,
        "profile": 240,
        "task": 312,
        "file": 288,
        "status": 240,
        "content": 240,
        "action": 288,
        "unknown": 144,
    },
    "valid": {
        "chat": 45,
        "memory": 36,
        "profile": 30,
        "task": 39,
        "file": 36,
        "status": 30,
        "content": 30,
        "action": 36,
        "unknown": 18,
    },
    "test": {
        "chat": 45,
        "memory": 36,
        "profile": 30,
        "task": 39,
        "file": 36,
        "status": 30,
        "content": 30,
        "action": 36,
        "unknown": 18,
    },
}
COMPOUND_COUNTS = {"train": 480, "valid": 60, "test": 60}
COMPOUND_MARKERS = ("并", "然后", "同时", "再", "和")

BOUNDARY_RECORDS: tuple[tuple[str, str, str, str], ...] = (
    ("看一下运行记录，不要查询我的长期记忆。", "status", "query", "single"),
    ("保存这个网页，不是执行下载命令。", "content", "save", "single"),
    ("下载并保存这个网页正文。", "action", "execute", "single"),
    ("我之前说过哪些项目数据？", "memory", "query", "single"),
    ("按刚才那个来。", "unknown", "unknown", "single"),
)


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    train: list[V4TrainingRecord]
    valid: list[V4TrainingRecord]
    test: list[V4TrainingRecord]


@dataclass(frozen=True, slots=True)
class TemplateSpec:
    family: str
    text: str


def _single_templates(split: str, scene: str) -> list[TemplateSpec]:
    templates: dict[str, dict[str, list[tuple[str, str]]]] = {
        "train": {
            "chat": [
                ("train_chat_explain", "帮我解释一下这个概念，第{n}版。"),
                ("train_chat_resume", "这段项目描述怎么写更清楚，第{n}版？"),
                ("train_chat_reason", "分析一下这个方案是否合理，第{n}轮。"),
                ("train_chat_no_file", "我只是想讨论思路，不需要查文件，第{n}次。"),
            ],
            "memory": [
                ("train_memory_preference", "你还记得我之前说过的回答偏好吗，第{n}次？"),
                ("train_memory_miniroute", "我上次提到 MiniRoute 的重点是什么，第{n}轮？"),
                ("train_memory_history", "查一下我以前说过的训练计划，第{n}版。"),
            ],
            "profile": [
                ("train_profile_conclusion", "以后回答我先给结论，第{n}条。"),
                ("train_profile_no_english", "记住我不喜欢太多英文缩写，第{n}条。"),
                ("train_profile_resume_data", "之后写简历时多保留测试数据，第{n}条。"),
            ],
            "task": [
                ("train_task_stage", "帮我把 MiniRoute V4 拆成几个阶段，第{n}版。"),
                ("train_task_plan_eval", "制定一个训练和评测计划，第{n}版。"),
                ("train_task_next", "下一步该做什么，第{n}轮？"),
                ("train_task_progress", "当前任务进展到哪里了，第{n}轮？"),
            ],
            "file": [
                ("train_file_readme", "读取 README 看看当前项目进展，第{n}轮。"),
                ("train_file_eval", "帮我看一下 eval_route.py 有没有问题，第{n}轮。"),
                ("train_file_docs", "总结 miniroute 下的文档，第{n}版。"),
            ],
            "status": [
                ("train_status_tools", "刚才用了哪些工具，第{n}次？"),
                ("train_status_result", "当前测试结果是多少，第{n}轮？"),
                ("train_status_trace", "查看最近一次 trace，第{n}次。"),
            ],
            "content": [
                ("train_content_link", "帮我保存这个链接，第{n}条。"),
                ("train_content_article", "收藏这篇文章，标记为后续阅读，第{n}条。"),
                ("train_content_video", "把这个视频记录到资料库，第{n}条。"),
            ],
            "action": [
                ("train_action_command", "执行这个命令，第{n}次。"),
                ("train_action_delete", "删除这个目录，第{n}次。"),
                ("train_action_modify", "帮我修改这个文件，第{n}轮。"),
                ("train_action_install", "安装这些依赖，第{n}次。"),
            ],
            "unknown": [
                ("train_unknown_handle", "处理一下这个东西，第{n}次。"),
                ("train_unknown_do", "帮我弄一下，第{n}轮。"),
                ("train_unknown_method", "这个要怎么搞，第{n}次？"),
            ],
        },
        "valid": {
            "chat": [
                ("valid_chat_clarity", "帮我判断这句话是否清楚，验证样本{n}。"),
                ("valid_chat_tradeoff", "说明一下这个取舍是否合理，验证样本{n}。"),
            ],
            "memory": [
                ("valid_memory_style", "回忆一下我过去要求你怎么回答，验证样本{n}。"),
                ("valid_memory_project", "根据过去对话，我的项目重点是什么，验证样本{n}？"),
            ],
            "profile": [
                ("valid_profile_brief", "以后默认回答短一点，验证样本{n}。"),
                ("valid_profile_review", "以后帮我复盘时先列错误原因，验证样本{n}。"),
            ],
            "task": [
                ("valid_task_order", "安排一下下一轮实验顺序，验证样本{n}。"),
                ("valid_task_steps", "根据当前目标拆一个可执行计划，验证样本{n}。"),
            ],
            "file": [
                ("valid_file_markdown", "打开这个 markdown 看看结构，验证样本{n}。"),
                ("valid_file_jsonl", "查看这个 JSONL 前几条格式，验证样本{n}。"),
            ],
            "status": [
                ("valid_status_chain", "查看上一轮工具链路，不是问历史偏好，验证样本{n}。"),
                ("valid_status_trace", "查询最近 trace 里的工具调用，验证样本{n}。"),
            ],
            "content": [
                ("valid_content_repo", "保存这个 GitHub 项目地址，验证样本{n}。"),
                ("valid_content_library", "把这条资料加入内容库，验证样本{n}。"),
            ],
            "action": [
                ("valid_action_config", "覆盖这个配置文件，验证样本{n}。"),
                ("valid_action_shell", "运行 shell 查看环境，验证样本{n}。"),
            ],
            "unknown": [
                ("valid_unknown_image", "调用那个新能力处理图片，验证样本{n}。"),
                ("valid_unknown_audio", "用未知插件分析这段音频，验证样本{n}。"),
            ],
        },
        "test": {
            "chat": [
                ("test_chat_resume", "这段简历项目表述是否容易理解，测试样本{n}？"),
                ("test_chat_concept", "解释一下任务计划和普通建议的区别，测试样本{n}。"),
            ],
            "memory": [
                ("test_memory_name", "我之前有没有说过项目命名偏好，测试样本{n}？"),
                ("test_memory_v3", "根据过去对话，V3 的主要问题是什么，测试样本{n}？"),
            ],
            "profile": [
                ("test_profile_style", "以后讨论方案时先说取舍，测试样本{n}。"),
                ("test_profile_summary", "请记住我喜欢先总结再展开，测试样本{n}。"),
            ],
            "task": [
                ("test_task_priority", "把后续工作排一下优先级，测试样本{n}。"),
                ("test_task_continue", "继续执行上一步计划，测试样本{n}。"),
            ],
            "file": [
                ("test_file_config", "只读查看配置文件，不要执行命令，测试样本{n}。"),
                ("test_file_log", "帮我看日志内容，不要运行 shell，测试样本{n}。"),
            ],
            "status": [
                ("test_status_memory_boundary", "看一下运行记录，不要查询我的长期记忆，测试样本{n}。"),
                ("test_status_token", "刚才的 token 消耗记录了吗，测试样本{n}？"),
            ],
            "content": [
                ("test_content_web", "保存这个网页，不是执行下载命令，测试样本{n}。"),
                ("test_content_video", "收藏这个视频链接，不要运行 shell，测试样本{n}。"),
            ],
            "action": [
                ("test_action_script", "把这个脚本执行一遍，测试样本{n}。"),
                ("test_action_download", "调用工具把这个链接转成文件，测试样本{n}。"),
            ],
            "unknown": [
                ("test_unknown_device", "检查这个设备状态，测试样本{n}。"),
                ("test_unknown_that", "用合适的方法完成它，测试样本{n}。"),
            ],
        },
    }
    return [TemplateSpec(family, text) for family, text in templates[split][scene]]


def _compound_templates(split: str, scene: str) -> list[TemplateSpec]:
    templates: dict[str, dict[str, list[tuple[str, str]]]] = {
        "train": {
            "chat": [
                ("train_chat_compare", "比较这个概念和那个概念，并说明区别，第{n}组。"),
                ("train_chat_review", "分析这个方案和那个方案，同时指出优缺点，第{n}组。"),
            ],
            "memory": [
                ("train_memory_two_prefs", "你还记得我的回答偏好和项目命名偏好吗，第{n}组？"),
                ("train_memory_two_facts", "查一下我之前说过的训练计划和测试结论，第{n}组。"),
            ],
            "profile": [
                ("train_profile_two_rules", "以后回答我先给结论，并减少英文缩写，第{n}组。"),
                ("train_profile_two_habits", "记住我喜欢条目式输出和保留测试数据，第{n}组。"),
            ],
            "task": [
                ("train_task_two_parts", "把训练和评测同时拆成可执行步骤，第{n}组。"),
                ("train_task_two_orders", "安排数据修订和模型评测两个任务，第{n}组。"),
            ],
            "file": [
                ("train_file_two_reads", "读取 README 和训练命令文档，第{n}组。"),
                ("train_file_two_checks", "查看数据文件和评测脚本，第{n}组。"),
            ],
            "status": [
                ("train_status_trace_tokens", "查看最近 trace 和 token 消耗，第{n}组。"),
                ("train_status_tools_errors", "查询工具调用记录和错误样本数量，第{n}组。"),
            ],
            "content": [
                ("train_content_two_items", "保存这个链接和这篇文章，第{n}组。"),
                ("train_content_two_sources", "收藏这个视频链接和项目地址，第{n}组。"),
            ],
            "action": [
                ("train_action_two_execs", "运行测试并把结果写入文件，第{n}组。"),
                ("train_action_two_changes", "修改这个配置并执行脚本，第{n}组。"),
            ],
            "unknown": [
                ("train_unknown_two_refs", "处理这个东西和那个内容，第{n}组。"),
                ("train_unknown_two_unknowns", "用那个新能力和未知插件处理它，第{n}组。"),
            ],
        },
        "valid": {
            "chat": [("valid_chat_pair", "解释这个概念和另一个概念，并比较差异，验证组{n}。")],
            "memory": [("valid_memory_pair", "回忆我的输出偏好和学习方向，验证组{n}。")],
            "profile": [("valid_profile_pair", "以后先总结，并把回答写短一点，验证组{n}。")],
            "task": [("valid_task_pair", "规划训练流程和复盘流程，验证组{n}。")],
            "file": [("valid_file_pair", "查看 README 和数据说明，验证组{n}。")],
            "status": [("valid_status_pair", "查询 trace 和工具链路，验证组{n}。")],
            "content": [("valid_content_pair", "保存这个链接和资料地址，验证组{n}。")],
            "action": [("valid_action_pair", "执行测试并更新输出文件，验证组{n}。")],
            "unknown": [("valid_unknown_pair", "处理这个内容和那个输入，验证组{n}。")],
        },
        "test": {
            "chat": [("test_chat_pair", "分析这个说法和另一个说法，同时给出建议，测试组{n}。")],
            "memory": [("test_memory_pair", "查一下我的回答偏好和简历偏好，测试组{n}。")],
            "profile": [("test_profile_pair", "以后先列结论，并少用英文缩写，测试组{n}。")],
            "task": [("test_task_pair", "把数据准备和训练验证排成步骤，测试组{n}。")],
            "file": [("test_file_pair", "读取评测脚本和错误文件，测试组{n}。")],
            "status": [("test_status_pair", "查看运行记录和 token 统计，测试组{n}。")],
            "content": [("test_content_pair", "收藏文章和视频链接，测试组{n}。")],
            "action": [("test_action_pair", "安装依赖并运行测试，测试组{n}。")],
            "unknown": [("test_unknown_pair", "按这个和那个要求处理，测试组{n}。")],
        },
    }
    return [TemplateSpec(family, text) for family, text in templates[split][scene]]


def _record(
    *,
    split: str,
    scene: str,
    mode: str,
    family: str,
    text: str,
) -> V4TrainingRecord:
    operation = SCENE_OPERATIONS[scene]
    return V4TrainingRecord(
        input=text,
        has_active_task=scene == "task",
        label=V4RouteLabel(scene, operation, mode),
        source=f"v4_1:{split}:{scene}:{mode}:{family}",
    )


def _compound_counts_for_split(split: str) -> dict[str, int]:
    scene_counts = SPLIT_SCENE_COUNTS[split]
    target_total = COMPOUND_COUNTS[split]
    raw = {scene: scene_counts[scene] * 0.2 for scene in SCENES}
    counts = {scene: int(raw[scene]) for scene in SCENES}
    remainder = target_total - sum(counts.values())
    ranked = sorted(SCENES, key=lambda scene: (raw[scene] - counts[scene], scene), reverse=True)
    for scene in ranked[:remainder]:
        counts[scene] += 1
    return counts


def _expand(
    *,
    split: str,
    scene: str,
    mode: str,
    count: int,
    templates: list[TemplateSpec],
) -> list[V4TrainingRecord]:
    records: list[V4TrainingRecord] = []
    for index in range(count):
        template = templates[index % len(templates)]
        records.append(
            _record(
                split=split,
                scene=scene,
                mode=mode,
                family=template.family,
                text=template.text.format(n=index + 1),
            )
        )
    return records


def _boundary_records() -> list[V4TrainingRecord]:
    return [
        V4TrainingRecord(
            input=text,
            has_active_task=scene == "task",
            label=V4RouteLabel(scene, operation, mode),
            source=f"v4_1:train:{scene}:boundary:known_v4_error_{index}",
        )
        for index, (text, scene, operation, mode) in enumerate(BOUNDARY_RECORDS, start=1)
    ]


def build_v4_1_records() -> list[V4TrainingRecord]:
    records: list[V4TrainingRecord] = []
    boundary_by_scene: dict[str, list[V4TrainingRecord]] = defaultdict(list)
    for record in _boundary_records():
        boundary_by_scene[record.label.scene].append(record)

    for split in SPLITS:
        compound_counts = _compound_counts_for_split(split)
        for scene in SCENES:
            total = SPLIT_SCENE_COUNTS[split][scene]
            compound_count = compound_counts[scene]
            boundaries = boundary_by_scene[scene] if split == "train" else []
            single_count = total - compound_count - len(boundaries)
            if single_count < 0:
                raise AssertionError(f"negative single count for {split}:{scene}")
            records.extend(boundaries)
            records.extend(
                _expand(
                    split=split,
                    scene=scene,
                    mode="single",
                    count=single_count,
                    templates=_single_templates(split, scene),
                )
            )
            records.extend(
                _expand(
                    split=split,
                    scene=scene,
                    mode="compound",
                    count=compound_count,
                    templates=_compound_templates(split, scene),
                )
            )

    issues = validate_v4_1_records(records)
    if issues:
        raise AssertionError(f"invalid V4.1 records: {issues}")
    return records


def _split_from_source(record: V4TrainingRecord) -> str:
    parts = record.source.split(":")
    if len(parts) < 2 or parts[0] != "v4_1" or parts[1] not in SPLITS:
        raise ValueError(f"invalid V4.1 source: {record.source}")
    return parts[1]


def split_v4_1_records(records: Iterable[V4TrainingRecord]) -> DatasetSplits:
    by_split = {split: [] for split in SPLITS}
    for record in records:
        by_split[_split_from_source(record)].append(record)
    for split in SPLITS:
        random.Random(f"{SHUFFLE_SEED}:v4_1:{split}").shuffle(by_split[split])
    return DatasetSplits(
        train=by_split["train"],
        valid=by_split["valid"],
        test=by_split["test"],
    )


def validate_v4_1_records(records: Iterable[V4TrainingRecord]) -> list[str]:
    rows = list(records)
    issues: list[str] = []
    split_counts = {split: 0 for split in SPLITS}
    split_families: dict[str, set[str]] = {split: set() for split in SPLITS}
    compound_count = 0
    inputs_by_split: dict[str, set[str]] = {split: set() for split in SPLITS}

    for record in rows:
        try:
            split = _split_from_source(record)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        split_counts[split] += 1
        inputs_by_split[split].add(record.input)
        split_families[split].add(":".join(record.source.split(":")[2:]))
        if record.label.request_mode == "compound":
            compound_count += 1
            if "compound" not in record.source:
                issues.append(f"compound source missing marker: {record.source}")
            if not any(marker in record.input for marker in COMPOUND_MARKERS):
                issues.append(f"compound input missing semantic marker: {record.input}")

    if len(rows) != 3000:
        issues.append(f"total records mismatch: {len(rows)}")
    expected_split_counts = {"train": 2400, "valid": 300, "test": 300}
    if split_counts != expected_split_counts:
        issues.append(f"split counts mismatch: {split_counts}")
    if compound_count != 600:
        issues.append(f"compound count mismatch: {compound_count}")

    for left, right in (("train", "valid"), ("train", "test"), ("valid", "test")):
        overlap = inputs_by_split[left] & inputs_by_split[right]
        if overlap:
            issues.append(f"input overlap {left}/{right}: {sorted(overlap)[:3]}")
        family_overlap = split_families[left] & split_families[right]
        if family_overlap:
            issues.append(
                f"template family overlap {left}/{right}: {sorted(family_overlap)[:3]}"
            )

    labels = {record.input: record.label for record in rows}
    for text, scene, operation, mode in BOUNDARY_RECORDS:
        label = labels.get(text)
        if label != V4RouteLabel(scene, operation, mode):
            issues.append(f"boundary label mismatch: {text}")
    return issues


def write_jsonl(path: Path, records: Iterable[V4TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v4_1_dataset_files(out_dir: Path) -> DatasetSplits:
    splits = split_v4_1_records(build_v4_1_records())
    write_jsonl(out_dir / "route_v4_1_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_v4_1_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_v4_1_test.jsonl", splits.test)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V4.1 JSONL data.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args(argv)
    splits = write_v4_1_dataset_files(args.out_dir)
    records = [*splits.train, *splits.valid, *splits.test]
    issues = validate_v4_1_records(records)
    summary = {
        "train": len(splits.train),
        "valid": len(splits.valid),
        "test": len(splits.test),
        "total": len(records),
        "compound_count": sum(
            record.label.request_mode == "compound" for record in records
        ),
        "shuffle_seed": SHUFFLE_SEED,
        "out_dir": str(args.out_dir),
        "issues": issues,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

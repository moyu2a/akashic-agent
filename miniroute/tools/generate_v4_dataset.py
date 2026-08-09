from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Iterable

from miniroute.v4_schema import V4RouteLabel, V4TrainingRecord

SHUFFLE_SEED = 20260806

SCENE_COUNTS: dict[str, int] = {
    "chat": 450,
    "memory": 360,
    "profile": 300,
    "task": 390,
    "file": 360,
    "status": 300,
    "content": 300,
    "action": 360,
    "unknown": 180,
}


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    train: list[V4TrainingRecord]
    valid: list[V4TrainingRecord]
    test: list[V4TrainingRecord]


def _record(
    text: str,
    *,
    scene: str,
    operation: str,
    source: str,
    has_active_task: bool = False,
    request_mode: str = "single",
) -> V4TrainingRecord:
    return V4TrainingRecord(
        input=text,
        has_active_task=has_active_task,
        label=V4RouteLabel(scene, operation, request_mode),
        source=source,
    )


def _expand(
    templates: list[str],
    count: int,
    *,
    scene: str,
    operation: str,
    source: str,
    active_every: int = 0,
) -> list[V4TrainingRecord]:
    records: list[V4TrainingRecord] = []
    for index in range(count):
        text = templates[index % len(templates)].format(n=index + 1)
        records.append(
            _record(
                text,
                scene=scene,
                operation=operation,
                request_mode="compound" if index % 5 == 0 else "single",
                has_active_task=bool(active_every and index % active_every == 0),
                source=source,
            )
        )
    return records


def build_v4_records() -> list[V4TrainingRecord]:
    records: list[V4TrainingRecord] = []
    records += _expand(
        [
            "帮我解释一下这个概念，第{n}版。",
            "这段项目描述怎么写更清楚？",
            "分析一下这个方案是否合理。",
            "我只是想讨论思路，不需要查文件。",
            "说明一下工具治理为什么重要。",
            "这个简历表述是否容易理解？",
        ],
        260,
        scene="chat",
        operation="answer",
        source="v4:chat_core",
    )
    records += _expand(
        [
            "这只是分析表达，不是让我记住偏好。",
            "帮我判断这句话是否适合简历，不要更新用户画像。",
            "解释一下分点输出的好处，不是设置长期偏好。",
            "这里讨论回答风格，不要保存成我的规则。",
        ],
        90,
        scene="chat",
        operation="answer",
        source="v4:chat_vs_profile",
    )
    records += _expand(
        [
            "解释一下任务计划和普通建议的区别。",
            "这个计划写得是否清楚？",
            "帮我分析下一步方案，不要创建任务。",
            "什么叫按优先级排序？",
        ],
        100,
        scene="chat",
        operation="answer",
        source="v4:task_vs_chat",
    )

    records += _expand(
        [
            "你还记得我之前说过的回答偏好吗？",
            "我上次提到 MiniRoute 的重点是什么？",
            "查一下我以前说过的训练计划。",
            "根据我过去的偏好，这段话应该怎么改？",
            "我之前有没有说过项目命名偏好？",
        ],
        210,
        scene="memory",
        operation="query",
        source="v4:memory_core",
    )
    records += _expand(
        [
            "我之前说过喜欢什么输出方式？",
            "回忆一下我过去要求你怎么回答。",
            "查一下历史记忆里我的学习方向。",
        ],
        90,
        scene="memory",
        operation="query",
        source="v4:memory_vs_profile",
    )
    records += _expand(
        [
            "我之前说过哪些项目数据？",
            "回忆一下我上次讨论的测试结论。",
            "根据过去对话，V3 的主要问题是什么？",
        ],
        60,
        scene="memory",
        operation="query",
        source="v4:memory_vs_status",
    )

    records += _expand(
        [
            "以后回答我先给结论。",
            "记住我不喜欢太多英文缩写。",
            "之后写简历时多保留测试数据。",
            "以后讨论方案时先说取舍。",
            "把我的偏好改成回答更短一点。",
        ],
        210,
        scene="profile",
        operation="update",
        source="v4:profile_core",
    )
    records += _expand(
        [
            "以后默认用条目式输出。",
            "请记住我喜欢先总结再展开。",
            "以后帮我复盘时先列错误原因。",
        ],
        90,
        scene="profile",
        operation="update",
        source="v4:memory_vs_profile",
    )

    records += _expand(
        [
            "帮我把 MiniRoute V4 拆成几个阶段。",
            "制定一个训练和评测计划。",
            "下一步该做什么？",
            "当前任务进展到哪里了？",
            "继续执行上一步计划。",
            "把后续工作排一下优先级。",
        ],
        260,
        scene="task",
        operation="plan",
        source="v4:task_core",
        active_every=3,
    )
    records += _expand(
        [
            "把测试、训练、复盘分成几个任务。",
            "安排一下下一轮实验顺序。",
            "根据当前目标拆一个可执行计划。",
        ],
        130,
        scene="task",
        operation="plan",
        source="v4:task_vs_chat",
        active_every=2,
    )

    records += _expand(
        [
            "读取 README 看看当前项目进展。",
            "帮我看一下 eval_route.py 有没有问题。",
            "总结 miniroute 下的文档。",
            "打开这个 markdown 看看结构。",
            "查看这个 JSONL 前几条格式。",
        ],
        240,
        scene="file",
        operation="read",
        source="v4:file_core",
    )
    records += _expand(
        [
            "只读查看配置文件，不要执行命令。",
            "帮我看日志内容，不要运行 shell。",
            "分析测试文件覆盖了什么场景，不要修改文件。",
        ],
        120,
        scene="file",
        operation="read",
        source="v4:file_vs_action",
    )

    records += _expand(
        [
            "刚才用了哪些工具？",
            "当前测试结果是多少？",
            "查看最近一次 trace。",
            "本轮训练错误样本有多少？",
            "刚才的 token 消耗记录了吗？",
        ],
        210,
        scene="status",
        operation="query",
        source="v4:status_core",
    )
    records += _expand(
        [
            "查看上一轮工具链路，不是问历史偏好。",
            "查询最近 trace 里的工具调用。",
            "看一下运行记录，不要查询我的长期记忆。",
        ],
        90,
        scene="status",
        operation="query",
        source="v4:memory_vs_status",
    )

    records += _expand(
        [
            "帮我保存这个链接。",
            "收藏这篇文章，标记为后续阅读。",
            "把这个视频记录到资料库。",
            "保存这个 GitHub 项目地址。",
            "把这条资料加入内容库。",
        ],
        210,
        scene="content",
        operation="save",
        source="v4:content_core",
    )
    records += _expand(
        [
            "保存这个网页，不是执行下载命令。",
            "收藏这个视频链接，不要运行 shell。",
            "记录这篇文章地址，不是修改本地文件。",
        ],
        90,
        scene="content",
        operation="save",
        source="v4:content_vs_action",
    )

    records += _expand(
        [
            "执行这个命令。",
            "删除这个目录。",
            "帮我修改这个文件。",
            "安装这些依赖。",
            "运行测试并把结果写入文件。",
        ],
        240,
        scene="action",
        operation="execute",
        source="v4:action_core",
    )
    records += _expand(
        [
            "覆盖这个配置文件。",
            "运行 shell 查看环境。",
            "把这个脚本执行一遍。",
        ],
        60,
        scene="action",
        operation="execute",
        source="v4:file_vs_action",
    )
    records += _expand(
        [
            "下载并保存这个网页正文。",
            "调用工具把这个链接转成文件。",
        ],
        60,
        scene="action",
        operation="execute",
        source="v4:content_vs_action",
    )

    records += _expand(
        [
            "处理一下这个东西。",
            "帮我弄一下。",
            "这个要怎么搞？",
            "按刚才那个来。",
            "用合适的方法完成它。",
        ],
        120,
        scene="unknown",
        operation="unknown",
        source="v4:unknown_core",
    )
    records += _expand(
        [
            "调用那个新能力处理图片。",
            "用未知插件分析这段音频。",
            "检查这个设备状态。",
        ],
        60,
        scene="unknown",
        operation="unknown",
        source="v4:unknown_vs_action",
    )

    _assert_counts(records)
    return records


def split_v4_records(records: Iterable[V4TrainingRecord]) -> DatasetSplits:
    by_scene: dict[str, list[V4TrainingRecord]] = {}
    for record in records:
        by_scene.setdefault(record.label.scene, []).append(record)

    train: list[V4TrainingRecord] = []
    valid: list[V4TrainingRecord] = []
    test: list[V4TrainingRecord] = []
    for scene in sorted(by_scene):
        items = list(by_scene[scene])
        rng = random.Random(f"{SHUFFLE_SEED}:v4:{scene}")
        rng.shuffle(items)
        train_count = int(len(items) * 0.80)
        valid_count = int(len(items) * 0.10)
        train.extend(items[:train_count])
        valid.extend(items[train_count : train_count + valid_count])
        test.extend(items[train_count + valid_count :])

    random.Random(f"{SHUFFLE_SEED}:v4:train").shuffle(train)
    random.Random(f"{SHUFFLE_SEED}:v4:valid").shuffle(valid)
    random.Random(f"{SHUFFLE_SEED}:v4:test").shuffle(test)
    return DatasetSplits(train=train, valid=valid, test=test)


def write_jsonl(path: Path, records: Iterable[V4TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v4_dataset_files(out_dir: Path) -> DatasetSplits:
    splits = split_v4_records(build_v4_records())
    write_jsonl(out_dir / "route_v4_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_v4_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_v4_test.jsonl", splits.test)
    return splits


def _assert_counts(records: list[V4TrainingRecord]) -> None:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.label.scene] = counts.get(record.label.scene, 0) + 1
    if counts != SCENE_COUNTS:
        raise AssertionError(f"unexpected V4 scene counts: {counts}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V4 JSONL data.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args(argv)
    splits = write_v4_dataset_files(args.out_dir)
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

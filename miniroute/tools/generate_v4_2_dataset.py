from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import heapq
import json
from pathlib import Path
import random
import re
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
COMPOUND_MARKERS = ("并", "同时", "和", "分别", "以及")
REQUIRED_FAMILIES = {
    "file_no_shell",
    "file_config_log",
    "status_trace_tools",
    "status_not_memory",
    "memory_past_preference",
    "memory_not_status",
    "content_save_no_download",
    "action_execute_shell",
    "unknown_capability",
    "unknown_not_action",
    "task_next_plan",
    "chat_not_profile",
}
REQUIRED_HARD_NEGATIVE_FAMILIES = (
    "file_no_shell",
    "unknown_not_action",
    "content_save_no_download",
    "status_not_memory",
    "memory_not_status",
)
CONNECTOR_SINGLE_BOUNDARIES = {
    "下载并保存这个网页正文。": V4RouteLabel("action", "execute", "single"),
    "保存这个网页，不是执行下载命令。": V4RouteLabel("content", "save", "single"),
    "运行测试并把结果写入文件。": V4RouteLabel("action", "execute", "single"),
}


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    train: list[V4TrainingRecord]
    valid: list[V4TrainingRecord]
    test: list[V4TrainingRecord]


@dataclass(frozen=True, slots=True)
class SplitVariants:
    train: tuple[str, ...]
    valid: tuple[str, ...]
    test: tuple[str, ...]

    def for_split(self, split: str) -> tuple[str, ...]:
        return getattr(self, split)


@dataclass(frozen=True, slots=True)
class TemplateFamily:
    family: str
    scene: str
    operation: str
    request_mode: str
    variants: SplitVariants


ROOTS = (
    "训练流程",
    "评测脚本",
    "记忆策略",
    "工具治理",
    "运行日志",
    "数据版本",
    "任务计划",
    "简历内容",
    "项目描述",
    "错误样本",
    "上下文策略",
    "插件机制",
    "命令输出",
    "边界案例",
    "测试报告",
    "用户偏好",
    "资料链接",
    "系统状态",
    "配置文件",
    "未知能力",
)
QUALIFIERS = (
    "当前",
    "上一轮",
    "新的",
    "关键",
    "局部",
    "完整",
    "轻量",
    "复杂",
    "安全",
    "待确认",
    "可复盘",
    "高频",
    "低风险",
    "边界",
    "真实",
    "临时",
    "稳定",
    "候选",
    "补充",
    "对照",
)
DETAILS = (
    "先给结论",
    "保留数据",
    "不要执行",
    "只做分析",
    "关注差异",
    "说明原因",
    "避免误判",
    "记录证据",
    "检查边界",
    "用于复盘",
    "保持简洁",
    "强调风险",
    "区分场景",
    "不要写入",
    "不要下载",
    "保持只读",
    "查看摘要",
    "比较结果",
    "输出步骤",
    "确认状态",
)


def _families() -> list[TemplateFamily]:
    def fam(
        family: str,
        scene: str,
        operation: str,
        request_mode: str,
        train: tuple[str, ...],
        valid: tuple[str, ...],
        test: tuple[str, ...],
    ) -> TemplateFamily:
        return TemplateFamily(
            family=family,
            scene=scene,
            operation=operation,
            request_mode=request_mode,
            variants=SplitVariants(train=train, valid=valid, test=test),
        )

    return [
        fam("chat_explain", "chat", "answer", "single",
            ("帮我解释{a}这个概念，重点是{detail}。", "说明{a}为什么重要，要求{detail}。"),
            ("讲清楚{a}的含义，侧重{detail}。", "用简短方式解释{a}，并关注{detail}。"),
            ("分析{a}这个说法是否合理，重点看{detail}。", "帮我理解{a}，回答里要{detail}。")),
        fam("chat_review", "chat", "answer", "single",
            ("这段{a}表述是否清楚，帮我指出问题。", "帮我审一下{a}这句话是否适合简历。"),
            ("判断{a}这段话是否容易理解。", "看看{a}的表达有没有歧义。"),
            ("评估{a}这段描述是否准确。", "帮我分析{a}这句话的表达效果。")),
        fam("chat_not_profile", "chat", "answer", "single",
            ("这里只是讨论{a}表达，不要更新用户画像。", "分析{a}写法，不是设置我的长期偏好。"),
            ("帮我判断{a}是否清楚，不要记成偏好。", "讨论{a}的表述，不需要保存规则。"),
            ("解释{a}的表达差异，不要写入画像。", "只评价{a}，不要更新我的偏好。")),
        fam("chat_compare", "chat", "answer", "compound",
            ("比较{a}和{b}，并说明区别。", "分析{a}和{b}，同时指出优缺点。"),
            ("说明{a}以及{b}的差异。", "分别解释{a}和{b}的适用场景。"),
            ("比较{a}和{b}，并给出判断。", "把{a}和{b}放在一起分析。")),
        fam("memory_past_preference", "memory", "query", "single",
            ("你还记得我之前说过的{a}偏好吗？", "查一下我过去关于{a}的要求。"),
            ("回忆一下我以前对{a}有什么偏好。", "我之前有没有说过{a}相关要求？"),
            ("根据历史记录，我对{a}偏好是什么？", "查过去对话里我怎么要求{a}。")),
        fam("memory_project_history", "memory", "query", "single",
            ("我上次提到{a}的重点是什么？", "查一下我以前说过的{a}计划。"),
            ("根据过去对话，{a}的结论是什么？", "回忆一下上轮讨论的{a}。"),
            ("我之前对{a}做过什么判断？", "历史里关于{a}有什么记录？")),
        fam("memory_not_status", "memory", "query", "single",
            ("我之前说过哪些{a}数据？", "查历史记忆里的{a}结论，不是当前状态。"),
            ("回忆过去对话中的{a}信息。", "查一下以前讨论过的{a}内容。"),
            ("我过去有没有提过{a}？", "从长期记忆里找{a}相关事实。")),
        fam("memory_two_facts", "memory", "query", "compound",
            ("查一下我之前说过的{a}和{b}。", "你还记得我的{a}偏好和{b}偏好吗？"),
            ("回忆{a}以及{b}的历史记录。", "分别查一下我以前说过的{a}和{b}。"),
            ("根据过去对话找出{a}和{b}。", "查询历史里的{a}和{b}。")),
        fam("profile_answer_style", "profile", "update", "single",
            ("以后回答我关于{a}时先给结论。", "记住我希望{a}相关回答更简洁。"),
            ("以后处理{a}时默认先总结。", "把{a}回答偏好改成先说结论。"),
            ("以后聊{a}时少用英文缩写。", "记住我对{a}喜欢条目式表达。")),
        fam("profile_resume_style", "profile", "update", "single",
            ("之后写{a}时多保留测试数据。", "以后修改{a}时先突出结果。"),
            ("记住{a}内容要更具体。", "以后整理{a}时减少空话。"),
            ("以后写{a}要先写数字结果。", "把{a}偏好设为更短更明确。")),
        fam("profile_work_tone", "profile", "update", "single",
            ("以后讨论{a}时默认使用工作语气。", "记住{a}场景下回答要直接。"),
            ("把{a}相关偏好改成少寒暄。", "以后回答{a}时先列判断。"),
            ("记住我处理{a}时要更偏复盘口吻。", "以后{a}相关回答少用日常语气。")),
        fam("profile_two_rules", "profile", "update", "compound",
            ("以后回答我先给结论，并减少英文缩写。", "记住我喜欢条目式输出和保留测试数据。"),
            ("之后说明{a}时先总结，并保留关键数字。", "以后写{a}要简洁，同时突出测试结果。"),
            ("记住{a}回答要短，并先列错误原因。", "以后处理{a}时少废话以及多给数据。")),
        fam("task_next_plan", "task", "plan", "single",
            ("下一步围绕{a}该做什么？", "帮我把{a}拆成几个阶段。"),
            ("制定一个{a}执行计划。", "继续推进{a}，下一步是什么？"),
            ("把{a}后续工作排一下优先级。", "根据{a}目标拆一个可执行计划。")),
        fam("task_experiment_plan", "task", "plan", "single",
            ("给{a}设计训练和评测步骤。", "安排{a}的实验顺序。"),
            ("为{a}制定数据修订计划。", "规划{a}的验证流程。"),
            ("把{a}实验拆成可复盘步骤。", "安排{a}从数据到评测的流程。")),
        fam("task_boundary_plan", "task", "plan", "single",
            ("针对{a}边界问题制定下一轮计划。", "把{a}错误原因整理成行动项。"),
            ("围绕{a}失败样本安排修订步骤。", "规划{a}下一轮数据补充。"),
            ("给{a}制定一版复盘计划。", "安排{a}后续验证顺序。")),
        fam("task_priority", "task", "plan", "compound",
            ("把{a}和{b}同时拆成任务。", "安排{a}以及{b}的优先级。"),
            ("规划{a}和{b}两个阶段。", "分别给{a}和{b}制定步骤。"),
            ("把{a}和{b}排成执行顺序。", "同时推进{a}和{b}该怎么安排？")),
        fam("file_no_shell", "file", "read", "single",
            ("只读查看{a}，不要执行命令。", "帮我看{a}内容，不要运行 shell。"),
            ("打开{a}看一下，保持只读。", "查看{a}文本，不要触发执行。"),
            ("看一下{a}文件，不要跑命令。", "只读取{a}，不要修改或执行。")),
        fam("file_config_log", "file", "read", "single",
            ("帮我看{a}日志内容，关注{detail}。", "读取{a}配置文件，看看{detail}。"),
            ("检查{a}配置文本，重点是{detail}。", "查看{a}日志片段，找出{detail}。"),
            ("看一下{a}配置内容，说明{detail}。", "只读分析{a}日志，关注{detail}。")),
        fam("file_docs_jsonl", "file", "read", "single",
            ("总结{a}下的文档结构。", "查看{a} JSONL 前几条格式。"),
            ("打开{a} markdown 看看结构。", "读取{a}说明文档并概括。"),
            ("看一下{a}数据文件格式。", "帮我读{a}文档内容。")),
        fam("file_path_boundary", "file", "read", "single",
            ("检查{a}路径是否存在，只读查看。", "读取{a}目录里的说明文件。"),
            ("帮我看{a}文件摘要，不要修改。", "查看{a}路径下的文本内容。"),
            ("只读打开{a}，确认里面写了什么。", "看一下{a}文件，不做执行动作。")),
        fam("file_read_code", "file", "read", "compound",
            ("读取{a}和{b}两个文件。", "查看{a}以及{b}的主要内容。"),
            ("同时看一下{a}和{b}。", "分别总结{a}与{b}。"),
            ("打开{a}和{b}进行对比。", "只读查看{a}以及{b}。")),
        fam("status_trace_tools", "status", "query", "single",
            ("刚才用了哪些工具？关注{detail}。", "查看最近 trace 的工具调用。"),
            ("查询上一轮工具链路。", "看一下最近运行轨迹。"),
            ("刚才工具调用记录是什么？", "查看 trace 中的调用顺序。")),
        fam("status_token_result", "status", "query", "single",
            ("当前测试结果是多少？", "刚才的 token 消耗记录了吗？"),
            ("查询本轮评测指标。", "查看最近一次运行结果。"),
            ("刚才输出的统计是多少？", "看一下当前结果记录。")),
        fam("status_not_memory", "status", "query", "single",
            ("看一下运行记录，不要查询我的长期记忆。", "查看工具链路，不是问历史偏好。"),
            ("查询当前 trace，不要回忆过去偏好。", "看运行状态，不查长期记忆。"),
            ("查看本轮记录，不要读取历史画像。", "查当前工具历史，不是查记忆。")),
        fam("status_current_run", "status", "query", "single",
            ("当前任务跑到哪一步了？", "看一下这次执行是否结束。"),
            ("查询当前后台任务状态。", "查看最近一次命令是否完成。"),
            ("现在评测进度是多少？", "检查当前流程有没有报错。")),
        fam("status_pair", "status", "query", "compound",
            ("查看最近 trace 和 token 消耗。", "查询工具调用记录以及错误样本数量。"),
            ("同时查看运行结果和工具链路。", "分别查询 trace 与 token 统计。"),
            ("看运行记录和模型调用轮次。", "查询状态以及最近错误数量。")),
        fam("content_save_link", "content", "save", "single",
            ("帮我保存{a}链接。", "收藏{a}资料地址。"),
            ("把{a}加入内容库。", "记录{a}这个资料链接。"),
            ("保存{a}，后续再看。", "把{a}资料收进收藏。")),
        fam("content_save_no_download", "content", "save", "single",
            ("保存这个网页，不是执行下载命令。", "收藏{a}链接，不要运行 shell。"),
            ("记录{a}网页地址，不要下载正文。", "保存{a}资料，不修改本地文件。"),
            ("把{a}链接加入内容库，不执行工具下载。", "收藏{a}页面，不触发命令。")),
        fam("content_two_items", "content", "save", "compound",
            ("保存{a}和{b}两个链接。", "收藏{a}以及{b}。"),
            ("把{a}和{b}加入资料库。", "同时记录{a}与{b}。"),
            ("保存{a}，并收藏{b}。", "分别记录{a}和{b}两个资料。")),
        fam("content_article_video", "content", "save", "single",
            ("把{a}视频记录到资料库。", "收藏{a}文章，标记为后续阅读。"),
            ("保存{a}项目地址。", "记录{a}文章链接。"),
            ("收藏{a}视频链接。", "把{a}这篇文章加入内容库。")),
        fam("content_note_save", "content", "save", "single",
            ("把{a}这条资料先记到内容库。", "保存{a}笔记，后面整理。"),
            ("记录{a}这段内容作为素材。", "把{a}摘要保存起来。"),
            ("收藏{a}这条素材，不需要执行命令。", "把{a}保存成待读内容。")),
        fam("action_execute_shell", "action", "execute", "single",
            ("运行 shell 查看{a}环境。", "下载并保存这个网页正文。"),
            ("把这个脚本执行一遍。", "运行测试命令。"),
            ("在命令行执行{a}检查。", "启动脚本处理{a}。")),
        fam("action_modify_file", "action", "execute", "single",
            ("帮我修改{a}文件。", "覆盖这个配置文件。"),
            ("把{a}写入输出文件。", "更新{a}配置内容。"),
            ("编辑{a}并保存结果。", "修改{a}里的设置。")),
        fam("action_install_run", "action", "execute", "single",
            ("安装这些依赖。", "运行测试并把结果写入文件。"),
            ("安装{a}后执行检查。", "执行测试并保存日志。"),
            ("运行构建并写入报告。", "安装依赖并运行验证。")),
        fam("action_approval_needed", "action", "execute", "single",
            ("执行高风险命令前先申请确认。", "准备修改{a}，需要走审批。"),
            ("运行会写文件的操作前先确认。", "执行{a}变更，需要风险判断。"),
            ("准备触发外部操作处理{a}。", "执行{a}之前先判断权限。")),
        fam("action_download_save", "action", "execute", "compound",
            ("下载{a}并保存网页正文。", "调用工具把{a}转成文件并保存。"),
            ("抓取{a}并写入本地文件。", "下载{a}以及生成输出文件。"),
            ("执行下载并保存{a}内容。", "调用外部工具和写文件处理{a}。")),
        fam("unknown_capability", "unknown", "unknown", "single",
            ("调用那个新能力处理{a}。", "用未知插件分析{a}。"),
            ("这个未注册能力能处理{a}吗？", "尝试用新插件看{a}是否支持。"),
            ("能不能用图像插件处理{a}？", "这个能力现在是否能处理{a}？")),
        fam("unknown_not_action", "unknown", "unknown", "single",
            ("按刚才那个来。", "用合适的方法完成它。"),
            ("处理一下这个东西。", "帮我弄一下这个内容。"),
            ("这个要怎么搞？", "按前面说的方式处理它。")),
        fam("unknown_vague_reference", "unknown", "unknown", "single",
            ("检查这个设备状态。", "处理那个外部对象。"),
            ("看一下这个未说明的输入。", "判断这个新资源能不能处理。"),
            ("分析这个未知来源内容。", "帮我处理未定义的材料。")),
        fam("unknown_missing_context", "unknown", "unknown", "single",
            ("按上面那个配置处理。", "根据刚才那个结果继续。"),
            ("把那个东西整理一下。", "继续处理前面提到的对象。"),
            ("这个输入缺少上下文，先判断类型。", "这个请求信息不完整，先标记未知。")),
        fam("unknown_pair", "unknown", "unknown", "compound",
            ("处理这个东西和那个内容。", "用未知能力分别分析{a}和{b}。"),
            ("同时检查这个设备和那个输入。", "处理{a}以及{b}两个未知对象。"),
            ("按这个和那个要求处理。", "分别看{a}和{b}能否处理。")),
    ]


def _family_index() -> dict[str, TemplateFamily]:
    return {family.family: family for family in _families()}


def _values(seed: str, index: int) -> tuple[str, str, str]:
    digest = hashlib.sha256(f"{SHUFFLE_SEED}:{seed}:{index}".encode("utf-8")).digest()
    base = int.from_bytes(digest[:8], "big")
    a = f"{QUALIFIERS[base % len(QUALIFIERS)]}{ROOTS[(base // 7) % len(ROOTS)]}"
    b = f"{QUALIFIERS[(base // 11) % len(QUALIFIERS)]}{ROOTS[(base // 17) % len(ROOTS)]}"
    if b == a:
        b = f"{QUALIFIERS[(base // 19) % len(QUALIFIERS)]}{ROOTS[(base // 23) % len(ROOTS)]}"
    detail = DETAILS[(base // 29) % len(DETAILS)]
    return a, b, detail


def _render(template: str, *, seed: str, index: int) -> str:
    a, b, detail = _values(seed, index)
    return template.format(a=a, b=b, detail=detail)


def _target_compound_counts(split: str) -> dict[str, int]:
    target_total = {"train": 480, "valid": 60, "test": 60}[split]
    raw = {scene: SPLIT_SCENE_COUNTS[split][scene] * 0.2 for scene in SCENES}
    counts = {scene: int(raw[scene]) for scene in SCENES}
    remainder = target_total - sum(counts.values())
    ranked = sorted(SCENES, key=lambda scene: (raw[scene] - counts[scene], scene), reverse=True)
    for scene in ranked[:remainder]:
        counts[scene] += 1
    return counts


def _split_scene_families(split: str, scene: str, mode: str) -> list[TemplateFamily]:
    return [
        family
        for family in _families()
        if family.scene == scene and family.request_mode == mode
    ]


def _record(
    *,
    split: str,
    family: TemplateFamily,
    text: str,
) -> V4TrainingRecord:
    return V4TrainingRecord(
        input=text,
        has_active_task=family.scene == "task",
        label=V4RouteLabel(family.scene, family.operation, family.request_mode),
        source=f"v4_2:{split}:{family.scene}:{family.request_mode}:{family.family}",
    )


def _expand_family(
    *,
    split: str,
    family: TemplateFamily,
    count: int,
    start_index: int,
) -> list[V4TrainingRecord]:
    variants = family.variants.for_split(split)
    records: list[V4TrainingRecord] = []
    seen: set[str] = set()
    index = 0
    while len(records) < count:
        template = variants[index % len(variants)]
        rendered = _render(
            template,
            seed=f"{split}:{family.family}:{start_index}",
            index=start_index + index,
        )
        if rendered in seen:
            a, _, detail = _values(
                f"{split}:{family.family}:duplicate:{start_index}",
                start_index + index,
            )
            rendered = f"{rendered.rstrip('。')}，补充关注{a}并{detail}。"
        index += 1
        if rendered in seen:
            continue
        seen.add(rendered)
        records.append(_record(split=split, family=family, text=rendered))
    return records


def _allocate_counts(total: int, families: list[TemplateFamily]) -> dict[str, int]:
    base = total // len(families)
    remainder = total % len(families)
    counts: dict[str, int] = {}
    for index, family in enumerate(families):
        counts[family.family] = base + (1 if index < remainder else 0)
    return counts


def build_v4_2_records() -> list[V4TrainingRecord]:
    records: list[V4TrainingRecord] = []
    for split in SPLITS:
        compound_counts = _target_compound_counts(split)
        for scene in SCENES:
            total = SPLIT_SCENE_COUNTS[split][scene]
            compound_total = compound_counts[scene]
            single_total = total - compound_total
            single_families = _split_scene_families(split, scene, "single")
            compound_families = _split_scene_families(split, scene, "compound")
            for family_name, count in _allocate_counts(single_total, single_families).items():
                family = _family_index()[family_name]
                records.extend(
                    _expand_family(
                        split=split,
                        family=family,
                        count=count,
                        start_index=len(records),
                    )
                )
            for family_name, count in _allocate_counts(compound_total, compound_families).items():
                family = _family_index()[family_name]
                records.extend(
                    _expand_family(
                        split=split,
                        family=family,
                        count=count,
                        start_index=len(records),
                    )
                )

    issues = validate_v4_2_records(records)
    if issues:
        raise AssertionError(f"invalid V4.2 records: {issues}")
    return records


def _split_from_source(record: V4TrainingRecord) -> str:
    parts = record.source.split(":")
    if len(parts) != 5 or parts[0] != "v4_2" or parts[1] not in SPLITS:
        raise ValueError(f"invalid V4.2 source: {record.source}")
    return parts[1]


def split_v4_2_records(records: Iterable[V4TrainingRecord]) -> DatasetSplits:
    by_split = {split: [] for split in SPLITS}
    for record in records:
        by_split[_split_from_source(record)].append(record)
    for split in SPLITS:
        random.Random(f"{SHUFFLE_SEED}:v4_2:{split}").shuffle(by_split[split])
    return DatasetSplits(
        train=by_split["train"],
        valid=by_split["valid"],
        test=by_split["test"],
    )


def normalize_for_leakage(text: str) -> str:
    text = re.sub(r"(训练|验证|测试)?样本[0-9一二三四五六七八九十百]+", "", text)
    text = re.sub(r"第[0-9一二三四五六七八九十百]+[轮组版次条]", "", text)
    text = re.sub(r"[0-9]+", "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。？！、；：,.!?;:]", "", text)
    return text


def _ngrams(text: str, n: int = 4) -> set[str]:
    if len(text) <= n:
        return {text}
    return {text[index : index + n] for index in range(len(text) - n + 1)}


def _jaccard_grams(left_grams: set[str], right_grams: set[str]) -> float:
    if not left_grams and not right_grams:
        return 1.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def _family_from_source(source: str) -> str:
    parts = source.split(":")
    if len(parts) != 5:
        raise ValueError(f"invalid V4.2 source: {source}")
    return parts[4]


def _normalized_by_split(
    splits: DatasetSplits,
) -> dict[str, list[tuple[str, str, set[str]]]]:
    return {
        "train": [
            (
                _family_from_source(record.source),
                normalized,
                _ngrams(normalized),
            )
            for record in splits.train
            for normalized in (normalize_for_leakage(record.input),)
        ],
        "valid": [
            (
                _family_from_source(record.source),
                normalized,
                _ngrams(normalized),
            )
            for record in splits.valid
            for normalized in (normalize_for_leakage(record.input),)
        ],
        "test": [
            (
                _family_from_source(record.source),
                normalized,
                _ngrams(normalized),
            )
            for record in splits.test
            for normalized in (normalize_for_leakage(record.input),)
        ],
    }


def top_cross_split_similar_pairs(
    splits: DatasetSplits,
    *,
    limit: int = 5,
) -> list[tuple[str, str, str, str, float]]:
    normalized = _normalized_by_split(splits)
    top: list[tuple[float, int, str, str, str, str]] = []
    sequence = 0
    for left, right in (("train", "valid"), ("train", "test"), ("valid", "test")):
        right_by_family: dict[str, list[tuple[str, set[str]]]] = defaultdict(list)
        for family, right_text, right_grams in normalized[right]:
            right_by_family[family].append((right_text, right_grams))
        for family, left_text, left_grams in normalized[left]:
            for right_text, right_grams in right_by_family[family]:
                score = _jaccard_grams(left_grams, right_grams)
                item = (score, sequence, left, right, left_text, right_text)
                sequence += 1
                if len(top) < limit:
                    heapq.heappush(top, item)
                elif score > top[0][0]:
                    heapq.heapreplace(top, item)
    return [
        (left, right, left_text, right_text, score)
        for score, _, left, right, left_text, right_text in sorted(
            top, key=lambda item: item[0], reverse=True
        )
    ]


def max_cross_split_similarity(splits: DatasetSplits) -> float:
    pairs = top_cross_split_similar_pairs(splits, limit=1)
    return pairs[0][4] if pairs else 0.0


def validate_v4_2_records(records: Iterable[V4TrainingRecord]) -> list[str]:
    rows = list(records)
    issues: list[str] = []
    split_counts = {split: 0 for split in SPLITS}
    scene_counts = Counter()
    compound_count = 0
    families_by_split: dict[str, set[str]] = {split: set() for split in SPLITS}
    family_counts_by_split: dict[str, Counter[str]] = {split: Counter() for split in SPLITS}
    family_counts_by_scene_mode: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    inputs_by_split: dict[str, list[str]] = {split: [] for split in SPLITS}

    for record in rows:
        try:
            split = _split_from_source(record)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        _, _, scene, mode, family = record.source.split(":")
        split_counts[split] += 1
        scene_counts[record.label.scene] += 1
        inputs_by_split[split].append(record.input)
        families_by_split[split].add(family)
        family_counts_by_split[split][family] += 1
        family_counts_by_scene_mode[(record.label.scene, record.label.request_mode)][family] += 1
        if scene != record.label.scene or mode != record.label.request_mode:
            issues.append(f"source/label mismatch: {record.source}")
        if record.label.request_mode == "compound":
            compound_count += 1
            if "compound" not in record.source:
                issues.append(f"compound source missing marker: {record.source}")
            if not any(marker in record.input for marker in COMPOUND_MARKERS):
                issues.append(f"compound input missing semantic marker: {record.input}")

    if len(rows) != 3000:
        issues.append(f"total records mismatch: {len(rows)}")
    if split_counts != {"train": 2400, "valid": 300, "test": 300}:
        issues.append(f"split counts mismatch: {split_counts}")
    expected_scene_counts = {
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
    if dict(scene_counts) != expected_scene_counts:
        issues.append(f"scene counts mismatch: {dict(scene_counts)}")
    if compound_count != 600:
        issues.append(f"compound count mismatch: {compound_count}")

    for split in SPLITS:
        normalized = [normalize_for_leakage(text) for text in inputs_by_split[split]]
        duplicate = [text for text, count in Counter(normalized).items() if count > 1]
        if duplicate:
            issues.append(f"internal normalized duplicate {split}: {duplicate[:3]}")

    all_inputs = {split: set(inputs_by_split[split]) for split in SPLITS}
    all_normalized = {
        split: {normalize_for_leakage(text) for text in inputs_by_split[split]}
        for split in SPLITS
    }
    for left, right in (("train", "valid"), ("train", "test"), ("valid", "test")):
        overlap = all_inputs[left] & all_inputs[right]
        if overlap:
            issues.append(f"input overlap {left}/{right}: {sorted(overlap)[:3]}")
        normalized_overlap = all_normalized[left] & all_normalized[right]
        if normalized_overlap:
            issues.append(
                f"normalized overlap {left}/{right}: {sorted(normalized_overlap)[:3]}"
            )

    splits = split_v4_2_records(rows)
    max_similarity = max_cross_split_similarity(splits)
    if max_similarity >= 0.92:
        issues.append(f"max cross split similarity too high: {max_similarity:.4f}")

    family_sets = list(families_by_split.values())
    if family_sets and not all(families == family_sets[0] for families in family_sets):
        issues.append("template families differ across splits")
    if not REQUIRED_FAMILIES <= family_sets[0]:
        issues.append(f"missing required families: {sorted(REQUIRED_FAMILIES - family_sets[0])}")

    for scene in SCENES:
        if len(family_counts_by_scene_mode[(scene, "single")]) < 3:
            issues.append(f"single family count too low: {scene}")
        if len(family_counts_by_scene_mode[(scene, "compound")]) < 1:
            issues.append(f"compound family missing: {scene}")
    for scene in ("file", "status", "unknown", "content", "action"):
        if len(family_counts_by_scene_mode[(scene, "single")]) < 4:
            issues.append(f"boundary single family count too low: {scene}")

    labels = {record.input: record.label for record in rows}
    for text, label in CONNECTOR_SINGLE_BOUNDARIES.items():
        if labels.get(text) != label:
            issues.append(f"connector single boundary mismatch: {text}")

    for family in REQUIRED_HARD_NEGATIVE_FAMILIES:
        if family_counts_by_split["train"][family] < 20:
            issues.append(
                f"hard negative family too small: {family}={family_counts_by_split['train'][family]}"
            )
    return issues


def write_jsonl(path: Path, records: Iterable[V4TrainingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_training_json(), ensure_ascii=False) + "\n")


def write_v4_2_dataset_files(out_dir: Path) -> DatasetSplits:
    splits = split_v4_2_records(build_v4_2_records())
    write_jsonl(out_dir / "route_v4_2_train.jsonl", splits.train)
    write_jsonl(out_dir / "route_v4_2_valid.jsonl", splits.valid)
    write_jsonl(out_dir / "route_v4_2_test.jsonl", splits.test)
    return splits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate MiniRoute V4.2 JSONL data.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    args = parser.parse_args(argv)
    splits = write_v4_2_dataset_files(args.out_dir)
    records = [*splits.train, *splits.valid, *splits.test]
    issues = validate_v4_2_records(records)
    similar_pairs = top_cross_split_similar_pairs(splits)
    summary = {
        "train": len(splits.train),
        "valid": len(splits.valid),
        "test": len(splits.test),
        "total": len(records),
        "compound_count": sum(
            record.label.request_mode == "compound" for record in records
        ),
        "max_cross_split_similarity": round(similar_pairs[0][4], 4) if similar_pairs else 0.0,
        "top_similar_pairs": similar_pairs,
        "shuffle_seed": SHUFFLE_SEED,
        "out_dir": str(args.out_dir),
        "issues": issues,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())

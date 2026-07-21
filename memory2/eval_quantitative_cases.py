from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from memory2.eval_cases import EVAL_CONFIG_PROFILES, EVAL_PHASE_TARGETS, EvalCase


EVAL_CASE_PACKS: tuple[str, ...] = ("standard", "comprehensive")

QUANTITATIVE_FEATURES: tuple[str, ...] = (
    "write_value_score",
    "tri_retrieval",
    "graph_retrieval",
    "rerank_shadow",
    "injection_governance_shadow",
    "version_chain_shadow",
    "provenance_shadow",
    "sleep_consolidation_shadow",
)

_COMMON_PHASE_TARGETS: tuple[str, ...] = tuple(EVAL_PHASE_TARGETS)
_COMMON_CONFIG_PROFILES: tuple[str, ...] = tuple(EVAL_CONFIG_PROFILES)

_EXPECTED_METRIC_KEYS: dict[str, list[str]] = {
    "write_value_score": [
        "candidate_count",
        "policy_reject_count",
        "temporary_risk_count",
        "duplicate_risk_count",
        "write_reduction_rate",
    ],
    "tri_retrieval": [
        "semantic_hit_count",
        "fused_hit_count",
        "retrieval_latency_ms",
    ],
    "graph_retrieval": [
        "graph_hit_count",
        "graph_path_count",
        "baseline_graph_overlap_rate",
    ],
    "rerank_shadow": [
        "rerank_changed_count",
        "baseline_experimental_overlap_rate",
        "source_ref_count",
    ],
    "injection_governance_shadow": [
        "prompt_token_delta",
        "dropped_by_reason",
    ],
    "version_chain_shadow": [
        "stale_recalled_count",
        "conflict_chain_count",
        "rollback_candidate_count",
    ],
    "provenance_shadow": [
        "source_ref_coverage",
        "parse_success_rate",
        "cross_scope_risk_count",
    ],
    "sleep_consolidation_shadow": [
        "duplicate_group_count",
        "stale_candidate_count",
        "estimated_token_saving",
    ],
}

_PROFILE_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "off": {
        "forbidden_trace_features": list(QUANTITATIVE_FEATURES),
    },
    "phase1": {
        "required_trace_features": ["write_value_score"],
        "forbidden_trace_features": [
            "tri_retrieval",
            "graph_retrieval",
            "rerank_shadow",
            "injection_governance_shadow",
            "version_chain_shadow",
            "provenance_shadow",
            "sleep_consolidation_shadow",
        ],
        "metric_keys": {
            "write_value_score": _EXPECTED_METRIC_KEYS["write_value_score"],
        },
    },
    "phase2": {
        "required_trace_features": ["tri_retrieval", "graph_retrieval"],
        "forbidden_trace_features": [
            "write_value_score",
            "rerank_shadow",
            "injection_governance_shadow",
            "version_chain_shadow",
            "provenance_shadow",
            "sleep_consolidation_shadow",
        ],
        "metric_keys": {
            "tri_retrieval": _EXPECTED_METRIC_KEYS["tri_retrieval"],
            "graph_retrieval": _EXPECTED_METRIC_KEYS["graph_retrieval"],
        },
    },
    "phase3": {
        "required_trace_features": ["rerank_shadow", "injection_governance_shadow"],
        "forbidden_trace_features": [
            "write_value_score",
            "tri_retrieval",
            "graph_retrieval",
            "version_chain_shadow",
            "provenance_shadow",
            "sleep_consolidation_shadow",
        ],
        "metric_keys": {
            "rerank_shadow": _EXPECTED_METRIC_KEYS["rerank_shadow"],
            "injection_governance_shadow": _EXPECTED_METRIC_KEYS[
                "injection_governance_shadow"
            ],
        },
    },
    "phase4": {
        "required_trace_features": ["version_chain_shadow", "provenance_shadow"],
        "forbidden_trace_features": [
            "write_value_score",
            "tri_retrieval",
            "graph_retrieval",
            "rerank_shadow",
            "injection_governance_shadow",
            "sleep_consolidation_shadow",
        ],
        "metric_keys": {
            "version_chain_shadow": _EXPECTED_METRIC_KEYS["version_chain_shadow"],
            "provenance_shadow": _EXPECTED_METRIC_KEYS["provenance_shadow"],
        },
    },
    "phase5": {
        "required_trace_features": ["sleep_consolidation_shadow"],
        "forbidden_trace_features": [
            "write_value_score",
            "tri_retrieval",
            "graph_retrieval",
            "rerank_shadow",
            "injection_governance_shadow",
            "version_chain_shadow",
            "provenance_shadow",
        ],
        "metric_keys": {
            "sleep_consolidation_shadow": _EXPECTED_METRIC_KEYS[
                "sleep_consolidation_shadow"
            ],
        },
    },
    "all": {
        "required_trace_features": list(QUANTITATIVE_FEATURES),
        "metric_keys": _EXPECTED_METRIC_KEYS,
    },
}


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    target_profile: str
    measurement_family: str
    memory_type: str
    target_summary: str
    graph_summary: str
    old_summary: str
    duplicate_summary: str
    conflict_summary: str
    stale_summary: str
    noise_summary: str
    query_common: str
    query_hard: str
    answer_contains: tuple[str, ...]
    forbidden_contains: tuple[str, ...]
    graph_topic: str
    primary_phase_target: str


_SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        name="preference_recall",
        target_profile="tri_retrieval_only",
        measurement_family="tri_retrieval",
        memory_type="preference",
        target_summary="用户偏好中文回答",
        graph_summary="用户偏好中文回答并保持条目式输出",
        old_summary="用户偏好英文回答",
        duplicate_summary="用户偏好中文回答",
        conflict_summary="用户不偏好中文回答",
        stale_summary="临时测试：这次先随便回答",
        noise_summary="助手推断：看起来应该喜欢英文",
        query_common="请继续用中文回答，并保持 pytest 风格。",
        query_hard="上次那个回答方式怎么说？",
        answer_contains=("中文",),
        forbidden_contains=("英文", "English"),
        graph_topic="中文回答",
        primary_phase_target="phase2a",
    ),
    ScenarioSpec(
        name="tool_preference",
        target_profile="tri_retrieval_only",
        measurement_family="tri_retrieval",
        memory_type="profile",
        target_summary="用户常用 pytest 做 Python 测试",
        graph_summary="Python 测试优先使用 pytest",
        old_summary="用户常用 unittest 做 Python 测试",
        duplicate_summary="用户常用 pytest 做 Python 测试",
        conflict_summary="用户更喜欢 unittest",
        stale_summary="临时测试记录：这次先不要记入长期记忆",
        noise_summary="助手推断：看起来应该喜欢 unittest",
        query_common="我之后写 Python 测试时优先用什么工具？",
        query_hard="那个测试工具偏好还在吗？",
        answer_contains=("pytest",),
        forbidden_contains=("unittest",),
        graph_topic="pytest",
        primary_phase_target="phase2a",
    ),
    ScenarioSpec(
        name="style_preference",
        target_profile="tri_retrieval_only",
        measurement_family="tri_retrieval",
        memory_type="preference",
        target_summary="回答时尽量用条目式",
        graph_summary="回答时优先条目式并保持简洁",
        old_summary="回答时尽量写成长段落",
        duplicate_summary="回答时尽量用条目式",
        conflict_summary="回答时尽量写成长段落",
        stale_summary="临时测试：这次先不要记",
        noise_summary="助手推断：看起来应该喜欢大段叙述",
        query_common="回答时保持条目式可以吗？",
        query_hard="之前说的格式要求是什么？",
        answer_contains=("条目式",),
        forbidden_contains=("长段落",),
        graph_topic="条目式",
        primary_phase_target="phase2a",
    ),
    ScenarioSpec(
        name="tri_rrf",
        target_profile="tri_retrieval_only",
        measurement_family="tri_retrieval",
        memory_type="procedure",
        target_summary="三路召回结果使用 RRF 融合排序",
        graph_summary="三路召回之后再用 RRF 排序",
        old_summary="三路召回结果按时间顺序排序",
        duplicate_summary="三路召回结果使用 RRF 融合排序",
        conflict_summary="三路召回后按时间顺序排序",
        stale_summary="临时测试：这次先不要记入长期记忆",
        noise_summary="助手推断：看起来应该按最近时间排序",
        query_common="三路召回要怎么融合排序？",
        query_hard="第三路方案怎么排序？",
        answer_contains=("RRF",),
        forbidden_contains=("时间顺序",),
        graph_topic="RRF",
        primary_phase_target="phase2a",
    ),
    ScenarioSpec(
        name="graph_bridge",
        target_profile="graph_only",
        measurement_family="graph_retrieval",
        memory_type="procedure",
        target_summary="NetworkX 实体图谱可以辅助第三路召回",
        graph_summary="实体图谱把第三路召回和 source_ref 连起来",
        old_summary="图谱只做展示，不参与检索",
        duplicate_summary="NetworkX 实体图谱可以辅助第三路召回",
        conflict_summary="图谱不参与第三路召回",
        stale_summary="临时测试：这个图谱节点先别记",
        noise_summary="助手推断：看起来应该只做静态图",
        query_common="图谱能辅助第三路召回吗？",
        query_hard="那个图谱路由怎么接？",
        answer_contains=("图谱", "NetworkX"),
        forbidden_contains=("只做展示",),
        graph_topic="图谱",
        primary_phase_target="phase2b",
    ),
    ScenarioSpec(
        name="version_chain",
        target_profile="version_provenance_only",
        measurement_family="version_provenance",
        memory_type="procedure",
        target_summary="旧版本记忆被新版本替换后只保留叶子",
        graph_summary="版本链只保留当前叶子并记录回滚候选",
        old_summary="旧版本和新版本都保留为有效",
        duplicate_summary="旧版本记忆被新版本替换后只保留叶子",
        conflict_summary="旧版本和新版本都有效",
        stale_summary="临时测试：这次先不要记入长期记忆",
        noise_summary="助手推断：看起来应该保留全部历史版本",
        query_common="旧版本替换后怎么处理？",
        query_hard="那个旧方案怎么回滚？",
        answer_contains=("叶子", "回滚"),
        forbidden_contains=("都保留",),
        graph_topic="版本链",
        primary_phase_target="phase4a",
    ),
    ScenarioSpec(
        name="cross_scope",
        target_profile="version_provenance_only",
        measurement_family="provenance",
        memory_type="event",
        target_summary="不同会话的偏好不能混用",
        graph_summary="session_key 隔离 telegram 和 qq",
        old_summary="所有平台可以共享会话状态",
        duplicate_summary="不同会话的偏好不能混用",
        conflict_summary="不同平台共享会话状态",
        stale_summary="临时测试：不同会话不要混淆",
        noise_summary="助手推断：看起来应该跨会话复用",
        query_common="不同会话的偏好能混用吗？",
        query_hard="别的会话内容还能继续用吗？",
        answer_contains=("会话", "隔离"),
        forbidden_contains=("共享会话状态",),
        graph_topic="session_key",
        primary_phase_target="phase4b",
    ),
    ScenarioSpec(
        name="duplicate_cleanup",
        target_profile="sleep_only",
        measurement_family="sleep_consolidation",
        memory_type="event",
        target_summary="重复内容要合并",
        graph_summary="重复记忆合并后减少冗余",
        old_summary="重复内容越多越好",
        duplicate_summary="重复内容要合并",
        conflict_summary="重复内容不需要合并",
        stale_summary="临时测试：重复记录",
        noise_summary="助手推断：看起来应该重复保存",
        query_common="重复内容怎么处理？",
        query_hard="那个重复句子还保留吗？",
        answer_contains=("合并",),
        forbidden_contains=("越多越好",),
        graph_topic="重复",
        primary_phase_target="phase5",
    ),
    ScenarioSpec(
        name="conflict_resolution",
        target_profile="rerank_only",
        measurement_family="rerank_injection",
        memory_type="preference",
        target_summary="冲突偏好要保留最新明确版本",
        graph_summary="冲突链应保留最新明确决策",
        old_summary="早期模糊说法优先",
        duplicate_summary="冲突偏好要保留最新明确版本",
        conflict_summary="早期模糊说法优先",
        stale_summary="临时测试：这次先不要记入长期记忆",
        noise_summary="助手推断：看起来应该按照旧结论",
        query_common="前后矛盾时以最新为准吗？",
        query_hard="前后矛盾的设置哪个算数？",
        answer_contains=("最新",),
        forbidden_contains=("早期模糊",),
        graph_topic="冲突",
        primary_phase_target="phase3a",
    ),
    ScenarioSpec(
        name="stale_sleep",
        target_profile="sleep_only",
        measurement_family="sleep_consolidation",
        memory_type="event",
        target_summary="离线睡眠巩固要清理过期低价值记忆",
        graph_summary="睡眠守护进程清理重复、过期、低价值",
        old_summary="过期记忆继续保留不处理",
        duplicate_summary="离线睡眠巩固要清理过期低价值记忆",
        conflict_summary="过期记忆继续保留不处理",
        stale_summary="临时测试：这次先不要记入长期记忆",
        noise_summary="助手推断：看起来应该继续保留旧内容",
        query_common="什么时候做离线睡眠巩固？",
        query_hard="后台整理旧记忆时怎么判断？",
        answer_contains=("睡眠", "清理"),
        forbidden_contains=("继续保留",),
        graph_topic="睡眠巩固",
        primary_phase_target="phase5",
    ),
)

_COMPREHENSIVE_EXTRA_SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        name="entity_alias",
        target_profile="graph_only",
        measurement_family="graph_retrieval",
        memory_type="profile",
        target_summary="用户把 memory2 称为第二套记忆系统",
        graph_summary="memory2、第二套记忆系统、向量记忆属于同一主题",
        old_summary="memory2 是临时测试名称",
        duplicate_summary="用户把 memory2 称为第二套记忆系统",
        conflict_summary="memory2 不属于记忆系统",
        stale_summary="临时备注：memory2 名称以后再定",
        noise_summary="助手推断：memory2 可能是数据库名",
        query_common="第二套记忆系统指的是哪个模块？",
        query_hard="他说的那个第二套是什么？",
        answer_contains=("memory2", "记忆"),
        forbidden_contains=("数据库名",),
        graph_topic="memory2",
        primary_phase_target="phase2b",
    ),
    ScenarioSpec(
        name="temporal_preference",
        target_profile="version_provenance_only",
        measurement_family="version_provenance",
        memory_type="preference",
        target_summary="用户现在希望先看百分比表格",
        graph_summary="当前汇报偏好是百分比表格优先",
        old_summary="用户以前希望先看长篇解释",
        duplicate_summary="用户现在希望先看百分比表格",
        conflict_summary="用户仍然希望先看长篇解释",
        stale_summary="临时测试：这次先口头说一下",
        noise_summary="助手推断：用户应该喜欢长篇解释",
        query_common="汇报测试结果时先给什么形式？",
        query_hard="最近那个展示偏好是什么？",
        answer_contains=("百分比", "表格"),
        forbidden_contains=("长篇解释",),
        graph_topic="百分比表格",
        primary_phase_target="phase4a",
    ),
    ScenarioSpec(
        name="low_value_filter",
        target_profile="write_value_only",
        measurement_family="write_governance",
        memory_type="event",
        target_summary="有长期复用价值的偏好才写入长期记忆",
        graph_summary="写入价值治理拦截低价值短期闲聊",
        old_summary="所有聊天内容都写入长期记忆",
        duplicate_summary="有长期复用价值的偏好才写入长期记忆",
        conflict_summary="短期闲聊也必须写入长期记忆",
        stale_summary="临时测试：今天午饭吃面",
        noise_summary="助手推断：任何句子都应该记住",
        query_common="什么内容适合写入长期记忆？",
        query_hard="刚才闲聊要不要都记下来？",
        answer_contains=("长期", "价值"),
        forbidden_contains=("所有聊天",),
        graph_topic="写入价值",
        primary_phase_target="phase1",
    ),
    ScenarioSpec(
        name="costly_call_preference",
        target_profile="write_value_only",
        measurement_family="write_governance",
        memory_type="procedure",
        target_summary="高风险或花费调用前必须确认",
        graph_summary="工具边界治理要求费用调用前确认",
        old_summary="模型选中工具后可以直接执行费用调用",
        duplicate_summary="高风险或花费调用前必须确认",
        conflict_summary="费用调用无需用户确认",
        stale_summary="临时测试：这次先跳过确认",
        noise_summary="助手推断：用户喜欢蓝色主题",
        query_common="调用会产生费用的服务前要怎么处理？",
        query_hard="花钱的工具模型选了就能跑吗？",
        answer_contains=("确认",),
        forbidden_contains=("直接执行", "模型自己确认"),
        graph_topic="工具确认",
        primary_phase_target="phase1",
    ),
    ScenarioSpec(
        name="injection_noise",
        target_profile="rerank_only",
        measurement_family="rerank_injection",
        memory_type="event",
        target_summary="注入上下文只放和当前问题有关的证据",
        graph_summary="注入治理会丢弃无关或低置信记忆",
        old_summary="上下文越多越好",
        duplicate_summary="注入上下文只放和当前问题有关的证据",
        conflict_summary="无关记忆也应该全部注入",
        stale_summary="临时测试：无关闲聊",
        noise_summary="助手推断：多放上下文更安全",
        query_common="回答前注入记忆时怎么控制范围？",
        query_hard="所有记忆都塞进 prompt 合适吗？",
        answer_contains=("有关", "证据"),
        forbidden_contains=("越多越好", "全部注入"),
        graph_topic="注入治理",
        primary_phase_target="phase3b",
    ),
    ScenarioSpec(
        name="source_ref_missing",
        target_profile="version_provenance_only",
        measurement_family="provenance",
        memory_type="event",
        target_summary="重要记忆应保留 source_ref 方便回源",
        graph_summary="溯源 scheme 依赖 source_ref 和解析成功率",
        old_summary="记忆不需要来源引用",
        duplicate_summary="重要记忆应保留 source_ref 方便回源",
        conflict_summary="source_ref 可以随意丢弃",
        stale_summary="临时测试：来源未知",
        noise_summary="助手推断：没有来源也可信",
        query_common="为什么记忆要保留来源引用？",
        query_hard="没有 source_ref 的记忆能不能当证据？",
        answer_contains=("source_ref", "回源"),
        forbidden_contains=("不需要来源",),
        graph_topic="source_ref",
        primary_phase_target="phase4b",
    ),
    ScenarioSpec(
        name="session_boundary",
        target_profile="version_provenance_only",
        measurement_family="provenance",
        memory_type="profile",
        target_summary="telegram:123 和 qq:123 是不同会话",
        graph_summary="session_key 由 channel 和 chat_id 共同组成",
        old_summary="chat_id 相同就是同一个会话",
        duplicate_summary="telegram:123 和 qq:123 是不同会话",
        conflict_summary="不同平台相同 chat_id 可以共享运行状态",
        stale_summary="临时测试：这次先混用 session",
        noise_summary="助手推断：chat_id 相同即可共享",
        query_common="telegram:123 和 qq:123 是同一个会话吗？",
        query_hard="两个入口数字一样能共享 history 吗？",
        answer_contains=("不同会话", "channel"),
        forbidden_contains=("同一个会话",),
        graph_topic="session_key",
        primary_phase_target="phase4b",
    ),
    ScenarioSpec(
        name="sleep_compaction",
        target_profile="sleep_only",
        measurement_family="sleep_consolidation",
        memory_type="event",
        target_summary="睡眠巩固要压缩重复内容并保留有效事实",
        graph_summary="离线异步巩固减少 token 但保持召回",
        old_summary="睡眠巩固可以随意删除有效事实",
        duplicate_summary="睡眠巩固要压缩重复内容并保留有效事实",
        conflict_summary="压缩时不需要考虑召回保持率",
        stale_summary="临时测试：重复低价值片段",
        noise_summary="助手推断：压缩越狠越好",
        query_common="睡眠巩固压缩后最重要的约束是什么？",
        query_hard="后台压缩能不能只看 token 下降？",
        answer_contains=("保留", "召回"),
        forbidden_contains=("随意删除", "越狠越好"),
        graph_topic="睡眠巩固",
        primary_phase_target="phase5",
    ),
    ScenarioSpec(
        name="causal_consistency",
        target_profile="version_provenance_only",
        measurement_family="version_provenance",
        memory_type="procedure",
        target_summary="因果一致性版本链要按替换关系追踪当前有效记忆",
        graph_summary="版本链记录 old -> new 的因果替换关系",
        old_summary="版本之间没有先后因果关系",
        duplicate_summary="因果一致性版本链要按替换关系追踪当前有效记忆",
        conflict_summary="旧版本和新版本可以同时作为当前事实",
        stale_summary="临时测试：版本顺序未确认",
        noise_summary="助手推断：直接按时间排序即可",
        query_common="因果一致性版本链解决什么问题？",
        query_hard="旧事实和新事实冲突时怎么追踪？",
        answer_contains=("替换", "当前"),
        forbidden_contains=("同时作为当前事实",),
        graph_topic="因果一致性",
        primary_phase_target="phase4a",
    ),
    ScenarioSpec(
        name="entropy_value",
        target_profile="write_value_only",
        measurement_family="write_governance",
        memory_type="procedure",
        target_summary="信息熵可以作为交互内容价值的量化参考",
        graph_summary="写入治理可用信息量辅助判断是否值得记忆",
        old_summary="低信息量重复内容也应大量写入",
        duplicate_summary="信息熵可以作为交互内容价值的量化参考",
        conflict_summary="信息量不影响写入决策",
        stale_summary="临时测试：嗯嗯好的",
        noise_summary="助手推断：短回复都值得长期保存",
        query_common="信息熵在记忆写入里能起什么作用？",
        query_hard="像嗯嗯好的这种内容值得长期写吗？",
        answer_contains=("信息", "价值"),
        forbidden_contains=("大量写入",),
        graph_topic="信息熵",
        primary_phase_target="phase1",
    ),
)


def build_quantitative_eval_cases(
    case_set: str = "all",
    limit: int = 0,
    case_pack: str = "standard",
) -> list[EvalCase]:
    normalized = str(case_set or "all").strip().lower()
    if normalized not in {"all", "common", "hard"}:
        raise ValueError("case_set must be 'all', 'common', or 'hard'")
    normalized_pack = str(case_pack or "standard").strip().lower()
    if normalized_pack not in EVAL_CASE_PACKS:
        raise ValueError("case_pack must be 'standard' or 'comprehensive'")

    cases: list[EvalCase] = []
    sets = ("common", "hard") if normalized == "all" else (normalized,)
    scenarios = (
        _SCENARIOS
        if normalized_pack == "standard"
        else _SCENARIOS + _COMPREHENSIVE_EXTRA_SCENARIOS
    )
    variant_count = 4 if normalized_pack == "standard" else 8
    for current_set in sets:
        for variant in range(1, variant_count + 1):
            for scenario in scenarios:
                cases.append(_build_case(scenario, current_set, variant))
    if limit > 0:
        return cases[:limit]
    return cases


def _build_case(scenario: ScenarioSpec, case_set: str, variant: int) -> EvalCase:
    prefix = f"{case_set}_{scenario.name}_{variant:02d}"
    channel, chat_id = ("cli", "local") if case_set == "common" else ("telegram", "123")
    scope = {
        "session_key": f"{channel}:{chat_id}",
        "channel": channel,
        "chat_id": chat_id,
    }
    query = scenario.query_common if case_set == "common" else scenario.query_hard
    memory_items = _build_memory_items(prefix, scope, scenario, case_set)
    memorize_calls = _build_memorize_calls(prefix, scenario, case_set)
    baseline_miss_recall_ids = _baseline_miss_recall_ids(
        prefix,
        scenario,
        case_set,
        variant,
    )
    setup: dict[str, Any] = {
        "scope": scope,
        "measurement_family": scenario.measurement_family,
        "target_profile": scenario.target_profile,
        "memory_items": memory_items,
        "memory_replacements": _build_memory_replacements(
            prefix,
            scenario,
            scope,
            case_set,
            variant,
        ),
        "memorize_calls": memorize_calls,
        "query": query,
    }
    expectations = {
        "should_recall_ids": [
            f"{prefix}_target",
            f"{prefix}_graph",
        ],
        "should_not_recall_ids": [
            f"{prefix}_old",
            f"{prefix}_noise",
            *( [f"{prefix}_cross_scope"] if case_set == "hard" else [] ),
        ],
        "expected_trace_features": list(QUANTITATIVE_FEATURES),
        "expected_metric_keys": _EXPECTED_METRIC_KEYS,
        "expected_graph_recall_ids": [f"{prefix}_graph"],
        "expected_active_version_ids": [f"{prefix}_target"],
        "expected_stale_version_ids": [f"{prefix}_old"],
        "expected_conflict_chain_count": (
            1
            if scenario.name == "version_chain" and case_set == "hard" and variant == 4
            else 0
        ),
        "profile_expectations": _PROFILE_EXPECTATIONS,
        "answer_expectations": {
            "expected_answer_contains": list(scenario.answer_contains),
            "expected_answer_contains_any": [
                list(scenario.answer_contains),
                [scenario.graph_topic, scenario.target_summary],
            ],
            "forbidden_answer_contains": list(scenario.forbidden_contains),
            "expected_memory_ids": [
                f"{prefix}_target",
                f"{prefix}_graph",
            ],
            "expected_language": "zh",
            "grounding_required": True,
        },
        "quantitative_thresholds": {
            "answer_rule_min": 0.45 if case_set == "common" else 0.35,
            "memory_grounding_min": 0.40 if case_set == "common" else 0.30,
            "forbidden_violation_max": 0.25 if case_set == "common" else 0.35,
            "token_cost_max": 5000,
            "latency_ms_max": 5000,
        },
    }
    if baseline_miss_recall_ids:
        expectations["baseline_miss_recall_ids"] = baseline_miss_recall_ids
    return EvalCase(
        id=prefix,
        title=f"{scenario.name.replace('_', ' ').title()} ({case_set} #{variant})",
        category=f"{case_set}_{scenario.name}",
        phase_targets=_COMMON_PHASE_TARGETS,
        config_profiles=_COMMON_CONFIG_PROFILES,
        setup=setup,
        expectations=expectations,
        source_path="",
    )


def _baseline_miss_recall_ids(
    prefix: str,
    scenario: ScenarioSpec,
    case_set: str,
    variant: int,
) -> list[str]:
    if case_set != "hard" or variant not in {3, 4}:
        return []
    if scenario.measurement_family == "tri_retrieval":
        return [f"{prefix}_target"]
    if scenario.measurement_family == "graph_retrieval":
        return [f"{prefix}_graph"]
    return []


def _build_memory_items(
    prefix: str,
    scope: dict[str, str],
    scenario: ScenarioSpec,
    case_set: str,
) -> list[dict[str, object]]:
    same_scope = dict(scope)
    other_scope = {
        "session_key": "qq:42" if case_set == "hard" else "cli:local",
        "channel": "qq" if case_set == "hard" else scope["channel"],
        "chat_id": "42" if case_set == "hard" else scope["chat_id"],
    }
    old_updated = datetime.now(timezone.utc) - timedelta(days=240)
    stale_updated = datetime.now(timezone.utc) - timedelta(days=365)
    target_id = f"{prefix}_target"
    graph_id = f"{prefix}_graph"
    old_id = f"{prefix}_old"
    duplicate_a = f"{prefix}_dup_a"
    duplicate_b = f"{prefix}_dup_b"
    conflict_id = f"{prefix}_conflict"
    stale_id = f"{prefix}_stale"
    noise_id = f"{prefix}_noise"

    items: list[dict[str, object]] = [
        {
            "id": target_id,
            "memory_type": scenario.memory_type,
            "summary": scenario.target_summary,
            "status": "active",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": [scenario.graph_topic, "RRF", "三路召回"]},
        },
        {
            "id": graph_id,
            "memory_type": "procedure",
            "summary": scenario.graph_summary,
            "status": "active",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": [scenario.graph_topic, "图谱", "source_ref"]},
        },
        {
            "id": old_id,
            "memory_type": scenario.memory_type,
            "summary": scenario.old_summary,
            "status": "superseded",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": [scenario.graph_topic]},
        },
        {
            "id": duplicate_a,
            "memory_type": "event",
            "summary": scenario.duplicate_summary,
            "status": "active",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": ["重复", scenario.graph_topic]},
        },
        {
            "id": duplicate_b,
            "memory_type": "event",
            "summary": scenario.duplicate_summary,
            "status": "active",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": ["重复", scenario.graph_topic]},
        },
        {
            "id": conflict_id,
            "memory_type": scenario.memory_type,
            "summary": scenario.conflict_summary,
            "status": "active",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": ["冲突", scenario.graph_topic]},
        },
        {
            "id": stale_id,
            "memory_type": "event",
            "summary": scenario.stale_summary,
            "status": "active",
            "source_ref": f"{scope['session_key']}@post_response",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "updated_at": stale_updated.isoformat(),
            "reinforcement": 0,
            "emotional_weight": 0,
            "extra_json": {"active_topics": ["过期", "低价值"]},
        },
        {
            "id": noise_id,
            "memory_type": "event",
            "summary": scenario.noise_summary,
            "status": "active",
            "source_ref": "",
            "scope_channel": same_scope["channel"],
            "scope_chat_id": same_scope["chat_id"],
            "extra_json": {"active_topics": ["助手推断"]},
        },
    ]

    if case_set == "hard":
        items.append(
            {
                "id": f"{prefix}_cross_scope",
                "memory_type": scenario.memory_type,
                "summary": scenario.target_summary,
                "status": "active",
                "source_ref": f"{other_scope['session_key']}@post_response",
                "scope_channel": other_scope["channel"],
                "scope_chat_id": other_scope["chat_id"],
                "extra_json": {"active_topics": [scenario.graph_topic, "跨会话"]},
            }
        )
    return items


def _build_memory_replacements(
    prefix: str,
    scenario: ScenarioSpec,
    scope: dict[str, str],
    case_set: str,
    variant: int,
) -> list[dict[str, object]]:
    replacements = [
        {
            "old_item_id": f"{prefix}_old",
            "new_item_id": f"{prefix}_target",
            "old_memory_type": scenario.memory_type,
            "new_memory_type": scenario.memory_type,
            "old_summary": scenario.old_summary,
            "new_summary": scenario.target_summary,
            "old_source_ref": f"{scope['session_key']}@post_response",
            "new_source_ref": f"{scope['session_key']}@post_response",
        }
    ]
    if scenario.name == "version_chain" and case_set == "hard" and variant == 4:
        replacements.append(
            {
                "old_item_id": f"{prefix}_old",
                "new_item_id": f"{prefix}_alt",
                "old_memory_type": scenario.memory_type,
                "new_memory_type": scenario.memory_type,
                "old_summary": scenario.old_summary,
                "new_summary": f"{scenario.target_summary}（分叉备选）",
                "old_source_ref": f"{scope['session_key']}@post_response",
                "new_source_ref": f"{scope['session_key']}@post_response",
            }
        )
    return replacements


def _build_memorize_calls(
    prefix: str,
    scenario: ScenarioSpec,
    case_set: str,
) -> list[dict[str, object]]:
    base = scenario.target_summary
    return [
        {
            "summary": f"以后请保持 {base}",
            "category": "preference",
            "result": f"item_id={prefix}_write_1 status=written",
        },
        {
            "summary": "临时测试记录：这次先不要记入长期记忆",
            "category": "status",
            "result": f"item_id={prefix}_write_2 status=rejected",
        },
        {
            "summary": f"助手推断：看起来应该 {scenario.conflict_summary}",
            "category": "decision",
            "result": f"item_id={prefix}_write_3 status=rejected",
        },
    ]

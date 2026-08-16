from __future__ import annotations

from memory2.eval_memory_governance_dataset import MemoryGovernanceEvalCase


SCENARIO_GROUPS: tuple[str, ...] = (
    "preference_replace",
    "user_correction",
    "similar_memory_conflict",
    "stale_memory_interference",
    "same_name_entity_confusion",
    "low_confidence_source",
    "ambiguous_question_with_answer",
    "insufficient_evidence_should_uncertain",
)


def generate_memory_governance_dataset(
    *,
    seed: int = 42,
    case_count: int = 80,
    eval_base_time: str = "2026-08-16T00:00:00Z",
) -> tuple[MemoryGovernanceEvalCase, ...]:
    if case_count % len(SCENARIO_GROUPS) != 0:
        raise ValueError("case_count must be divisible by scenario group count")
    per_group = case_count // len(SCENARIO_GROUPS)
    cases: list[MemoryGovernanceEvalCase] = []
    counter = 1
    for scenario in SCENARIO_GROUPS:
        for offset in range(per_group):
            cases.append(_build_case(counter, scenario, offset, eval_base_time))
            counter += 1
    return tuple(cases)


def _build_case(
    index: int,
    scenario: str,
    offset: int,
    eval_base_time: str,
) -> MemoryGovernanceEvalCase:
    case_id = f"mgov_{index:03d}"
    topic = _topic_for(scenario, offset)
    old_value, new_value, distractor = _values_for(scenario, offset)
    old_id = f"{case_id}_old"
    new_id = f"{case_id}_new"
    distractor_id = f"{case_id}_distractor"
    question = _question_for(scenario, topic)
    old_summary = f"用户过去在{topic}上的偏好是{old_value}"
    new_summary = f"用户现在在{topic}上的偏好是{new_value}"
    distractor_summary = f"用户在相邻但不同主题上的记录是{distractor}"
    return MemoryGovernanceEvalCase(
        case_id=case_id,
        scenario=scenario,
        user_question=question,
        eval_base_time=eval_base_time,
        memories=(
            {
                "id": old_id,
                "summary": old_summary,
                "content": old_summary,
                "status": "superseded",
                "relative_timestamp_days": -120 - offset,
                "confidence": "medium",
                "source_ref": f"eval://{case_id}/old",
            },
            {
                "id": new_id,
                "summary": new_summary,
                "content": new_summary,
                "status": "active",
                "relative_timestamp_days": -3 - (offset % 5),
                "confidence": "high",
                "source_ref": f"eval://{case_id}/new",
            },
            {
                "id": distractor_id,
                "summary": distractor_summary,
                "content": distractor_summary,
                "status": "active",
                "relative_timestamp_days": -15 - offset,
                "confidence": "low",
                "source_ref": f"eval://{case_id}/distractor",
            },
        ),
        should_recall_ids=(new_id,),
        should_not_recall_ids=(old_id, distractor_id),
        expected_answer_contains=(new_value,),
        expected_answer_contains_any=((new_value, f"当前{new_value}"),),
        forbidden_answer_contains=(old_value,),
        evidence_graph={
            "nodes": [old_id, new_id, distractor_id],
            "edges": [{"from": old_id, "to": new_id, "type": "supersedes"}],
        },
        profile_expectations={
            "chain_tri_retrieval": "may_fail",
            "chain_tri_candidate_governance": "should_improve",
            "chain_tri_evidence_only": "should_improve",
            "chain_tri_governed_answer_contract": "should_pass",
        },
        notes=f"{scenario} case，必须回答当前有效的{topic}信息。",
    )


def _topic_for(scenario: str, offset: int) -> str:
    topics = {
        "preference_replace": ("回答语言", "输出格式", "会议摘要风格"),
        "user_correction": ("项目代号", "默认分支", "部署环境"),
        "similar_memory_conflict": ("客户联系人", "候选方案", "文档路径"),
        "stale_memory_interference": ("出差城市", "报告截止日", "使用工具"),
        "same_name_entity_confusion": ("张伟的团队", "Phoenix 项目", "晨会频道"),
        "low_confidence_source": ("预算口径", "实验模型", "数据来源"),
        "ambiguous_question_with_answer": ("默认提醒时间", "首选审批人", "复盘模板"),
        "insufficient_evidence_should_uncertain": ("尚未确认的餐厅", "待定航班", "未定会议室"),
    }
    values = topics[scenario]
    return values[offset % len(values)]


def _values_for(scenario: str, offset: int) -> tuple[str, str, str]:
    pairs = {
        "preference_replace": ("英文", "中文", "代码注释保持英文"),
        "user_correction": ("Aurora", "Akashic", "另一个项目叫 Atlas"),
        "similar_memory_conflict": ("李雷", "韩梅梅", "李雷负责旧项目"),
        "stale_memory_interference": ("上海", "深圳", "上海天气记录"),
        "same_name_entity_confusion": ("后端张伟", "设计张伟", "销售张伟"),
        "low_confidence_source": ("粗略估算", "财务确认版", "同事转述版本"),
        "ambiguous_question_with_answer": ("上午九点", "下午三点", "其他日程在上午九点"),
        "insufficient_evidence_should_uncertain": ("已确认", "无法确认", "候选项尚未批准"),
    }
    old_value, new_value, distractor = pairs[scenario]
    if offset % 2 == 1:
        return (
            f"{old_value}{offset}",
            f"{new_value}{offset}",
            f"{distractor}{offset}",
        )
    return old_value, new_value, distractor


def _question_for(scenario: str, topic: str) -> str:
    if scenario == "insufficient_evidence_should_uncertain":
        return f"关于{topic}，我现在应该怎么回答？"
    if scenario == "same_name_entity_confusion":
        return f"请确认现在和{topic}相关的有效记忆是什么？"
    return f"我现在在{topic}上的有效偏好是什么？"

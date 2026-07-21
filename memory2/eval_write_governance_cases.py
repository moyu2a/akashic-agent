from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WriteGovernanceCandidate:
    id: str
    case_set: str
    category: str
    subtype: str
    summary: str
    expected_action: str
    existing_memories: tuple[dict[str, object], ...] = ()


CATEGORY_SUBTYPES: dict[str, dict[str, tuple[str, ...]]] = {
    "valuable_preference": {
        "common": ("answer_language", "answer_format", "tool_boundary", "meeting_style", "doc_style"),
        "hard": ("conditional_preference", "multi_constraint", "cross_session_preference", "priority_rule", "exception_rule"),
    },
    "stable_fact": {
        "common": ("project_metric", "repo_convention", "test_policy", "doc_policy", "branch_policy"),
        "hard": ("versioned_requirement", "multi_repo_rule", "evaluation_contract", "deployment_constraint", "review_standard"),
    },
    "temporary": {
        "common": ("today_only", "single_run", "debug_note", "scratch_data", "one_time_instruction"),
        "hard": ("near_term_deadline", "temporary_override", "session_only_secret", "expired_state", "tentative_plan"),
    },
    "assistant_inference": {
        "common": ("guessed_preference", "guessed_identity", "guessed_mood", "guessed_skill", "guessed_intent"),
        "hard": ("soft_inference", "statistical_guess", "ambiguous_signal", "unconfirmed_profile", "model_explanation"),
    },
    "duplicate": {
        "common": ("exact_preference", "exact_fact", "same_metric", "same_boundary", "same_doc_rule"),
        "hard": ("paraphrase_preference", "paraphrase_fact", "near_duplicate", "same_entities", "same_policy"),
    },
    "conflict": {
        "common": ("opposite_format", "opposite_language", "opposite_scope", "opposite_metric", "opposite_order"),
        "hard": ("partial_conflict", "priority_conflict", "time_conflict", "scope_conflict", "policy_conflict"),
    },
}


_VARIANT_SUBJECTS = (
    "面试材料",
    "评测报告",
    "插件文档",
    "记忆实验",
    "代码审阅",
    "线上复盘",
    "架构说明",
    "用户偏好",
    "测试计划",
    "项目记录",
)

_VARIANT_OBJECTS = (
    "先给结论",
    "保留关键数字",
    "按条目组织",
    "说明边界",
    "记录来源",
    "避免泛化",
    "区分事实和推断",
    "标出风险",
    "保留反例",
    "写清验证命令",
)

_VARIANT_CONTEXTS = (
    "在中文回答中",
    "在复盘文档里",
    "在离线评测时",
    "在面试表达中",
    "在更新 my_md 时",
    "在执行计划前",
    "在整理结论时",
    "在比较模块增益时",
    "在解释失败原因时",
    "在生成报告时",
)

_COMMON_PATTERNS = (
    "{subject}：以后请记住，{context}要{object}，样本 {index}",
    "{subject}：长期偏好是{context}{object}，样本 {index}",
    "{subject}：用户明确要求{context}{object}，样本 {index}",
    "{subject}：下次处理同类问题时请{object}，样本 {index}",
)

_HARD_WRITE_PATTERNS = (
    "{subject}：稳定要求是{context}{object}，适用于后续同类任务，样本 {index}",
    "{subject}：这条规则跨会话保留，{context}优先{object}，样本 {index}",
    "{subject}：当信息冲突时，先遵守{object}这一长期约束，样本 {index}",
    "{subject}：除非用户临时改口，否则{context}保持{object}，样本 {index}",
)

_TEMPORARY_PATTERNS = (
    "{subject}：今天这次先{object}，后续不用沿用，样本 {index}",
    "{subject}：本轮调试临时采用{object}，完成后恢复默认，样本 {index}",
    "{subject}：这个草稿只服务当前排查，先不用长期保存，样本 {index}",
    "{subject}：会议前临时记一下{object}，过期后不再使用，样本 {index}",
)

_INFERENCE_PATTERNS = (
    "{subject}：助手推断用户可能喜欢{object}，样本 {index}",
    "{subject}：从回答中猜到用户倾向于{object}，样本 {index}",
    "{subject}：模型感觉用户大概希望{context}{object}，样本 {index}",
    "{subject}：看起来用户应该偏向{object}，但没有确认，样本 {index}",
)

_DUPLICATE_PATTERNS = (
    "{subject}：以后请记住用户偏好，{context}要{object}，样本 {index}",
    "{subject}：长期偏好是{context}{object}，样本 {index}",
    "{subject}：后续同类任务请继续{object}，并保持中文简洁，样本 {index}",
    "{subject}：用户偏好可以概括为{context}{object}，样本 {index}",
)

_CONFLICT_PATTERNS = (
    "{subject}：长期项目约定改为不要{object}，而是先完整铺开解释，样本 {index}",
    "{subject}：优先级调整为先忽略旧的{object}规则，样本 {index}",
    "{subject}：以后在{context}不要再{object}，样本 {index}",
    "{subject}：新规则只在部分场景覆盖旧规则，{context}先完整解释再说结论，样本 {index}",
)


def build_write_governance_candidates(
    case_set: str = "all",
    limit: int = 0,
) -> list[WriteGovernanceCandidate]:
    normalized = str(case_set or "all").strip().lower()
    if normalized not in {"all", "common", "hard"}:
        raise ValueError("case_set must be 'all', 'common', or 'hard'")
    sets = ("common", "hard") if normalized == "all" else (normalized,)
    candidates: list[WriteGovernanceCandidate] = []
    for current_set in sets:
        for category, set_subtypes in CATEGORY_SUBTYPES.items():
            for subtype in set_subtypes[current_set]:
                for index in range(1, 21):
                    candidates.append(_build_candidate(current_set, category, subtype, index))
    if limit > 0:
        return candidates[:limit]
    return candidates


def _build_candidate(
    case_set: str,
    category: str,
    subtype: str,
    index: int,
) -> WriteGovernanceCandidate:
    candidate_id = f"{case_set}_{category}_{subtype}_{index:02d}"
    summary = _summary(case_set, category, subtype, index)
    expected = "write" if category in {"valuable_preference", "stable_fact"} else "block"
    if category == "conflict":
        expected = "review"
    return WriteGovernanceCandidate(
        id=candidate_id,
        case_set=case_set,
        category=category,
        subtype=subtype,
        summary=summary,
        expected_action=expected,
        existing_memories=_existing_memories(candidate_id, category, subtype, index, summary),
    )


def _summary(case_set: str, category: str, subtype: str, index: int) -> str:
    subject = _pick(_VARIANT_SUBJECTS, index, salt=len(subtype))
    obj = _pick(_VARIANT_OBJECTS, index, salt=len(category))
    context = _pick(_VARIANT_CONTEXTS, index, salt=len(case_set) + len(subtype))
    if category in {"valuable_preference", "stable_fact"}:
        patterns = _COMMON_PATTERNS if case_set == "common" else _HARD_WRITE_PATTERNS
    elif category == "temporary":
        patterns = _TEMPORARY_PATTERNS
    elif category == "assistant_inference":
        patterns = _INFERENCE_PATTERNS
    elif category == "duplicate":
        patterns = _DUPLICATE_PATTERNS
    elif category == "conflict":
        patterns = _CONFLICT_PATTERNS
    else:
        raise ValueError(f"unknown category: {category}")
    pattern = _pick(patterns, index, salt=len(subtype) + len(category))
    difficulty = "常见" if case_set == "common" else "难例"
    return (
        f"{difficulty}/{category}/{subtype}："
        + pattern.format(subject=subject, context=context, object=obj, index=index)
    )


def _existing_memories(
    candidate_id: str,
    category: str,
    subtype: str,
    index: int,
    summary: str,
) -> tuple[dict[str, object], ...]:
    if category == "duplicate":
        existing_summary = summary
        if "难例/" in summary:
            subject = _pick(_VARIANT_SUBJECTS, index, salt=len(subtype))
            obj = _pick(_VARIANT_OBJECTS, index, salt=len(category))
            context = _pick(_VARIANT_CONTEXTS, index, salt=len(subtype))
            existing_summary = f"难例/{category}/{subtype}：{subject}：后续同类任务请{context}{obj}，样本 {index}"
        return (
            {
                "id": f"{candidate_id}_existing",
                "summary": existing_summary,
                "memory_type": "preference",
            },
        )
    if category == "conflict":
        subject = _pick(_VARIANT_SUBJECTS, index, salt=len(subtype))
        obj = _pick(_VARIANT_OBJECTS, index, salt=len(category))
        context = _pick(_VARIANT_CONTEXTS, index, salt=len(subtype))
        existing_summary = f"{subject}：长期项目约定是{context}{obj}，样本 {index}"
        return (
            {
                "id": f"{candidate_id}_existing",
                "summary": existing_summary,
                "memory_type": "procedure",
            },
        )
    return ()


def _pick(values: tuple[str, ...], index: int, *, salt: int) -> str:
    return values[(index + salt) % len(values)]

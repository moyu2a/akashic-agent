from __future__ import annotations
from typing import Any, cast

from pathlib import Path
from types import SimpleNamespace

from agent.core.prompt_block import (
    ActiveSkillsPromptBlock,
    BehaviorRulesPromptBlock,
    IdentityPromptBlock,
    LongTermMemoryPromptBlock,
    MemoryBlockPromptBlock,
    RecentContextPromptBlock,
    SelfModelPromptBlock,
    SessionContextPromptBlock,
    SkillsCatalogPromptBlock,
    SystemPromptBuilder,
    TurnContext,
)
from agent.persona import (
    CASUAL_PERSONALITY_RULES,
    PERSONALITY_RULES,
    WORK_PERSONALITY_RULES,
    get_personality_rules,
)
from prompts.agent import build_agent_static_identity_prompt


class _Memory:
    def read_profile(self) -> str:
        return "memory block"

    def read_self(self) -> str:
        return "self note"


class _Skills:
    def get_always_skills(self) -> list[str]:
        return ["always"]

    def load_skills_for_context(self, names: list[str]) -> str:
        return "\n".join(names)

    def build_skills_summary(self) -> str:
        return "summary"


def test_system_prompt_builder_uses_prompt_blocks_and_static_cache(tmp_path: Path):
    builder = SystemPromptBuilder(
        [
            IdentityPromptBlock(render_fn=lambda **_: "identity"),
            MemoryBlockPromptBlock(),
        ]
    )
    ctx = TurnContext(
        workspace=tmp_path,
        memory=cast(Any, _Memory()),
        skills=cast(Any, _Skills()),
        skill_names=[],
        channel=None,
        chat_id=None,
        retrieved_memory_block="retrieved",
    )

    first = builder.build(ctx)
    second = builder.build(ctx)

    assert first.system_prompt == "identity\n\n---\n\nretrieved"
    assert [item.name for item in first.system_sections] == ["identity", "retrieved_memory"]
    assert second.debug_breakdown[0].cache_hit is True


def test_system_prompt_builder_respects_disabled_sections(tmp_path: Path):
    builder = SystemPromptBuilder(
        [
            IdentityPromptBlock(render_fn=lambda **_: "identity"),
            MemoryBlockPromptBlock(),
        ]
    )
    ctx = TurnContext(
        workspace=tmp_path,
        memory=cast(Any, _Memory()),
        skills=cast(Any, _Skills()),
        skill_names=[],
        channel=None,
        chat_id=None,
        retrieved_memory_block="retrieved",
    )

    built = builder.build(ctx, disabled_sections={"retrieved_memory"})

    assert built.system_prompt == "identity"
    assert [item.name for item in built.system_sections] == ["identity"]


def test_static_identity_prompt_is_not_hardcoded_to_specific_user(tmp_path: Path):
    prompt = build_agent_static_identity_prompt(workspace=tmp_path)

    assert "花月的长期 AI 伙伴" not in prompt
    assert "用户的长期 AI 伙伴" in prompt


def test_personality_rules_alias_keeps_casual_default():
    assert PERSONALITY_RULES == CASUAL_PERSONALITY_RULES
    assert get_personality_rules() == CASUAL_PERSONALITY_RULES


def test_work_personality_rules_define_task_boundaries():
    assert get_personality_rules("work") == WORK_PERSONALITY_RULES
    assert "工作模式" in WORK_PERSONALITY_RULES
    assert "任务正确性优先" in WORK_PERSONALITY_RULES
    assert "关键术语" in WORK_PERSONALITY_RULES
    assert "<read_file>" in WORK_PERSONALITY_RULES
    assert "<search>" in WORK_PERSONALITY_RULES
    assert "<tool>" in WORK_PERSONALITY_RULES


def test_static_identity_prompt_defaults_to_casual_persona(tmp_path: Path):
    prompt = build_agent_static_identity_prompt(workspace=tmp_path)

    assert "先接住，再展开" in prompt
    assert "## 工作模式" not in prompt


def test_static_identity_prompt_can_render_work_persona(tmp_path: Path):
    prompt = build_agent_static_identity_prompt(workspace=tmp_path, persona_mode="work")

    assert "## 工作模式" in prompt
    assert "任务正确性优先" in prompt
    assert "不要写成工具调用占位" in prompt
    assert "<read_file>" in prompt
    assert "先接住，再展开" not in prompt


def test_identity_prompt_block_can_render_work_persona(tmp_path: Path):
    block = IdentityPromptBlock(persona_mode="work")
    ctx = TurnContext(
        workspace=tmp_path,
        memory=cast(Any, _Memory()),
        skills=cast(Any, _Skills()),
        skill_names=[],
        channel=None,
        chat_id=None,
        retrieved_memory_block="retrieved",
    )

    prompt = block.render(ctx)

    assert prompt is not None
    assert "## 工作模式" in prompt
    assert "先接住，再展开" not in prompt


def test_prompt_block_priorities_leave_spacing_for_future_inserts():
    priorities = [
        (IdentityPromptBlock.label, IdentityPromptBlock.priority),
        (BehaviorRulesPromptBlock.label, BehaviorRulesPromptBlock.priority),
        (SkillsCatalogPromptBlock.label, SkillsCatalogPromptBlock.priority),
        (SelfModelPromptBlock.label, SelfModelPromptBlock.priority),
        (LongTermMemoryPromptBlock.label, LongTermMemoryPromptBlock.priority),
        (SessionContextPromptBlock.label, SessionContextPromptBlock.priority),
        (RecentContextPromptBlock.label, RecentContextPromptBlock.priority),
        (ActiveSkillsPromptBlock.label, ActiveSkillsPromptBlock.priority),
        (MemoryBlockPromptBlock.label, MemoryBlockPromptBlock.priority),
    ]

    assert priorities == [
        ("identity", 10),
        ("behavior_rules", 15),
        ("skills_catalog", 20),
        ("self_model", 30),
        ("long_term_memory", 35),
        ("session_context", 40),
        ("recent_context", 45),
        ("active_skills", 50),
        ("retrieved_memory", 55),
    ]

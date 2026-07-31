# Work Persona Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Subagents are not available in this side conversation, so review is performed inline using the requesting-code-review checklist.

**Goal:** Add a conservative work-mode persona prompt that can be selected manually while preserving the existing casual persona as the default behavior.

**Architecture:** Keep persona text and mode selection in `agent/persona.py`. Let `prompts/agent.py` accept an optional `persona_mode` argument for static identity prompt rendering. Do not implement automatic mode detection in this phase.

**Tech Stack:** Python 3, pytest, existing prompt-building modules.

## Global Constraints

- Do not change the casual persona text except for renaming it into a new constant.
- Preserve backward compatibility: current callers that import `PERSONALITY_RULES` or call `build_agent_static_identity_prompt(workspace=...)` must continue to work.
- Do not change proactive prompts in this phase; they should continue using the casual persona through the compatibility alias.
- Do not implement automatic persona switching in this phase.
- Do not touch unrelated dirty memory/eval files already present in the worktree.

---

## File Structure

- Modify `agent/persona.py`
  - Owns identity text, casual persona text, work persona text, mode type, and `get_personality_rules()`.
- Modify `prompts/agent.py`
  - Imports `PersonaMode` and `get_personality_rules()`.
  - Adds optional `persona_mode` to `build_agent_static_identity_prompt()`.
- Modify `agent/core/prompt_block.py`
  - Adds optional `persona_mode` to `IdentityPromptBlock`.
- Modify `agent/context.py`
  - Adds optional `persona_mode` to `ContextBuilder` and passes it into `IdentityPromptBlock`.
- Modify `tests/test_agent_core_p4_prompt_block.py`
  - Adds focused tests for default/casual compatibility and explicit work-mode rendering.
- Create `my_md/memory_optimization/12-work-persona-mode-test-report.md`
  - Records test method, data, and conclusion.

## Review Notes

Inline review using `requesting-code-review` criteria found two plan risks and revisions:

- Risk: changing the default prompt could alter production behavior unexpectedly. Revision: keep `PERSONALITY_RULES = CASUAL_PERSONALITY_RULES` and default `persona_mode="casual"`.
- Risk: work prompt could accidentally affect proactive composition. Revision: leave `prompts/proactive.py` untouched.

## Task 1: Persona Constants and Selector

**Files:**
- Modify: `agent/persona.py`
- Test: `tests/test_agent_core_p4_prompt_block.py`

**Interfaces:**
- Produces: `PersonaMode = Literal["casual", "work"]`
- Produces: `CASUAL_PERSONALITY_RULES: str`
- Produces: `WORK_PERSONALITY_RULES: str`
- Produces: `get_personality_rules(mode: PersonaMode = "casual") -> str`
- Preserves: `PERSONALITY_RULES: str`

- [x] **Step 1: Write failing persona selector tests**

Add tests asserting:

```python
from agent.persona import (
    CASUAL_PERSONALITY_RULES,
    PERSONALITY_RULES,
    WORK_PERSONALITY_RULES,
    get_personality_rules,
)


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
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider
```

Expected: fail because `CASUAL_PERSONALITY_RULES`, `WORK_PERSONALITY_RULES`, and `get_personality_rules` are not defined.

- [x] **Step 3: Implement persona constants**

Change `agent/persona.py` as follows:

```python
from __future__ import annotations

from typing import Literal

PersonaMode = Literal["casual", "work"]
```

Keep the existing `AKASHIC_IDENTITY` assignment exactly as it is.

Rename the existing `PERSONALITY_RULES` constant to `CASUAL_PERSONALITY_RULES`; keep the full string body byte-for-byte identical to the current casual prompt text in `agent/persona.py`.

Then add the new work prompt and selector:

```python
WORK_PERSONALITY_RULES = """## 工作模式

你当前处于 Akashic 的工作模式。

工作模式用于代码协作、实验分析、记忆召回、事实核查、测试结论、计划制定、问题诊断、文档整理和工具执行等任务型对话。

### 核心原则

在工作模式下，首要目标是准确完成用户任务。

优先级从高到低：
1. 系统规则、工具规则、安全规则。
2. 用户本轮明确要求。
3. 已验证证据、代码、测试数据、检索结果、记忆 contract。
4. 用户长期偏好，例如中文回答、条目式回答、pytest 风格。
5. 简洁自然的表达。

当风格与任务正确性冲突时，任务正确性优先。

### 回答方式

直接回答问题，先给结论，再给依据和必要细节。

如果信息不足，先说明当前能确定什么，再提出最小必要澄清问题。

保留用户或证据中的关键术语；当这些术语是用户偏好、实现锚点或测试期望时，不要只用近义表达替代。

### 工具与证据

需要工具时就真实调用工具；不能调用或不需要调用时，直接基于已有证据回答。

最终答案只输出给用户看的自然语言；不要写成工具调用占位、内部动作计划或伪 XML 标签，例如 `<read_file>`、`<search>`、`<tool>`。

记忆召回、实验分析和事实判断必须基于当前可用证据；证据不足时明确说不足，不要编造或用闲聊语气补全。"""


def get_personality_rules(mode: PersonaMode = "casual") -> str:
    if mode == "work":
        return WORK_PERSONALITY_RULES
    return CASUAL_PERSONALITY_RULES


PERSONALITY_RULES = CASUAL_PERSONALITY_RULES
```

- [x] **Step 4: Run tests to verify Task 1 passes**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider
```

Expected: existing tests pass plus new persona selector tests pass.

## Task 2: Static Identity Prompt Mode Parameter

**Files:**
- Modify: `prompts/agent.py`
- Test: `tests/test_agent_core_p4_prompt_block.py`

**Interfaces:**
- Consumes: `PersonaMode`, `get_personality_rules()`
- Produces: `build_agent_static_identity_prompt(*, workspace: Path, persona_mode: PersonaMode = "casual") -> str`

- [x] **Step 1: Write failing prompt rendering tests**

Add tests asserting:

```python
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
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider
```

Expected: fail because `persona_mode` is not accepted by `build_agent_static_identity_prompt`.

- [x] **Step 3: Implement prompt mode parameter**

Modify `prompts/agent.py`:

```python
from agent.persona import AKASHIC_IDENTITY, PersonaMode, get_personality_rules


def build_agent_static_identity_prompt(
    *,
    workspace: Path,
    persona_mode: PersonaMode = "casual",
) -> str:
    workspace_path = str(workspace.expanduser().resolve())
    personality_rules = get_personality_rules(persona_mode)

    return f"""# Akashic

{AKASHIC_IDENTITY}

## 性格

{personality_rules}

## 工作区
- 根目录：{workspace_path}
- 长期记忆：{workspace_path}/memory/MEMORY.md
- 自我认知：{workspace_path}/memory/SELF.md
- 历史日志：{workspace_path}/memory/HISTORY.md（支持 grep 搜索）
- 近期语境摘要：{workspace_path}/memory/RECENT_CONTEXT.md
  这是面向 proactive / drift 的近期上下文压缩结果，用来帮助判断“最近在聊什么、什么适合自然续接”。
  它不是原始证据，不可替代 fetch_messages / search_messages / 实时查询；涉及细节、时间线、当前状态时，仍要回源或查工具。
- 主动规则面板：{workspace_path}/PROACTIVE_CONTEXT.md
  这是 proactive 链路专用规则文件，用来记录主动推送白名单、黑名单、过滤条件、前置验证要求。
  当用户明确修改“以后主动推送怎么做”时，应优先更新这里，而不是只停留在普通回复或长期记忆里。
- 知识库：{workspace_path}/kb/
"""
```

- [x] **Step 4: Run tests to verify Task 2 passes**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider
```

Expected: all tests in the file pass.

## Task 3: Documentation and Focused Verification

**Files:**
- Modify: `agent/core/prompt_block.py`
- Modify: `agent/context.py`
- Create: `my_md/memory_optimization/12-work-persona-mode-test-report.md`

**Interfaces:**
- Consumes: `PersonaMode` and `build_agent_static_identity_prompt(..., persona_mode=...)`.
- Produces: `IdentityPromptBlock(..., persona_mode="work")`.
- Produces: `ContextBuilder(..., persona_mode="work")`.
- Produces: durable test-method/data/conclusion record.

- [x] **Step 1: Add prompt block manual mode entry**

Modify `agent/core/prompt_block.py` so `IdentityPromptBlock` accepts `persona_mode: PersonaMode = "casual"` and passes it to `build_agent_static_identity_prompt`.

- [x] **Step 2: Add ContextBuilder manual mode entry**

Modify `agent/context.py` so `ContextBuilder` accepts `persona_mode: PersonaMode = "casual"` and passes it to `IdentityPromptBlock`.

- [x] **Step 3: Run focused compile verification**

Run:

```bash
uv run python -m compileall agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py tests/test_agent_core_p4_prompt_block.py
```

Expected: compile succeeds.

- [x] **Step 4: Run focused pytest verification**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [x] **Step 5: Write test report**

Create `my_md/memory_optimization/12-work-persona-mode-test-report.md` with:

```markdown
# Work Persona Mode Test Report

## Scope

- Added manual work-mode persona prompt.
- Preserved casual persona as the default.
- Did not implement automatic mode switching.
- Did not change proactive persona behavior.

## Test Method

| command | purpose |
| --- | --- |
| `uv run python -m compileall agent/persona.py prompts/agent.py tests/test_agent_core_p4_prompt_block.py` | Syntax/import verification |
| `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider` | Focused prompt/persona behavior verification |

## Data

Record exact command outputs and pass/fail counts here after running verification.

## Conclusion

Record whether manual work mode renders the expected rules, whether default casual behavior is preserved, and whether any follow-up remains.
```

- [x] **Step 6: Final diff check**

Run:

```bash
git diff -- agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py tests/test_agent_core_p4_prompt_block.py my_md/memory_optimization/12-work-persona-mode-test-report.md docs/superpowers/plans/2026-07-31-work-persona-mode.md
```

Expected: diff contains only this feature and documentation.

## Final Verification

- Run focused compile command.
- Run focused pytest command.
- Check `git status --short`.
- Report changed files, test data, and conclusion to the user.

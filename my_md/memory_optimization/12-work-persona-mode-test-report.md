# Work Persona Mode Test Report

## Scope

- Added a manual work-mode persona prompt.
- Added a manual prompt-block/context entry for selecting work mode.
- Preserved the existing casual persona as the default.
- Did not implement automatic mode switching.
- Did not change proactive persona behavior.

## Method

The change used a focused TDD cycle:

1. Added tests for persona selector exports and work-mode prompt rendering.
2. Ran the focused pytest command before implementation and confirmed the expected import failure.
3. Implemented the minimal persona constants, selector, optional `persona_mode` parameter, and prompt-block/context entry.
4. Re-ran focused pytest and compile verification.

## Data

| step | command | result |
| --- | --- | --- |
| red test | `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider` | Failed during collection with `ImportError: cannot import name 'CASUAL_PERSONALITY_RULES' from 'agent.persona'` |
| prompt-block red test | `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider` | Failed with `TypeError: IdentityPromptBlock.__init__() got an unexpected keyword argument 'persona_mode'` |
| focused pytest | `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py -q -p no:cacheprovider` | `9 passed in 0.20s` |
| context compatibility pytest | `uv run --with pytest --with pytest-asyncio pytest tests/test_support_modules.py -q -p no:cacheprovider` | `12 passed in 3.17s` |
| compile | `uv run python -m compileall agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py tests/test_agent_core_p4_prompt_block.py` | Exit code 0 |

## Verified Behavior

| behavior | result |
| --- | --- |
| `PERSONALITY_RULES` compatibility alias remains casual | Passed |
| `get_personality_rules()` defaults to casual | Passed |
| `get_personality_rules("work")` returns the work prompt | Passed |
| default static identity prompt still contains casual "先接住，再展开" | Passed |
| explicit `persona_mode="work"` renders "工作模式" | Passed |
| work prompt contains key-term retention rule | Passed |
| work prompt contains final-answer tool markup guard for `<read_file>`, `<search>`, `<tool>` | Passed |
| work prompt does not include the casual "先接住，再展开" rule | Passed |
| `IdentityPromptBlock(persona_mode="work")` renders work mode | Passed |

## Conclusion

Manual work-mode persona selection is now available at the prompt rendering layer through `build_agent_static_identity_prompt(..., persona_mode="work")`, `IdentityPromptBlock(persona_mode="work")`, and `ContextBuilder(..., persona_mode="work")`.

The production default remains unchanged because existing callers still use the casual prompt through `persona_mode="casual"` and the `PERSONALITY_RULES` compatibility alias. Proactive prompt composition was not changed in this phase.

This change addresses the prompt-level cause of task answers drifting into casual openings or pseudo tool markup. It does not yet enable automatic mode classification or apply work mode by default to memory eval/runtime turns; those should be handled as a separate follow-up after deciding the routing policy.

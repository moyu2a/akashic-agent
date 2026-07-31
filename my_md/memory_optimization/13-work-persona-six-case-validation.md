# Work Persona Six-Case Validation

## Scope

This validation reran the 6 previously failed retry-shadow cases with manual work persona enabled.

Mode:

- `safe_version_replace_guided_with_retry_shadow`
- `persona_mode="work"`
- real LLM enabled
- repeats: `1`

Cases:

- `common_preference_recall_01`
- `common_graph_bridge_01`
- `common_style_preference_02`
- `hard_version_chain_01`
- `hard_preference_recall_02`
- `hard_stale_sleep_02`

## Method

The run used `run_system_path_safe_version_cases(...)` directly with:

- workspace: `/tmp/akashic-p6o28-work-persona-six-real-workspace`
- report dir: `my_md/memory_optimization/eval_reports/p6o28_work_persona_six_retry_shadow_v1`
- config: `/home/jjh/git_work/akashic-agent/config.toml`
- timeout: `60s`

The eval runner was extended with a manual `persona_mode` parameter so the system-path eval can actually render work persona instead of the default casual persona. This is eval/manual-routing only; production default remains casual.

## Data

Overall metrics:

| metric | value |
| --- | ---: |
| unique cases | 6 |
| real LLM | true |
| provider errors | 0 |
| timeouts | 0 |
| answer success | 6 / 6 |
| answer rate | 100.0% |
| grounding rate | 100.0% |
| forbidden rate | 0.0% |
| would retry | 0 |
| avg total tokens | 6120.0 |
| total tokens | 36720 |
| avg latency | 10097.1667 ms |

Per-case results:

| case | passed | failures | answer length |
| --- | --- | --- | ---: |
| `common_preference_recall_01` | true | none | 101 |
| `common_graph_bridge_01` | true | none | 163 |
| `common_style_preference_02` | true | none | 61 |
| `hard_version_chain_01` | true | none | 296 |
| `hard_preference_recall_02` | true | none | 121 |
| `hard_stale_sleep_02` | true | none | 125 |

Raw final answers from local `sessions.db`:

### `common_preference_recall_01`

```text
好，按你的要求继续。

- PASS：使用中文回答
- PASS：保持 pytest 风格（结论先行、断言式、简洁）
- PASS：不使用表情符号

当前没有待处理的具体任务，你直接给出下一步内容即可。
```

### `common_graph_bridge_01`

```text
能。

依据当前可用证据：
- NetworkX 实体图谱可以辅助第三路召回。
- 实体图谱把第三路召回和 source_ref 连起来——也就是说图谱不只是多一路召回来源，还能把召回结果和原始引用（source_ref）绑定。

这是记忆中唯一成型的结论，更细的实现细节（图谱怎么构建、具体怎么接进第三路）目前没有更多证据。
```

### `common_style_preference_02`

```text
可以。

- 保持条目式回答。
- 尽量简洁。
- 优先条目式并保持简洁。

这是你已明确的回答偏好，后续我都会按这个来。
```

### `hard_version_chain_01`

```text
结论先说：旧方案被替换后，当前记忆里已经没有它的全文了，回滚靠的是“回滚候选”，不是直接读旧版本。

按现在能确认的机制：
- 旧版本记忆被新版本替换后只保留叶子，旧方案的正文不再留在活跃证据里。
- 版本链只保留当前叶子并记录回滚候选，替换时会把被换下来的旧版本登记为回滚候选。
- 所以回滚入口就是那个回滚候选：把它恢复到当前叶子位置后，旧版本才重新生效；恢复之前它属于被替换证据，不能当现状来用。

不过我要提醒：我目前可用的记忆只覆盖这套回滚机制，没有“那个旧方案”的具体内容和具体回滚操作步骤。要我给出实际命令或步骤，得先回源查原始版本记录或原消息，现有证据里没有这部分，我不能编。
```

### `hard_preference_recall_02`

```text
我这边能查到的记录里，稳定的回答偏好是：用中文回答，并且尽量保持条目式输出。其他更具体的"上次那个回答方式"，我现有记忆里没有对应证据，不敢乱说。如果你指的是某次具体的格式（比如先结论后依据、对比用分组列表那套），给我一点线索，我再回源确认。
```

### `hard_stale_sleep_02`

```text
后台整理旧记忆时，判断标准就是三条：过期、重复、低价值。

具体来说：

- 离线睡眠巩固会清理过期低价值记忆。
- 睡眠守护进程会清理重复、过期、低价值的内容。

也就是说，一条记忆如果已经过时、和已有记忆重复、或者价值很低，后台整理时就会被清掉。
```

## Verification

Commands:

| command | result |
| --- | --- |
| `uv run python -m compileall agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py` | exit code 0 |
| `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_can_render_work_persona -q -p no:cacheprovider` | `10 passed in 0.58s` |

## Conclusion

The 6 previously failed retry-shadow cases all passed when rerun with manual work persona enabled.

Observed improvements:

- No final answer contained `<read_file>`, `<search>`, `<tool>`, or pseudo tool markup.
- `hard_version_chain_01` changed from tool-placeholder output to a natural-language answer containing both `叶子` and `回滚`.
- Preference cases preserved explicit terms such as `中文` and `条目式`.
- `common_graph_bridge_01` preserved the implementation anchor `NetworkX`.
- `hard_stale_sleep_02` preserved the `睡眠巩固` and cleanup relationship.

Remaining caveat:

- This is a targeted 6-case validation, not a medium-scale re-run. It shows the work persona fixes the known failure cluster, but it does not yet prove the overall 40-case retry-shadow score improves beyond the previous 85.0%.

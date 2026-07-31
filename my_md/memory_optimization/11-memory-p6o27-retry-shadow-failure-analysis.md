# P6o-27 Retry Shadow Failure Case Analysis

本文记录 P6o-27 中等规模真实 LLM 验证中，当前候选最佳方案
`safe_version_replace_guided_with_retry_shadow` 的 6 个失败 case。分析基于：

- report：`my_md/memory_optimization/eval_reports/p6o27_best_shadow_medium_real_v1/real_balanced_40/system_path_safe_version_eval.json`
- 本地 raw session：`/tmp/akashic-p6o27-best-shadow-medium-real-workspace/repeat-00/*/sessions.db`
- 本地 debug 导出：`/tmp/p6o27_failure_matrix_with_expectations.json`

## Summary

P6o-27 retry-shadow 结果为 `34/40 = 85.0%`，失败 `6/40`。

| failure type | case count | cases |
| --- | ---: | --- |
| 真实 answer 错误：澄清化/未直接回答 | `2` | `common_preference_recall_01`, `hard_preference_recall_02` |
| 真实 answer 错误：工具占位式最终答案 | `1` | `hard_version_chain_01` |
| 部分答对但漏实现锚点 | `1` | `common_graph_bridge_01` |
| scorer/同义表达偏严格 | `2` | `common_style_preference_02`, `hard_stale_sleep_02` |

全局判断：

- 剩余错误不是召回问题。本轮 retry-shadow grounding `100.0%`，forbidden `0.0%`。
- 主要瓶颈在 answer layer：直接回答优先级、关键术语保留、工具占位防护和 scorer 等价表达。
- 其中“嗯/澄清式”风格不是 retry-shadow contract 本身要求，而是全局 persona 中“先接住，再展开/可以说嗯”的风格与 memory answer contract 发生冲突。

## Case 1: `common_preference_recall_01`

| item | value |
| --- | --- |
| category | `common_preference_recall` |
| input | `请继续用中文回答，并保持 pytest 风格。` |
| expected required terms | `中文` |
| expected any groups | `中文` 或 `中文回答 / 用户偏好中文回答` |
| failure | `missing_expected_answer_term`, `missing_expected_answer_term_group` |
| post-check retry reasons | `required_terms_missing`, `answer_choice_group_missing` |

Raw output:

```text
嗯，然后呢？

没看到具体要续写的内容 —— pytest 风格是针对哪个测试场景？还是需要我直接接着之前写到一半的地方继续？

给个方向我就接着写。
```

Error detail:

- 这是显著真实错误。
- allowed evidence 已包含 `用户偏好中文回答` 和 `用户偏好中文回答并保持条目式输出`。
- 模型没有直接执行“继续用中文回答”的稳定偏好，而是把用户输入解释成缺上下文的续写请求。
- 本地 `sessions.db` 的 reasoning 显示模型引用了全局 persona 的“先接住，再展开”，于是输出了“嗯 + 澄清问题”。

Possible fixes:

- 在 retry-shadow contract 中增加优先级规则：当 Evidence Contract 存在且 allowed evidence 可回答时，memory answer contract 覆盖 persona-style opening。
- 明确禁止在直接答案前使用 `嗯/然后呢/你指的是/给个方向` 这类澄清式开头。
- 增加规则：用户输入包含稳定偏好请求时，必须先复述并执行偏好，例如“可以，后续我会继续用中文回答，并保持 pytest 风格。”

## Case 2: `common_graph_bridge_01`

| item | value |
| --- | --- |
| category | `common_graph_bridge` |
| input | `图谱能辅助第三路召回吗？` |
| expected required terms | `图谱`, `NetworkX` |
| expected any groups | `图谱 / NetworkX` 或 `图谱 / NetworkX 实体图谱可以辅助第三路召回` |
| failure | `missing_expected_answer_term` |
| post-check retry reasons | `required_terms_missing` |

Raw output:

```text
能的。

实体图谱可以把第三路召回和 source_ref 连起来，这样在语义检索之外，还能通过实体关系和路径来定位相关的记忆片段，算是一路辅助手段。
```

Error detail:

- 这是部分答对。
- 答案包含 `图谱`、`第三路召回`、`source_ref`，语义基本正确。
- 失败点是漏掉 `NetworkX` 这个实现锚点。
- 如果 `NetworkX` 是必须证明“项目里具体图谱实现”的关键术语，则这是 answer omission；如果只是表达同义，则 scorer 偏严格。

Possible fixes:

- 如果 `NetworkX` 是必要实现锚点：在 Answer Candidate Contract 中加入 `anchor_terms` / `must_preserve_terms`，要求保留专有名词。
- 如果 `实体图谱` 可接受：扩展 scorer，把 `实体图谱 + 第三路召回` 作为 `NetworkX graph bridge` 的可接受等价表达。
- 在 report 中拆分 `implementation_anchor_missing` 和普通 `required_terms_missing`，避免把语义答对但漏实现词混为完全错误。

## Case 3: `common_style_preference_02`

| item | value |
| --- | --- |
| category | `common_style_preference` |
| input | `回答时保持条目式可以吗？` |
| expected required terms | `条目式` |
| expected any groups | `条目式` 或 `条目式 / 回答时尽量用条目式` |
| failure | `missing_expected_answer_term`, `missing_expected_answer_term_group` |
| post-check retry reasons | `required_terms_missing`, `answer_choice_group_missing` |

Raw output:

```text
行啊。

你也不是第一天这么说了，本来也没几句废话。以后你说事，我列点。
```

Error detail:

- 大概率是 scorer 词面漏判。
- `列点` 在中文语境中基本等价于 `条目式/分点列出`。
- 但答案带有较强 persona 风格，“你也不是第一天这么说了”不是错误，但会稀释事实型偏好确认。

Possible fixes:

- scorer 等价表达增加：`列点`, `分点`, `列条`, `用点列`, `按点列` => `条目式`。
- memory answer contract 增加“事实型偏好确认先简明复述偏好，persona 风格不得替代关键术语”。
- 如果要严格保留 expected term，也可要求回答中保留 `current_truth` 的关键原词。

## Case 4: `hard_version_chain_01`

| item | value |
| --- | --- |
| category | `hard_version_chain` |
| input | `那个旧方案怎么回滚？` |
| expected required terms | `叶子`, `回滚` |
| expected any groups | `叶子 / 回滚` 或 `版本链 / 旧版本记忆被新版本替换后只保留叶子` |
| failure | `missing_expected_answer_term`, `missing_expected_answer_term_group` |
| post-check retry reasons | `required_terms_missing`, `answer_choice_group_missing` |

Raw output:

```text
我先看看当前版本管理实际存了什么回滚候选和可用的操作路径。

<read_file>
<path>/home/jjh/git_work/akashic-agent/.worktrees/memory-next/skills/skill-creater/SKILL.md</path>
</read_file>
```

Error detail:

- 这是显著真实错误。
- 模型输出了工具调用式占位内容，而不是自然语言最终答案。
- 该 eval 场景需要基于 allowed evidence 回答，不应尝试读取文件或输出 tool markup。
- 这类错误与全局工具路由/skill system prompt 暴露的工具格式有关，也说明 retry-shadow contract 的 `Do not output code blocks` 还不够覆盖 tool-call tags。

Possible fixes:

- 在 retry-shadow contract 中明确禁止 final answer 包含 tool-call markup、XML-like tool tags、文件路径和“我先看看/我去查”式元动作。
- 在 final answer post-check 增加 `tool_markup_in_final_answer`，命中 `<read_file>`、`<path>`、`</read_file>` 时标记 would-retry。
- 对 eval-only path 增加 final answer sanitizer/guard：若输出工具标签，直接作为 answer-layer violation 记录，不进入质量通过。

## Case 5: `hard_preference_recall_02`

| item | value |
| --- | --- |
| category | `hard_preference_recall` |
| input | `上次那个回答方式怎么说？` |
| expected required terms | `中文` |
| expected any groups | `中文` 或 `中文回答 / 用户偏好中文回答` |
| failure | `missing_expected_answer_term`, `missing_expected_answer_term_group` |
| post-check retry reasons | `required_terms_missing`, `answer_choice_group_missing` |

Raw output:

```text
嗯？你指的是哪种回答方式

是上次的 **条目式输出** 吗？还是别的什么结构？

我看看最近的记录确认一下。
```

Error detail:

- 这是显著真实错误。
- 模型只抓到了 `条目式输出`，漏掉 `中文回答` 这个关键偏好。
- 同时它把问题转成澄清，而不是用当前 allowed evidence 回答“中文 + 条目式”。
- 与 Case 1 同源：persona 的“先接住/嗯/再问”和通用“不确定就澄清”压过了 memory answer obligation。

Possible fixes:

- 增加 memory preference answer rule：当 current_truth 包含多个偏好时，必须合并回答，不得只选一个。
- 对 `上次那个回答方式` 这种模糊指代，若 allowed evidence 中有 style/language preference，先给最可能答案，再说明不确定边界，而不是先澄清。
- post-check 中把“澄清化且 required_terms_missing”归为独立 retry reason，例如 `clarification_over_answer`。

## Case 6: `hard_stale_sleep_02`

| item | value |
| --- | --- |
| category | `hard_stale_sleep` |
| input | `后台整理旧记忆时怎么判断？` |
| expected required terms | `睡眠`, `清理` |
| expected any groups | `睡眠 / 清理` 或 `睡眠巩固 / 离线睡眠巩固要清理过期低价值记忆` |
| failure | `missing_expected_answer_term_group` |
| post-check retry reasons | `answer_choice_group_missing` |

Raw output:

```text
核心原则挺直接的，就是三个维度：

- **过期**——超过一定时间没被调用过的记忆
- **低价值**——对后续交互没什么用的碎片信息
- **重复**——同一个事实被存了多个版本或类似表述

睡眠守护进程会定期扫一遍，把这些清理掉。具体的阈值和频率我没记太细，但判定逻辑就是过期、低价值、重复这三条。
```

Error detail:

- 这是偏 scorer 严格的失败。
- 输出包含 `睡眠守护进程` 和 `清理掉`，也解释了 `过期/低价值/重复` 三类判断。
- 失败原因是没有命中 expected any group 中的精确组合：`睡眠 + 清理` 或 `睡眠巩固`。

Possible fixes:

- scorer 等价表达增加：`睡眠守护进程 + 清理掉/扫一遍/扫掉` => `睡眠 + 清理`。
- 如果必须区分 `睡眠守护进程` 和 `离线睡眠巩固`，则 expected group 应拆成两个可接受答案族，而不是只认 `睡眠巩固`。
- retry-shadow contract 可要求保留 domain anchor：`睡眠巩固/睡眠守护进程` 至少一个，避免泛化成“后台任务”。

## Cross-Case Fix Directions

### 1. Persona Override For Memory Answer

Current conflict:

- persona says: 先接住，再展开，可以用“嗯”。
- retry-shadow contract says: directly answer first; do not answer only with acknowledgement or clarification.

Proposed rule:

```text
When an Evidence Contract is present and allowed_evidence can answer the user,
the Evidence Contract overrides persona-style opening behavior. Do not open
with "嗯", "然后呢", "你指的是", or a clarification question unless the direct
answer has already been provided.
```

### 2. Direct Preference Answer Obligation

For preference/style/language cases:

```text
If current_truth contains user preference facts, answer by applying and
restating those preferences first. Do not ask for clarification before
stating the best-supported preference.
```

### 3. Tool Markup Final-Answer Guard

Add post-check reason:

```text
tool_markup_in_final_answer
```

Detect:

- `<read_file>`
- `<path>`
- `</read_file>`
- other XML-like tool call tags
- local repo/worktree paths in final answer when the user did not ask for a file path

### 4. Anchor Term Preservation

For implementation-specific cases:

```text
Preserve domain anchor terms from current_truth, especially implementation
names such as NetworkX, version_chain, source_ref, sleep consolidation, and
session_key.
```

### 5. Scorer Calibration

Recommended synonym additions:

| expected | acceptable expressions |
| --- | --- |
| `条目式` | `列点`, `分点`, `列条`, `按点列`, `用点列` |
| `睡眠 + 清理` | `睡眠守护进程 + 清理掉`, `睡眠守护进程 + 扫一遍`, `后台睡眠任务 + 清理` |
| `NetworkX` | only relax if project decides `实体图谱` is enough; otherwise keep as required anchor |

## Next Experiment Recommendation

Before another large real LLM run, run a small fake + 10-case real pregate for:

- persona override wording;
- final-answer tool markup guard;
- scorer synonym calibration.

Success criteria:

- retry-shadow still `grounding = 100.0%`, `forbidden = 0.0%`;
- the six P6o-27 failed cases improve without regressing previously passed guided cases;
- no increase in tool-markup final answers;
- token increase stays below about `5%` vs guided.

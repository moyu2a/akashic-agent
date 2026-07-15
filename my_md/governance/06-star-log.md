# Failure STAR Log

这个文档是通用问题复盘台账，记录所有场景下的“问题发现 -> 原因分析 -> 处理方案 -> 处理结果 -> STAR 复盘”闭环。

适用场景：

- 运行启动报错。
- CLI / Dashboard / 插件 / 工具调用异常。
- 自动测试或手动测试失败。
- 学习过程中发现理解盲区。
- 架构设计上出现取舍问题。
- RAG、memory、agent loop、tool governance 等模块优化。
- 面试准备中发现表达不清或案例不足。
- 后续部署、性能、成本、安全、可观测性问题。

它和其他治理文档的关系：

- `01-issue-index.md` 记录问题总表。
- `02-current-issues.md` 记录当前待解决问题。
- `03-domain-evolution.md` 记录领域演进过程。
- `04-fix-roadmap.md` 记录后续修复计划。
- `05-design-decisions.md` 记录重要设计取舍。
- 本文档记录可以长期复盘、可以沉淀为 STAR 面试案例的完整闭环。

项目方向沉淀：

- Document RAG、工具边界治理、运行观测和 CLI 稳定性问题的复盘，已经沉淀出更大的产品/架构方向：本地个人数字员工 / 本地开发工作台 Agent。
- 该方向的长期路线记录在 `../local_agent/01-local-dev-workbench-agent-roadmap.md`。
- 本文档只记录已经发生的问题闭环和可复用 STAR 案例，不承载未来路线细节，也不把尚未实现的本地 Agent 能力写成已完成成果。

使用规则：

- 只要一个问题有复盘价值，就可以记录到这里，不限于测试问题。
- 如果问题还没修完，`处理结果` 写“待执行/处理中”，后续继续更新。
- 如果后续进入具体修复路线，再同步更新本目录下对应治理文档。
- 本文档是最终沉淀层，不是所有问题的第一入口；领域问题应先记录到对应领域演进文档，再筛选是否同步到这里。

## 问题映射规则

其他文档下的问题按以下路径映射到本文档：

| 问题来源 | 第一记录位置 | 同步到本文档的条件 |
| --- | --- | --- |
| 架构/模块设计问题 | `my_md/governance/03-domain-evolution.md` 的 Architecture 分节 | 涉及设计取舍、模块边界或代码修复闭环 |
| 测试失败/测试误判 | `my_md/test_docs/07-test-log.md` 或 `my_md/test_docs/eval_suite/reports/` | 有完整发现、分析、修复、验证过程 |
| 测试体系演进 | `my_md/governance/03-domain-evolution.md` 的 Test 分节 | 新增测试集、修正误判、调整 judge 或指标 |
| RAG 设计/实验问题 | `my_md/governance/03-domain-evolution.md` 的 RAG 分节 | 有实验结果、参数调整、失败案例或指标变化 |
| 跨模块系统问题 | `my_md/governance/02-current-issues.md` 和 `my_md/governance/03-domain-evolution.md` 的 System 分节 | 影响多个模块，能形成系统级复盘 |
| 问题总表/技术债 | `my_md/governance/01-issue-index.md` | 某个问题进入处理闭环后同步 |
| 当前待解决问题 | `my_md/governance/02-current-issues.md` | 某个问题被定位、处理、验证后同步 |
| 修复路线 | `my_md/governance/04-fix-roadmap.md` | 某条路线实际执行完后同步 |
| 设计决策 | `my_md/governance/05-design-decisions.md` | 决策背后有冲突、取舍和结果时同步 |

同步判断标准：

- 有明确问题现象。
- 有原因分析。
- 有处理方案或处理结果。
- 能用 STAR 法则讲成一个案例。

满足其中两个以上，就可以同步到本文档。

建议问题编号：

```text
ARCH-001
TEST-001
RAG-001
SYS-001
EV-001
```

同步提示词：

```text
请按 my_md/governance 的问题映射规则处理：原始事实保留在对应业务目录；需要治理的问题同步到 my_md/governance/01-issue-index.md 或 02-current-issues.md；领域演进写入 03-domain-evolution.md；如果该问题具备明确现象、原因分析、处理方案或处理结果，并且适合沉淀为 STAR 案例，请同步更新 my_md/governance/06-star-log.md，并保留来源编号或关联文档路径。
```

复盘提炼提示词：

```text
请基于当前问题的日志、observe 记录、测试结果和相关文档，按 06-star-log.md 的结构做一次可复用复盘：

1. 先保留事实：问题现象、证据、影响范围、原因分析、排查路径。
2. 再做问题分层：把问题拆成配置/工具可见性/工具访问边界/执行边界/收尾边界/证据忠实度/可观测性/性能成本等层面。
3. 然后提炼方案：每一层写清楚根因、采用的模块化边界或策略、为什么不用更简单但不可扩展的修补。
4. 最后量化成果：记录修复前后 ReAct 轮次、工具调用次数、prompt tokens、是否断连、是否仍有 forbidden tools、自动化测试结果和真实 smoke 结果。

输出时请同时补充：
- `可提炼成果`：用表格总结“问题 -> 根因 -> 方案 -> 成果指标”。
- `可复用结构`：总结这次问题暴露出的通用工程模式，例如 access control plane、execution boundary、completion boundary、evidence labeling。
- `后续可复用提示词`：给出下一次遇到类似问题时可以直接复制使用的诊断/复盘 prompt。

不要只写“已修复”；必须写清楚指标改善和仍未解决的边界。
```

## 记录模板

### CASE-xxx: 问题标题

日期：

问题类型：

- 运行 / 测试 / 学习 / 架构 / RAG / memory / tool / plugin / proactive / 面试 / 部署 / 其他

关联问题或文档：

- EV-xxx
- 可选：相关学习文档、测试报告、源码路径

发现方式：

- 手动测试 / 自动评估 / 日志观察 / 用户反馈 / 学习卡点 / 代码阅读 / 面试复盘

问题现象：

-

证据：

- 日志：
- 报告：
- 源码：
- 复现步骤：

影响范围：

-

原因分析：

-

排查路径：

| 顺序 | 检查点 | 检查方式 | 结果 | 结论 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  |  |

处理方案：

-

取舍说明：

-

处理结果：

-

可提炼成果：

| 问题 | 根因 | 方案 | 成果指标 |
| --- | --- | --- | --- |
|  |  |  |  |

可复用结构：

- 这个问题可以抽象成什么工程边界问题？
- 哪些模块边界被重新划清？
- 哪些指标可以作为以后同类问题的验收标准？

验证方式：

-

遗留问题：

-

STAR 复盘：

- Situation：当时系统处于什么场景，为什么这个问题重要？
- Task：我需要解决什么目标，约束是什么？
- Action：我做了哪些分析、取舍和改动？
- Result：最后结果如何，指标或现象有什么改善？

面试表达：

-

后续可复用提示词：

```text
请把这个问题整理成 STAR 复盘，重点不要只写现象和修复，而要提炼工程模式：

- 问题分层：配置、访问权限、工具可见性、执行边界、终止条件、证据忠实度、可观测性、性能成本。
- 边界设计：哪些判断应该在 core policy，哪些可以交给插件，哪些不能写入跨 turn 状态。
- 指标结果：修复前后 ReAct 轮次、工具调用次数、prompt tokens、错误工具调用、CLI/服务稳定性、测试通过情况。
- 复用价值：以后遇到类似问题，可以复用哪些模块、规则、测试和 smoke 方法。

请更新 `my_md/governance/06-star-log.md`，并在相关 `02-current-issues.md`、`04-fix-roadmap.md` 或领域文档中同步当前状态。
```

## 当前案例

### CASE-001: 自动评估发现测试失败中混有测试误判

日期：2026-07-03

关联问题：

- EV-004
- EV-005

发现方式：

- 运行 `deep_live_eval_runner.py --judge` 后查看报告。

错误现象：

- 102 个 safe case 中 pass 80、fail 22。
- judge 全部 skipped，原因是当前 Python 环境缺少 `openai` 包。
- 部分失败不是 agent 行为错误，而是测试断言过硬。

影响范围：

- 如果直接根据失败列表修改核心源码，可能会为了通过错误断言而改坏正确行为。
- 真实问题和测试噪声混在一起，会影响后续修复优先级。

原因分析：

- C/D 组存在 group-level 工具调用断言，导致无关问题也被强制要求调用记忆工具。
- 部分中文断言只接受少量固定表达，没有覆盖“答不了”“查不到”等同义回答。
- judge runner 依赖 `openai` Python 包，但实际运行环境没有安装。

排查路径：

| 顺序 | 检查点 | 检查方式 | 结果 | 结论 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 1 | 自动评估总体结果 | 查看 deep live report | 102 条 safe case，80 pass，22 fail | 失败数量较多，需要先分类 | 分析失败 case 类型 |
| 2 | judge 是否实际运行 | 查看 report judge 字段 | judge 全部 skipped，缺少 `openai` 包 | 语义评审没有生效 | 修 judge runner 或运行环境 |
| 3 | 失败是否都是 agent bug | 抽查 A/C/D 组失败项 | 多个 case 是断言过硬或 group-level 工具要求过宽 | 不能直接按失败列表改核心源码 | 先修测试噪声 |
| 4 | 修复顺序 | 对比测试噪声和真实问题 | 测试误判会干扰真实问题定位 | 先修测试体系，再修 agent 行为 | 小范围回归验证 |

处理方案：

- 第一阶段先修测试集和 judge runner，不先改 agent 核心源码。
- 放宽中文同义表达。
- 把整组工具调用断言下沉到具体 case。
- judge runner 改为 OpenAI-compatible HTTP 调用，减少本地包依赖。

处理结果：

- 待执行。

验证方式：

- `python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --dry-run`
- 小范围回归 A019、C011、C014、D015、D024。
- 再运行 `--judge --limit 10` 确认 judge 不再全部 skipped。

遗留问题：

- 真实 agent 行为问题仍需后续处理：临时记忆污染、no-tool 硬约束、工具链成本。

STAR 复盘：

- Situation：自动评估报告显示大量失败，但失败原因混杂，无法直接判断哪些是系统 bug。
- Task：先把测试噪声和真实问题分离，建立可靠的修复基线。
- Action：分析失败 case，识别出测试断言过硬和 judge 环境依赖问题，决定先修测试体系。
- Result：形成了清晰的修复顺序：先降低测试噪声，再处理核心 agent 行为问题。

面试表达：

在做 Agent 评估时，我没有直接根据 pass/fail 修改核心逻辑，而是先审查失败样本，把测试误判、judge 基础设施问题和真实系统缺陷分开。这样可以避免为了通过错误测试而破坏正确行为，也体现了我对评估基线可靠性的重视。

### CASE-002: 临时 session 信息可能污染长期记忆

日期：2026-07-03

关联问题：

- EV-001
- EV-006

发现方式：

- session isolation 自动评估失败。
- observe trace 中出现临时测试信息触发 `memorize`。
- 2026-07-03 小范围 live 回归中，`DL-B-012` 和 `DL-B-023` 仍失败。

错误现象：

- 临时 session 变量被写入长期记忆。
- 其他 session 后续可能通过长期记忆召回这些内容，看起来像跨 session 泄漏。
- `DL-B-012` 中，cli_b 回答包含了 cli_a 的 `value-a-012`。
- `DL-B-023` 中，cli_b 通过 `fetch_messages` 后回答了 cli_a 的 `private-a-b023`。
- `DL-B-018` 虽然 pass，但出现 `fetch_messages`、`forget_memory`、`memorize` 工具链。

影响范围：

- 长期记忆被测试数据污染。
- session isolation 测试结果失真。
- 用户临时信息可能被错误保存，影响信任。
- 消息回源工具如果不做 session 限制，会让其他会话私有内容进入当前回答。

原因分析：

- 模型看到结构化事实时，可能误判为值得保存的长期信息。
- 当前主要依赖提示词约束 `memorize` 使用时机。
- 工具层没有对明显临时标记做硬拦截。
- 最新 live 结果显示，问题不只在 `memorize`：`fetch_messages` 也可能跨 session 取到其他会话内容。
- 需要进一步确认 `fetch_messages` / `search_messages` 的 session 过滤逻辑，以及 eval runner 的 `cli_a/cli_b/cli_c` 是否真的隔离 session key。

排查路径：

| 顺序 | 检查点 | 检查方式 | 结果 | 结论 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 1 | 测试输入是否有歧义 | 检查 `deep-live-eval-cases.yaml` | 主要声明型 session 临时事实已带“临时会话信息，不要写入长期记忆”前缀 | 输入歧义基本排除 | 做小范围 live 回归 |
| 2 | 测试结构是否正常 | dry-run 重点 7 条 case | 7 条 case 均能正常展开 | 测试结构无问题 | 执行 live 测试 |
| 3 | session 隔离 live 表现 | live 跑 7 条重点 case | 5 pass / 2 fail，失败为 `DL-B-012`、`DL-B-023` | 问题仍存在 | 分析失败工具链 |
| 4 | 是否仍触发记忆工具 | 查看 live 报告工具调用 | `DL-B-018` 出现 `fetch_messages`、`forget_memory`、`memorize` | 临时 session 信息仍可能触发记忆工具链 | 检查 `memorize/forget_memory` 触发边界 |
| 5 | 是否存在消息回源跨 session | 查看失败 case 工具调用和回答 | `DL-B-012`、`DL-B-023` 通过 `fetch_messages` 后出现其他 session 内容 | 新增 EV-006，怀疑 `fetch_messages`/source_ref/session guard 问题 | 检查 `fetch_messages` 和 `search_messages` 实现 |
| 6 | eval runner 是否真的隔离 session | 查 `deep_live_eval_runner.py`、IPC server 和 report JSON | 不同 channel 对应不同 `IpcClient`，IPC 按连接生成不同 chat_id，report 中 session_key 不同 | runner 侧隔离基本成立 | 转向检查消息回源工具 |
| 7 | `fetch_messages/search_messages` 是否按 session 过滤 | 审查 `agent/tools/message_lookup.py`、`session/store.py`、工具上下文同步逻辑 | `fetch_messages` 没有当前 session 校验；`search_messages` 不传 `session_key` 时全局搜索；工具上下文未注入完整 `session_key` | 消息回源工具存在明确 session guard 缺口 | 查看失败 turn 的 source_ref 来源 |
| 8 | source_ref 从哪里进入 | 查询 observe DB 的 `turns/tool_chain_json`，并对照 `rag_queries`、`memory_writes`、`sessions.db` | `DL-B-012` 使用当前 session source_ref，工具结果未含 A 值；`DL-B-023` 使用另一个旧 session source_ref，且未在 observe 的 RAG/记忆写入表中找到对应来源 | 两个失败不是同一种原因：B012 更像回答层混入上下文，B023 是明确跨 session 回源 | 继续查 B012 的记忆注入来源 |
| 9 | B012 的 A 值是否来自长期记忆自动注入 | 查询 `memory2.db` 和 `recall_inspector.jsonl` | memory2 中存在 active 记忆 `EVAL_SESSION_B012 的 A 变量是 value-a-012`，recall inspector 记录该条被作为“相关历史”注入 prompt | B012 已定位为长期记忆污染 + 自动注入，不是工具读取错误 | 先修记忆写入边界并清理污染记忆 |

处理方案：

- 第一阶段已检查测试输入：主要 session 临时事实已带有“临时会话信息，不要写入长期记忆”。
- 后续候选方案包括：加强提示词、在 `memorize` 工具层拒绝明显临时/session/test 标记。
- 新增定位方向：检查 `fetch_messages` / `search_messages` 是否按当前 session 做过滤。
- 已完成代码审查：`fetch_messages` 默认允许按任意 source_ref 回源；`search_messages` 未传 `session_key` 时默认全局搜索；工具上下文没有注入完整 `session_key`。
- 已完成 source_ref 来源排查：`DL-B-012` 的工具调用没有读到其他 session，`DL-B-023` 的工具调用明确读取了另一个旧 session。
- 已完成 `DL-B-012` 进一步定位：A 值来自 memory2 active 记忆，并被 recall inspector 记录为自动注入到 prompt 的“相关历史”。

处理结果：

- 第一阶段测试输入消歧义已完成，但 live 回归仍有 2/7 失败。
- 结论：仅靠测试输入消歧义不足以解决隔离问题；`DL-B-012` 需要修长期记忆写入边界并清理污染记忆，`DL-B-023` 需要工具层 session guard。

验证方式：

- DL-A001
- DL-B001
- DL-B-010 到 DL-B-023
- 检查长期记忆中不出现 `EVAL_SESSION_*`。
- 最新 live 报告：`my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-172519-006985.md`
- 结果：7 条重点 case 中 pass 5、fail 2。

遗留问题：

- 需要区分“用户明确要求长期记住”和“只是当前会话临时事实”。
- 已确认 `fetch_messages` 工具实现缺少当前 session guard。
- `DL-B-023` 的旧 source_ref 暂未能从 observe 的 RAG 查询或记忆写入表中定位到来源，后续需要继续查 prompt/history 注入。
- `DL-B-012` 已确认是长期记忆污染和自动注入，不再是未定位问题。

STAR 复盘：

- Situation：session 隔离测试中出现跨会话信息泄漏现象。
- Task：判断是真正的 session history 隔离失败，还是长期记忆污染导致的间接泄漏。
- Action：先检查测试输入是否明确标注临时信息，再做小范围 live 回归；根据失败 case 的工具链，把问题拆成记忆写入边界和消息回源 session 隔离两条线；随后审查消息查询工具，确认默认搜索和回源缺少当前会话边界。
- Result：确认测试输入消歧义不足以解决问题，也确认 `message_lookup` 工具存在代码层 session guard 缺口。进一步查证后发现两个失败 case 类型不同：一个是长期记忆污染后被自动注入 prompt，另一个是明确跨 session 回源。下一步应先修记忆写入边界和污染清理，再设计默认当前会话、显式授权跨会话的工具边界。

面试表达：

我在排查 session 隔离失败时，没有只看表面现象，而是先区分短期会话上下文、长期记忆和消息回源工具三层。第一轮怀疑是临时信息污染长期记忆，但小范围 live 回归显示消息回源也可能跨 session 取到其他会话内容。随后我审查消息查询工具，确认默认搜索和回源缺少当前会话边界。进一步查实际工具参数和记忆注入记录后，我发现两个失败 case 类型不同：一个是临时测试数据进入长期记忆后被自动注入 prompt，另一个确实读取了旧 session 的 source_ref。因此修复路线分成两部分：先治理记忆写入边界和污染清理，再收紧消息回源工具权限，默认限定当前会话。

### CASE-003: Document RAG live smoke 发现配置、工具成本和 citation 忠实度问题

日期：2026-07-11

关联问题：

- RAG-005
- RAG-006
- RAG-007

发现方式：

- P9 Document RAG citation 自动化测试通过后，执行真实 CLI/LLM smoke。
- 通过 `observe.db` 查看真实工具链、ReAct 轮次、最终回答和 citation。

问题现象：

- 第一轮 live smoke 中，`search_docs` 返回 `doc_rag_disabled`，模型随后 fallback 到 `list_dir/read_file`，没有形成 Document RAG citation。
- 启用 Document RAG 后，第二轮 live smoke 能返回正确 citation，但 `react_iteration_count=7`。
- 最终 citation 来源真实，但“runtime 下辖 Tool Calling”这类表达属于基于标题结构的推断，正文证据没有直接写明“下辖”。

证据：

- `observe.db` turn id `344`：
  - `search_docs` 返回 `error_code=doc_rag_disabled`。
  - 后续继续调用 `list_dir/read_file`。
- `observe.db` turn id `345`：
  - 工具链：`search_docs -> tool_search -> search_docs -> tool_search -> fetch_doc_chunk -> fetch_doc_chunk`。
  - `react_iteration_count=7`。
  - 最终 citation：
    - `[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]`
    - `[my_md/doc_rag_corpus/manual_test.md > Agent Runtime > Tool Calling]`
- chunk 正文：
  - `Agent runtime 负责管理 agent 的一次运行过程。`
  - `工具调用用于让 agent 访问外部能力。`

影响范围：

- 如果配置未启用，live smoke 测不到 RAG citation 能力，只会测到 disabled fallback。
- 如果工具不可见，RAG happy path 会多出 2-3 轮，增加成本和延迟。
- 如果只校验 citation 来源，不校验 claim/evidence 对齐，仍可能出现“引用真实但结论说过头”的回答。

原因分析：

- `doc_rag.enabled` 默认关闭，运行配置未显式启用时，`search_docs` 正确返回 disabled。
- disabled 返回缺少足够强的 terminal 语义，模型会继续尝试用普通文件工具完成任务。
- `search_docs` / `fetch_doc_chunk` 初始不可见，真实对话需要先经由 `tool_search` 解锁。
- citation validator 当前只保证 citation 来自本轮工具结果，不负责逐句判断 claim 是否被证据直接支撑。

工具治理演进脉络：

- 最初的工具发现机制是 `tool_search`：基础工具保持少量 always-on，其他工具按需通过 `tool_search` 解锁。这降低了默认 prompt 工具空间，但强文档问题会先经历“工具不可见 -> 调用 tool_search -> 再调用目标工具”的额外 ReAct 轮次。
- 为了减少明确文档问题的循环次数，P10a 增加了 turn-local intent preload：强文档意图当前 turn 预加载 `search_docs`，强文档 + 原文/证据展开意图再预加载 `fetch_doc_chunk`。该方案刻意不改 always-on，也不写入 `ToolDiscoveryState` / LRU，避免把 Document RAG 工具长期暴露给普通聊天或记忆问题。
- P10a live smoke 证明预加载本身有效，但也暴露了下一层问题：工具“可见”不等于工具“应该使用”。强文档证据问题仍可能被模型解释成“查项目源码/仓库文件”，转向 `shell/read_file/list_dir`，形成更长工具链。
- 继续在 `DefaultReasoner.run_turn()` 里叠加 if 只能局部缓解，无法处理 `tool_search` 重新解锁、执行前兜底、terminal 工具结果禁止 fallback 等多个入口。工具可用性判断已经分散在 always-on、LRU、disabled_tools、P10a preload、tool_search、tool hook 和工具结果语义中。
- 因此后续演进方向调整为 Tool Access Gateway：把“当前 turn 哪些工具可见、哪些工具可被 tool_search 解锁、哪些工具即使被调用也不得执行、工具结果如何改变后续访问”收束到一个 core policy boundary。它不是普通插件，也不重写 AgentLoop；第一版只窄接入 `DefaultReasoner` 的 prompt schema、`tool_search` unlock 和工具执行前后。
- Gateway 的定位是 access control plane，插件仍作为 behavior extension plane。未来插件可以贡献 `ToolAccessPolicy`，但不得绕过 `disabled_tools`、不得直接改 LRU、不得直接改 LLM message list 或替换 `ToolRegistry.execute`。
- 2026-07-11 第一版 Tool Access Gateway 已实现：新增 `agent/policies/tool_access.py`，把 P10a turn-local preload 和 P10a.1 本地文件工具治理统一为 `ToolAccessPlan`；`DefaultReasoner` 只在工具 schema 计算、`tool_search` 结果过滤/解锁合并、执行前 gate、工具结果观察四个窄点接入。意图预加载仍不写入 `ToolDiscoveryState` / LRU，always-on 策略不变。
- turn `361` 证明 Tool Access Gateway 已解决强文档证据请求误用本地文件工具的问题，但也暴露出下一层边界：access control 只能回答“能不能用这个工具”，不能回答“还要不要继续调用工具”。因此 RAG-006 的下一步应命名为 P10a.2 成本治理，聚焦预算、重复调用和 evidence-complete 早停。
- P10a.2 Turn Tool Boundary Manager 进一步把“是否应该继续真实执行工具”收束到 current-turn execution boundary：冗余 `tool_search`、重复 `search_docs/fetch_doc_chunk` 和 evidence-complete 后的额外展开会变成非执行型 `soft_stop`。turn `362` 证明真实目标工具执行已收敛到 `search_docs + fetch_doc_chunk`，但也暴露出新的边界：`soft_stop` 作为工具结果仍会回到 LLM，继续消耗轮次和 prompt tokens。
- 因此 P10a.3 再把边界从“工具执行”推进到“ReAct 继续/收尾”：新增 `TurnCompletionController`，读取同一份 ledger 和 boundary decisions，在 `document_rag_evidence_complete` 后让下一次 LLM 调用进入 final-only，省略工具 schema，只允许基于已有 Document RAG evidence 回答。这是 completion control plane，不写入 LRU，不替代 Tool Access Gateway，也不改变 always-on。

排查路径：

| 顺序 | 检查点 | 检查方式 | 结果 | 结论 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| 1 | 索引是否存在 | 查看 `doc_rag.db` | 11 个 chunks 均为 ready | 索引不是失败原因 | 查运行配置 |
| 2 | 第一轮 smoke 为什么无 citation | 查看 `observe.db` turn 344 | `search_docs` 返回 `doc_rag_disabled` | 配置未启用 | 启用配置后重跑 |
| 3 | 启用后是否能检索 | 查看 `observe.db` turn 345 | `search_docs` ok，最终回答带 citation | RAG happy path 可用 | 分析成本 |
| 4 | 为什么有 7 轮 | 解析 `tool_calls` 和 `tool_chain_json` | `search_docs/fetch_doc_chunk` 都需要先解锁 | 工具可见性导致额外轮次 | 设计预加载策略 |
| 5 | citation 是否伪造 | 对比最终引用和工具返回 citation | 两个 citation 均来自本轮工具结果 | 不是 fake citation | 检查证据强度 |
| 6 | 结论是否被证据直接支撑 | 对比回答 claim 和 chunk 正文 | “负责管理运行过程”有直接证据，“下辖 Tool Calling”是结构推断 | 需要 faithfulness 约束 | 增加 evidence alignment |
| 7 | P10a 预加载是否解决工具链过长 | 查看 14:26 live smoke 日志和 observe turn 349 | 预加载生效，但链路转向 `shell/read_file` | 单纯可见性治理不足 | 设计强文档非 RAG 工具约束 |
| 8 | 工具约束应放在哪里 | 对比 prompt visibility、tool_search unlock、执行前 hook、terminal result | 单点 hook 无法覆盖所有绕路 | 需要统一工具访问边界 | 设计 Tool Access Gateway |
| 9 | 工具执行边界是否足够 | 查看 turn 362 P10a.2 smoke | 冗余工具已被 soft_stop，但 LLM 仍跑 5 轮 | 执行边界不足以控制 reasoning 成本 | 增加 final-only turn completion |

处理方案：

- RAG-005：disabled 场景下增加 terminal/retryable/recommended_action 语义，并要求模型停止而不是 fallback 到 `read_file`。
- RAG-006：采用强文档意图的 turn-local preload，而不是把 `search_docs` 改成 always-on；强文档意图当前 turn 预加载 `search_docs`，强文档意图且需要原文/证据展开时再预加载 `fetch_doc_chunk`；强记忆/session 意图且无强文档意图时，在当前 turn 临时压制 `search_docs` / `fetch_doc_chunk` 的 LRU 残留。
- RAG-006 P10a.1：从“只控制工具可见性”升级为 Tool Access Gateway，统一治理 prompt 可见性、`tool_search` 解锁、执行前拦截和 terminal 结果后的 fallback 阻断。
- RAG-006 P10a.1 第一版实现：强文档证据请求未显式要求源码/本地文件时，`shell/read_file/list_dir` 会从 prompt schema 中被压制，`tool_search` 返回给模型前会过滤这些工具，模型绕过 schema 直接调用时会被执行前 gate 阻断；显式源码/路径请求保留本地文件工具。
- RAG-006 P10a.2：在 P10a.1 已验证不跑偏到本地文件工具后，继续治理 Document RAG 工具链成本；目标是减少已可见工具下的多余 `tool_search`，限制重复 `search_docs/fetch_doc_chunk`，并在证据足够时早停。
- RAG-006 P10a.3：在 P10a.2 已能阻止冗余工具真实执行后，继续治理 `soft_stop` 后的 LLM 轮次/token 成本；当 `document_rag_evidence_complete` 已成立时，下一次 LLM 调用进入 final-only，不再暴露工具 schema。
- RAG-007：回答约束中区分“文档明确写明”和“基于标题结构推断”；评估中增加 `claim_evidence_alignment`。
- RAG-005 第一阶段已执行：`doc_rag_disabled` 返回 `terminal_scope=document_rag`、`fallback_allowed=false`、`recommended_action=answer_doc_rag_disabled`、`instructions` 和 `user_message`；工具描述明确不要用本地文件读取替代 Document RAG。

取舍说明：

- 不把所有 RAG 工具永久 always-on，也不把意图预加载结果写入 `ToolDiscoveryState` / LRU：避免非文档问题污染工具空间，并避免“上一轮查文档，下一轮问记忆”被 LRU 残留误导。
- 不把 Tool Access Gateway 做成普通插件：普通插件的 pre-tool hook 介入太晚，不能控制 prompt schema，也不能阻止 `tool_search` 把被压制工具重新解锁。Gateway 应作为 core policy boundary，未来再允许插件贡献受限的 policy。
- 不改 AgentLoop 主体循环：工具访问治理只需要窄接入 `DefaultReasoner` 的工具路径，不应影响 channel、scheduler、session storage 和 outbound dispatch。
- 不强制每个问题都 `fetch_doc_chunk`：简单事实问题用 snippet 足够时，应优先控制成本。
- 不把 citation valid 当作最终质量指标：citation 只能证明来源真实，不能证明每个结论都被原文充分支持。
- RAG-005 第一阶段没有改 AgentLoop：因为 `doc_rag_disabled` 是业务工具语义，先用工具协议和工具描述收敛模型行为；如果 live smoke 仍 fallback，再考虑执行器级阻断。

处理结果：

- 已定位并登记 RAG-005、RAG-006、RAG-007。
- RAG-005 第一阶段代码修复已完成，自动化回归通过。
- RAG-005 disabled live smoke 已执行：未再 fallback 到 `read_file/list_dir/shell`，但最终话术仍暗示可以主动开启配置，需要补充“必须重启当前 Agent 服务”的表达约束。
- RAG-005 第二小步代码已完成：disabled payload 已加入 `restart_required`、`restart_target`、`current_process_can_enable`、`retrieval_available_this_turn`、`config_key`、`required_config_value`，并强化 `instructions` / `user_message`，live smoke 待复测。
- RAG-006 P10 计划已完成审阅并修订：实现位置应放在 `DefaultReasoner.run_turn()` 当前 turn 工具可见性计算处，新增策略模块 `agent/policies/doc_rag_intent.py`，不改 `doc_rag` toolset 的 always-on 策略，不改 LRU 写入规则。
- RAG-006 P10a 代码实现已完成：`DefaultReasoner.run_turn()` 使用 turn-local `effective_preloaded`，强文档意图预加载 `search_docs`，强文档 + 原文/证据展开意图预加载 `fetch_doc_chunk`，强记忆/session 意图临时压制 doc_rag LRU 残留；自动化回归 `43 passed in 0.48s`。
- RAG-006 P10a live smoke 发现后续缺口：预加载生效，但强文档证据问题仍跑偏到 `shell/read_file`，turn `349` 实际工具链为 `search_docs -> shell/read_file...`，共 15 次工具调用，`react_iteration_count=10`，`react_input_peak_tokens~=34858`。
- CLI-001 已登记：第二轮主链完成并写入 observe 后，CLI 提示 `Separator is found, but chunk is longer than limit`，随后 IPC 出现 `[cli] client disconnected session=cli:cli-140554156611568`；第三轮未进入 observe。该提示来自 `asyncio.StreamReader.readline()` 单行读取限制，说明 outbound 单行 JSON payload 过大。旧版 CLI/IPC 还使用 `id(writer)` 生成 session，断线重连会丢失原会话关联。
- CLI-001 已完成自动化修复：CLI IPC v2 使用 `AKIP2` magic + length-prefixed frame、稳定 client/session id、CLI/TUI `tool_summary` 投影、payload 治理和 workspace 文件日志。
- 2026-07-11 16:17 复测：CLI IPC v2 未断连，session 仍为 `cli:cli-d76d211cea0546619146f9a7b1c4e268-default`；但强文档长证据 prompt 在 turn `354` 再次跑偏为 `read_file -> read_file -> shell -> search_docs -> shell -> shell -> read_file -> search_docs -> read_file`，`react_iteration_count=7`，`react_input_peak_tokens~=37978`。P10a.1 保持 open，本轮不修，后续回到工具治理处理。
- 2026-07-11 16:32 用户真实 CLI 测试确认：默认启动 CLI 会继承之前 session，说明 CLI-001 的稳定 client/session id 路径已在真实界面生效。CLI-001 可按 fixed 记录；后续主问题是 RAG-006 P10a.1。
- 2026-07-11 已形成 Tool Access Gateway 设计：将散落的工具可用性判断收束为 current-turn `ToolAccessPlan`，统一输出 `visible_add`、`visible_suppress`、`tool_search_block` 和 `execution_block`；第一阶段服务 RAG-006 P10a.1，不引入持久 RBAC，不替代插件系统，不重写 AgentLoop。
- 2026-07-11 Tool Access Gateway 第一版代码已完成并通过自动化回归：纯策略测试覆盖强文档压制、显式源码放行、memory-after-doc-LRU、`tool_search` 过滤、执行前拦截和 terminal fallback 阻断；reasoner 集成测试覆盖 schema 压制、过滤后 payload、blocked call 不执行/不计入 `tools_used`、显式源码放行。
- 2026-07-11 21:01 真实 CLI/LLM smoke 验证 Tool Access Gateway 的关键目标：turn `361` 强文档 + 原文 chunk 展开 prompt 未再调用 `shell/read_file/list_dir`，实际链路为 `tool_search -> search_docs -> fetch_doc_chunk -> fetch_doc_chunk -> fetch_doc_chunk -> search_docs -> fetch_doc_chunk`，`error=NULL`，CLI 未断连。问题从“工具可用性判断错误”收敛为“工具链成本偏高”。
- 2026-07-11 P10a.2 已登记为下一阶段：turn `361` 的剩余问题不是 access 错误，而是预算和终止条件不足；后续应把目标从“不用错工具”提升为“少用且及时停止”。
- 2026-07-12 P10a.2 正式设计已形成：`my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`，命名为 Turn Tool Boundary Manager，将 access、budget、evidence completion、ledger 和 trace 收束到 current-turn core policy boundary。
- 2026-07-12 已调用审阅 skill 审阅 P10a.2 设计并完成修订：补齐 `soft_stop` 执行语义、决策合并优先级、ledger 结构化字段和负向/优先级测试要求。修订后实现计划可以基于“soft_stop 不执行目标工具、core block 不可被放宽、ledger 是共享事实源”这三个控制面约束展开。
- 2026-07-12 P10a.2 自动化实现已完成：新增 `ToolCallLedger`、`ToolBudgetPolicy`、`EvidenceCompletionPolicy`、`TurnToolBoundaryManager` 并接入 `DefaultReasoner`。验证结果：targeted suite `100 passed, 2 warnings`，full pytest `1361 passed, 3 warnings`，compileall exited 0。
- 2026-07-12 P10a.2 真实 CLI/LLM smoke 已执行：turn `362` 中 `tool_boundary` 成功把冗余 `tool_search`、额外 `fetch_doc_chunk`、额外 `search_docs` 转为 `tool_boundary_soft_stop`，真实成功执行工具只有 `search_docs` 和 1 次 `fetch_doc_chunk`，且未调用 `shell/read_file/list_dir`。新暴露的问题是 `soft_stop` 仍需要回到 LLM 继续推理，导致 5 轮 LLM、`react_input_peak_tokens~=73267`、`prompt_tokens=419680`。演进结论：P10a.2 解决了“不要重复执行工具”，但没有完全解决“不要重复消耗 LLM 轮次/token”。
- 2026-07-12 P10a.3 自动化实现已完成：新增 `agent/policies/turn_completion.py` 并接入 `DefaultReasoner`；evidence-complete soft stop 后下一轮 LLM 使用 `tools=[]`，`context_retry.turn_completion` 记录 action/reason/metadata，普通日志输出 `[turn_completion] final_only ...`。验证结果：targeted suite `24 passed`，broader relevant suite `55 passed`，full pytest `1373 passed, 3 warnings`，compileall exited 0。真实 CLI/LLM smoke 仍需重跑 turn `362` 同类 prompt。
- 2026-07-12 P10a.3 真实 CLI/LLM smoke 已执行：turn `364` 中普通日志出现 `[tool_boundary] soft_stop tool=fetch_doc_chunk reason=document_rag_evidence_complete` 和 `[turn_completion] final_only reason=document_rag_evidence_complete`；成功工具执行为 `search_docs + fetch_doc_chunk`，未调用 `shell/read_file/list_dir`，`react_iteration_count=3`，`prompt_tokens=265562`，相较 turn `362` 的 5 轮/`419680` prompt tokens 达成轮次和 token 降本目标。新暴露的问题是 final-only 回答把 soft-stopped 的候选 chunk 写成“原文展开”，说明工具边界已收束，但回答 evidence labeling 仍需收紧。
- 2026-07-13 P10a.4a Evidence Contract 已完成：新增 `agent/policies/evidence_contract.py`，从同一份 ledger 和 boundary decisions 中抽取 `fetched_text`、`retrieval_snippet`、`soft_stopped_candidate`，并在 final-only 前注入回答约束。为避免真实 `search_docs` 结果被 `result_summary[:240]` 截断后无法解析，`ToolCallRecord` 新增完整 `result_text`。验证结果：新增 evidence contract 测试通过，相关 P10a 回归 `27 passed`，full pytest `1376 passed, 3 warnings`，compileall 和 `git diff --check` 通过。
- 2026-07-13 P10a.4a 真实 CLI/LLM smoke 已检查：turn `365` 和 `366` 均未调用 `shell/read_file/list_dir`，均只真实成功执行 `search_docs + fetch_doc_chunk`，两个后续 `fetch_doc_chunk` 请求被 soft-stop。最终回答已把成功 fetched chunk 称为“完整原文/原文”，把未真实 fetch 的 Tool Calling / 系统全景证据称为“检索命中/检索摘要”，不再把 soft-stopped candidate 写成已展开原文。
- 2026-07-13 新暴露的成本边界：P10a.4a 修复了证据忠实度，但 turn `365/366` 显示同一 assistant tool-call batch 中仍会生成多个 `fetch_doc_chunk` 请求；boundary 可以避免真实重复执行，却无法阻止模型先生成多余 tool calls。下一步 P10a.4b 应采用 bounded ReAct / React Boundary Cost Optimization：工具结果入账后 proactive final-only，下一轮动态隐藏已不需要的 Document RAG 工具，并用 batch-level budget 限制同一 LLM 响应里的多工具调用。
- 2026-07-13 P10a.4b Bounded ReAct / Batch Boundary 自动化实现已完成：新增 `ReactBoundaryManager`，把 after-result proactive completion 和 same-batch skip 分开治理。Evidence Contract 仍负责证据充分性，Turn Completion 仍负责 final-only 决策，React Boundary 只返回 `recommend_final_only` 和 `batch_skipped_by_react_boundary`。同批次 skipped calls 仍追加合法 tool result，但不计入成功 `tools_used`，不写入 evidence ledger，不成为 `soft_stopped_candidate`。验证结果：P10a targeted suite `48 passed`，full pytest `1391 passed, 3 warnings`，compileall 通过。随后已执行真实 CLI/LLM smoke。
- 2026-07-13 P10a.4b 真实 CLI/LLM smoke 已执行并检查 observe/session/log：
  - turn `367` 简单文档引用问题收敛为 `search_docs -> final`，`react_iteration_count=2`，日志出现 `[react_boundary] final_only reason=document_rag_retrieval_complete`。
  - turn `368` 原文证据问题收敛为 `search_docs -> fetch_doc_chunk -> final`，`react_iteration_count=3`；同一 assistant tool-call batch 中额外两个 `fetch_doc_chunk` 被 `react_boundary_batch_skip` 跳过，保持 provider tool-result 协议合法但不真实执行。
  - turn `369` 文档 + 源码问题只执行 `read_file x3`，说明显式源码读取的 local-source exemption 生效，没有被 Document RAG final-only 过早截断；但本轮文档证据来自前文上下文，不是 fresh RAG。
  - turn `370` “刚才第二个问题用了哪些工具”只执行 `search_messages`，没有被 `search_docs/fetch_doc_chunk` 的 LRU 残留污染；但最终回答把 turn `369` 的工具链说成 `search_docs + fetch_doc_chunk + read_file x3`，与 observe/session 记录的 `read_file x3` 不一致。
- 2026-07-13 新暴露的 session/meta 边界：当用户问“上一轮/第二个问题用了哪些工具”时，普通 `search_messages` 和模型上下文只能提供自然语言历史，不能保证工具链事实准确。这个问题不属于 Document RAG 成本边界，而属于结构化 turn/tool trace 回源边界。后续应提供或扩展一个只读 trace 查询能力，按当前 session、turn id/相对轮次返回真实 `tool_chain_json` / `tools_used`，并要求模型在回答工具历史时以结构化 trace 为准。
- 2026-07-13 已完成 Turn Trace Query 实现计划审阅：计划采用 core service + deferred tool adapter + ToolAccessGateway visibility，而不是纯插件或 AgentLoop 改造。核心约束包括：`inspect_turn_trace` 不 always-on、不进 LRU、不暴露 model-controllable `session_key`；protected `_session_key` 由 registry context 注入；`blocked_by_tool_boundary`、`soft_stopped_by_tool_boundary`、`react_boundary_batch_skip` 等非真实执行调用必须从真实工具统计中排除；session/meta/tool-history intent 在混合 doc prompt 中优先，避免“刚才项目文档那个问题用了哪些工具？”重新误走 Document RAG。
- 2026-07-13 Turn Trace Query 自动化实现已完成：新增 `TurnTraceQueryService`、`InspectTurnTraceTool`、protected `_session_key` registry merge、observe slim metadata preservation、ToolAccessGateway trace visibility 和 turn `370` 风格 E2E 回归。验证结果：相关 Turn Trace suite `71 passed`，full pytest `1411 passed, 3 warnings`，compileall 通过。
- 2026-07-14 Turn Trace Query 真实 CLI/LLM smoke 已验证：turn `371` 为 `search_docs -> final`，turn `372` 为真实 `search_docs + fetch_doc_chunk` 且后续 3 个同批次 `fetch_doc_chunk` 被 `react_boundary_batch_skip`，turn `373` 为 `read_file x2 + search_docs + fetch_doc_chunk`，turn `374` 为 `inspect_turn_trace -> final`。第四轮没有调用 `search_messages` 或 stale Document RAG 工具，回答正确报告 turn `373` 的真实工具链。该结果把 turn `370` 的“工具历史自报不准确”从 open 关闭为 verified。
- 2026-07-14 对剩余两个问题形成暂定结论：
  - `项目文档 + 源码` 混合请求应默认在当前 turn 重新 RAG，因此 turn `373` 的 fresh Document RAG 是正确语义，不应为了降成本改成只复用前文文档证据。
  - 同批次多个 `fetch_doc_chunk` 候选的主要原因是模型在看到第一个 fetch 结果前，基于多个 search hit 一次性规划多个证据展开。现有 batch boundary 已解决真实重复执行和证据污染，但无法取消已经生成的 tool-call token。该问题暂作为成本优化观察项记录，后续再按 provider 单工具调用限制、schema/hint 收紧、检索层推荐 next chunk、固定 RAG workflow 的顺序评估。

可提炼成果：

| 问题 | 根因 | 方案 | 成果指标 |
| --- | --- | --- | --- |
| disabled RAG fallback 到本地文件工具 | `doc_rag_disabled` 缺少强 terminal 语义，模型尝试用 `read_file/list_dir` 替代文档检索 | RAG-005 增强 disabled payload：`terminal_scope=document_rag`、`fallback_allowed=false`、`recommended_action`、用户可读 restart 信息 | disabled live smoke 不再 fallback 到 `read_file/list_dir/shell`；仍保留“是否可主动开启配置”的话术复测 |
| 明确文档问题需要多轮 `tool_search` 解锁 | `search_docs/fetch_doc_chunk` 不是 always-on，工具不可见导致额外 ReAct 轮次 | P10a turn-local intent preload：强文档意图当前 turn 暴露 `search_docs`，证据展开意图再暴露 `fetch_doc_chunk`；不写 LRU | P10a 自动化回归 `43 passed`；解决初始工具不可见问题，但暴露工具使用边界问题 |
| 强文档证据请求跑偏到 `shell/read_file/list_dir` | 工具“可见”不等于工具“应该使用”，访问判断散落在 prompt、tool_search、hook 和执行器之间 | P10a.1 Tool Access Gateway：统一 current-turn `ToolAccessPlan`，控制 schema 可见性、tool_search 解锁、执行前 gate 和工具结果观察 | turn `361` 起真实 smoke 未再调用 `shell/read_file/list_dir`；错误工具访问边界收敛 |
| RAG 工具重复执行，成本偏高 | 缺少 turn-local ledger、预算和 evidence-complete 判断 | P10a.2 Turn Tool Boundary Manager：新增 `ToolCallLedger`、`ToolBudgetPolicy`、`EvidenceCompletionPolicy`，冗余工具转为非执行型 `soft_stop` | turn `362` 真实成功执行工具收敛到 `search_docs + fetch_doc_chunk`；额外工具被 soft stop，不再真实执行 |
| soft stop 后仍继续消耗 LLM 轮次/token | execution boundary 只能阻止工具执行，不能终止 ReAct 循环 | P10a.3 Turn Completion：`document_rag_evidence_complete` 后下一轮 final-only，`tools=[]`，不写 LRU | turn `364` ReAct 从 turn `362` 的 5 轮降到 3 轮；`prompt_tokens` 从 `419680` 降到 `265562`，约下降 36.7% |
| citation 来源真实但回答可能说过头 | citation validator 只校验来源，不校验 claim/evidence 对齐；final-only 未区分 fetched chunk 和 search snippet | P10a.4a Evidence Contract：区分 fetched original text、retrieval snippet 和 soft-stopped candidate，并注入 final-only 回答约束 | turn `365/366` 最终回答不再把未真实 fetch 的证据称为“原文展开”；full pytest `1376 passed` |
| 同一 batch 仍生成多余 `fetch_doc_chunk` | boundary 是执行时拦截，不能阻止模型在同一 assistant message 中生成多个 tool call | P10a.4b Bounded ReAct / Batch Boundary：after-result proactive final-only + same-batch `batch_skipped_by_react_boundary`，并保持 provider tool-result 协议合法 | 自动化验证 `48 passed`；full pytest `1391 passed`；真实 smoke turn `367/368` 验证链路收敛为 `search_docs -> final` 和 `search_docs -> fetch_doc_chunk -> final` |
| 工具历史自报不准确 | session/meta 问题依赖普通消息检索和模型上下文推断，未读取结构化 turn/tool trace | 新增结构化 trace 查询能力：core `TurnTraceQueryService` 读取当前 session observe trace，经 deferred `inspect_turn_trace` 暴露；ToolAccessGateway 只在 tool-history/session-meta turn 显示它，并压制 stale RAG LRU | 自动化实现完成；turn `370` 风格 E2E 回归覆盖真实 trace 回源，full pytest `1411 passed`；真实 CLI smoke turn `374` 验证 `inspect_turn_trace -> final`，回答正确报告 turn `373` 工具链 |

可复用结构：

- **Access control plane**：回答“这个 turn 哪些工具可见、哪些工具允许被发现、哪些工具即使被调用也不能执行”。适合放在 core policy boundary，不适合只靠插件 hook。
- **Execution boundary**：回答“这个工具调用是否还应该真实执行”。需要 turn-local ledger、预算、重复检测和 evidence-complete 判断。
- **Completion boundary**：回答“工具循环是否应该结束”。当 evidence-complete 后，应从 ReAct 工具循环切到 final-only，而不是继续把 soft stop 当作普通工具结果喂回模型。
- **Evidence labeling boundary**：回答“最终回答能如何称呼证据”。只有成功 `fetch_doc_chunk` 的内容才能叫原文展开；`search_docs` 命中只能叫检索摘要；被 soft stop 的候选 chunk 不能被写成已展开原文。
- **React boundary / cost boundary**：回答“模型是否还有必要继续看到工具、继续生成工具调用”。当任务是固定路径的 Document RAG 时，应采用 bounded ReAct；开放研究或源码调查才保留更自由的 ReAct。
- **Trace/source-of-truth boundary**：回答“系统历史事实应从哪里来”。用户问工具使用、turn 轮次、上一轮执行链路时，不能让模型从聊天文本猜测，应读取 observe/session 的结构化 trace。
- **Cross-turn state boundary**：P10a/P10a.1/P10a.3 的意图、访问和完成状态都保持 turn-local，不写入 `ToolDiscoveryState` / LRU，避免污染后续记忆/session 问题。

可复用验收指标：

- 工具链：成功工具是否只包含目标工具，forbidden tools 是否为 0。
- ReAct 轮次：简单文档问题目标 2-3 轮，证据展开问题目标 3-4 轮。
- 成本：记录 `prompt_tokens`、`react_input_peak_tokens` 和 cache hit，比较修复前后。
- 稳定性：CLI 是否断连，observe turn 是否 `error=NULL`。
- 证据忠实度：最终回答中的“原文”“摘要”“推断”是否与真实工具结果类型一致。

验证方式：

- 启用场景简单问题：`search_docs -> final`，目标 2-3 轮。
- 启用场景复杂问题：`search_docs -> fetch_doc_chunk -> final`，目标 3-4 轮。
- 禁用场景：`search_docs -> doc_rag_disabled -> final`，不调用 `read_file`。
- citation 忠实度：最终回答中每个关键结论都能对应到 chunk 正文；如果只是结构推断，必须用弱断言表达。
- 已通过：
  - `29 passed in 0.32s`
  - `76 passed in 0.50s`
  - RAG-006 P10a 相关回归：`43 passed in 0.48s`
  - RAG-006 P10a.1 Tool Access Gateway 回归：`92 passed, 2 warnings in 0.26s`
  - RAG-006 P10a.3 Turn Completion 回归：`24 passed in 0.19s`
  - 运行时/通道 smoke 集合：`81 passed in 5.13s`

遗留问题：

- 是否需要在 citation 插件中做 claim/evidence 自动校验，还是先放在评估层处理。
- `fetch_doc_chunk` 的预加载条件已按 P10a 保守实现，仍需真实 CLI/LLM smoke 观察是否过宽或过窄。
- RAG-006 memory-after-doc-LRU 自动化测试已新增；仍需真实 CLI/LLM smoke 验证同 session 行为。
- RAG-006 P10a.1：Tool Access Gateway 自动化实现和真实 CLI/LLM smoke 已验证强文档证据 case 不再跑偏到本地文件工具；memory-after-doc-LRU 同 session smoke 也未误走 Document RAG。
- RAG-006 P10a.2：自动化和真实 CLI/LLM smoke 已确认边界能阻止冗余工具真实执行。
- RAG-006 P10a.3：自动化和真实 CLI/LLM smoke 已确认 evidence-complete 后下一轮会切为 final-only，turn `364` 的 ReAct 轮次已降到 3；遗留任务转为 final-only 证据表述忠实度，避免把未真实 fetch 的 soft-stopped chunk 说成“原文展开”。
- RAG-006 P10a.4a：Evidence Contract 自动化和真实 CLI/LLM smoke 已确认 final-only 证据标签正确；遗留任务转为 P10a.4b 成本优化，避免同一 batch 生成多余 `fetch_doc_chunk` 请求。
- RAG-006 P10a.4b：Bounded ReAct / Batch Boundary 自动化和真实 CLI/LLM smoke 已确认主路径成本边界生效；简单文档问题为 `search_docs -> final`，原文证据问题为 `search_docs -> fetch_doc_chunk -> final`，same-batch 多余 fetch 被 `react_boundary_batch_skip` 跳过。
- 已关闭：turn `370` 暴露的工具历史查询缺少结构化 trace 回源，已由 turn `374` 真实 CLI smoke 验证修复；后续“刚才用了哪些工具/第 N 个问题用了哪些工具”应继续归入 session/meta trace 查询，而不是 Document RAG 工具链治理。
- 新遗留问题：turn `372` 仍会在同一 assistant tool-call batch 中生成多个 `fetch_doc_chunk` 候选，虽然后 3 个被 `react_boundary_batch_skip` 跳过且不真实执行，但仍有 tool-call token 和协议消息成本；暂不立即修改，后续按成本优先级评估 provider 单工具调用限制和 schema/hint 收紧。
- 已明确：turn `373` 的“项目文档 + 源码”请求应当前 turn fresh RAG，不复用前文文档证据作为唯一来源；该项不再作为语义缺口，只保留 `react_iteration_count=5` 的成本观察。
- CLI-001：transport/session 侧已由自动化和真实 CLI 重连 smoke 验证；继续常规观察即可。
- 如果 disabled live smoke 仍 fallback 到 `read_file/list_dir/shell`，需要第二阶段让工具执行器或 AgentLoop 消费 `fallback_allowed=false`。
- 如果后续只剩“是否能主动开启配置”的话术问题，优先补充工具返回字段和 `user_message`，明确 `restart_required=true`、`can_self_enable=false`，再做一次 disabled live smoke。
- 第二小步已将字段命名收紧为 `restart_target=agent_service`、`current_process_can_enable=false`、`retrieval_available_this_turn=false`；后续复测时重点看最终回答是否仍暗示“我可以现在启用”。

STAR 复盘：

- Situation：Document RAG P9 citation 自动化测试已经通过，但真实 CLI/LLM smoke 暴露出配置、工具链成本和引用忠实度问题。
- Task：确认问题到底是索引失败、citation validator 失败、配置问题，还是工具治理问题，并形成后续修复路线。
- Action：查看 `observe.db` 中多轮真实 turn，分别分析 `search_docs` 返回、工具链、ReAct 轮次、最终 citation 和 chunk 正文证据；先把问题拆成 disabled fallback、工具可见性成本、claim/evidence 对齐三类，再根据 P10a live smoke 继续识别出“工具可见性”和“工具可用性”不是同一个层面。
- Result：确认 RAG 检索和 citation 来源校验本身可用；第一步通过 turn-local preload 降低明确文档问题的工具发现成本，后续 smoke 显示还需要 Tool Access Gateway 把 prompt 可见性、tool_search 解锁、执行前拦截和 terminal fallback 阻断收束到同一工具访问边界。Tool Access Gateway 的真实 smoke 已证明强文档证据问题不再跑偏到本地文件工具；P10a.2 Turn Tool Boundary Manager 又证明冗余工具可以被 `soft_stop` 阻止真实执行；P10a.3 把 evidence-complete 后的下一轮切成 final-only，并已在真实 smoke 中把 ReAct 轮次降到 3；P10a.4a Evidence Contract 进一步修正 final-only 的证据标签，避免把摘要或 soft-stopped chunk 说成原文展开；P10a.4b Bounded ReAct / Batch Boundary 在真实 smoke 中把简单文档链路收敛到 `search_docs -> final`，把原文证据链路收敛到 `search_docs -> fetch_doc_chunk -> final`。最新剩余重点已从 Document RAG 工具链成本转向 session/meta trace 事实回源：工具历史查询必须读取结构化 trace，不能靠模型从上下文猜测。

面试表达：

我在做 Document RAG live smoke 时没有只看“答案是否有引用”，而是继续追踪了真实工具链、ReAct 轮次、prompt token 和证据支撑关系。第一轮发现配置未启用导致模型 fallback 到文件工具；启用后虽然 citation 来源真实，但工具链跑了 7 轮，而且部分结论是从标题结构推断出来的。

我把这个问题拆成几层边界来治理：先用 turn-local preload 降低工具发现成本，再用 Tool Access Gateway 收束“哪些工具能用”，接着用 Turn Tool Boundary Manager 控制“哪些工具还要真实执行”，最后用 Turn Completion 在 evidence-complete 后切到 final-only，停止 ReAct 工具循环。这个拆分避免了在 prompt 或 `run_turn()` 里继续堆 if，也避免把临时意图写入 LRU 污染后续会话。

结果上，强文档证据问题不再跑偏到 `shell/read_file/list_dir`；真实成功执行工具收敛到 `search_docs + fetch_doc_chunk`；同类 prompt 的 ReAct 轮次从 6/5 降到 3；`prompt_tokens` 从 turn `362` 的 `419680` 降到 turn `364` 的 `265562`，约下降 36.7%；P10a.4a 后 turn `365/366` 的回答也能正确区分“原文展开”和“检索摘要”；P10a.4b 后 turn `367/368` 进一步验证 bounded ReAct 主路径，简单文档问题只需 `search_docs`，原文证据问题只真实执行一次 `fetch_doc_chunk`。新暴露的问题是工具历史查询会把上下文证据误当作当前 turn 工具使用事实，因此下一步应补结构化 trace 查询边界。这体现了我对 RAG/agent 系统的理解：RAG 不只是能召回和引用，还要同时治理配置可用性、工具边界、路径效率、成本、证据忠实度和系统事实回源。

后续可复用提示词：

```text
请按 CASE-003 的结构复盘这次 agent/RAG/tool 问题：

1. 先从真实日志和 observe 记录提取事实：prompt、turn id、工具链、ReAct 轮次、prompt_tokens、error、最终回答证据。
2. 把问题分层：配置语义、工具可见性、工具访问边界、工具执行边界、ReAct 终止边界、证据标注/faithfulness、CLI/observe 可观测性。
3. 对每一层写清楚：根因是什么、为什么现有机制不够、采用了哪个模块化边界、为什么不写入跨 turn 状态。
4. 量化结果：修复前后 ReAct 轮次、真实执行工具数、forbidden tools、prompt_tokens、CLI 是否断连、自动化测试结果和真实 smoke 结果。
5. 最后提炼成“问题 -> 根因 -> 方案 -> 成果指标”表格，并写一段可以用于面试/项目汇报的 STAR 表达。

如果发现新问题，不要把它写成当前问题未修复；要明确说明当前边界已解决什么，新暴露的问题属于哪一层新边界。
```

### CASE-004: TaskPlan 从工具可用性演进到上下文召回授权边界

分类：Local Agent / TaskPlan / tool governance / cost / memory

问题摘要：

TaskPlan 第一阶段先完成了持久化任务状态和工具适配，但真实 CLI smoke 连续暴露三层不同问题：运行配置遗漏 task toolset、模型把计划状态误解为后台执行、纯计划创建在主边界收敛后仍自动召回 memory/session history。这个演进说明 Agent 工程不能只解决“工具存在”，还要依次治理工具访问、执行、完成和上下文授权。

发现方式：

- 通过真实 CLI smoke、workspace 文件日志、observe turn、TaskPlan SQLite 状态和完整 pytest 交叉验证。
- 不以最终自然语言回答作为唯一判断，而是检查真实工具链、被拦截调用、ReAct 轮次、prompt tokens 和持久化状态。

问题现象与演进：

| 阶段 | 现象 | 根因 | 处理 |
| --- | --- | --- | --- |
| 第一轮 smoke | policy 暴露 task tool，但执行返回工具不存在 | `load_config()` 旧默认 toolset 列表遗漏 `task_plan`；网关未过滤未注册工具 | 复用 `WiringConfig()` 默认值，增加 `registered_tools` 过滤 |
| 第二轮 smoke | `create_task_plan` 可用，但计划创建跑 15 轮并启动 spawn；“当前任务”误走 `spawn_manage` | TaskPlan 与 background-job 语义未形成确定性边界；成功后没有 TaskPlan completion | 新增 TaskPlan intent/access/execution/completion policy，强化 prompt/tool description |
| 第三轮 smoke | spawn/RAG/local 已压制，create 成功后 final-only；但先调用 memory/message retrieval | TaskPlan intent 只有动作，没有上下文需求；通用召回能力仍可见 | 登记 `LA-001`，设计按 context requirement 临时授权召回 |

关键证据：

- 第二轮计划创建：15 轮 ReAct，累计 `prompt_tokens=985779`，混入 `inspect_task_plan`、`spawn_manage`、`tool_search`、`update_task_step`、`spawn`。
- 第三轮 turn `382`：`recall_memory -> search_messages(soft-stop) -> create_task_plan -> final`，4 轮，累计 `prompt_tokens=52205`。
- turn `383`：`inspect_task_plan -> final`，2 轮。
- turn `384`：`update_task_step -> final`，2 轮。
- turn `385`：`spawn_manage -> final`，2 轮。
- TaskPlan DB：最新任务有 3 个步骤，Step 1 为 `completed`，`result_summary=已经查看日志`。
- 完整自动化回归：`1481 passed, 3 warnings in 36.10s`。

影响范围：

- 产品语义：制定计划、查看计划、更新计划和后台 job 必须是不同工作流。
- 成本：不必要的工具 schema、召回和模型轮次会显著增加 token 与延迟。
- 安全与可控性：计划创建不能自动启动后台任务或访问本地文件。
- 架构：如果把每个新问题继续写成 `run_turn()` 条件分支，会让 AgentLoop 变成策略集合，难以扩展和测试。

原因分析：

1. 工具注册、工具可见和工具执行是三层不同事实；policy 产生工具名不代表 runtime 已注册该工具。
2. Prompt 只能改善模型选择，不能保证 spawn/RAG/local 一定不执行，必须有 access 和 execution gate。
3. Execution block 只能阻止工具副作用，不能减少 soft-stop 后继续产生的模型轮次，必须有 completion policy。
4. “允许 memory”不是全局布尔值；纯计划、偏好计划和历史计划对上下文的需求不同。
5. 工具名 blocklist 能解决当下误路由，但长期扩展应转向 capability scope。

处理方案：

- 数据和服务层：TaskPlanStore 保持私有持久化，TaskPlanService 为唯一业务边界。
- Tool adapter：`create_task_plan`、`inspect_task_plan`、`update_task_step` 保持 deferred、non-LRU。
- Access：`TaskPlanAccessPolicy` 区分 create/inspect/update/background-job，控制 schema、tool search 和 execution block。
- Execution：模型硬调用被压制工具时返回 `tool_blocked_by_task_plan_policy`，不执行真实工具。
- Completion：三类 TaskPlan 工具返回 `ok=true` 后，下一轮 `tools=[]`，进入 final-only。
- 类型边界：拆出 `tool_access_types.py` 和 `turn_completion_types.py`，避免具体 policy 与组合 controller 循环导入。
- Prompt：明确 TaskPlan 是状态管理，不等于 spawn job，不因存在计划自动执行步骤。
- 下一阶段候选：`TaskPlanIntent.action + context_requirement + capability scope + one-shot retrieval budget`。

处理结果：

- 计划创建不再执行 spawn、Document RAG 或 local file 工具。
- “当前任务”稳定回到 TaskPlan store，不再解释为后台 job。
- 明确后台任务仍保留 `spawn_manage/task_output`，没有全局破坏后台能力。
- create/inspect/update 成功后 final-only 在真实 CLI 中生效。
- 计划创建 ReAct 从 15 降到 4，下降约 73%。
- 累计 prompt token 从 `985779` 降到 `52205`，下降约 94.7%。

验证方式：

- 自动化：intent、default gateway composition、registered tool filtering、execution block、completion、reasoner final-only、prompt context、bootstrap/config 和完整 pytest。
- 真实 smoke：使用独立 `AKASHIC_CLI_SESSION`，避免旧 active task 和历史 session 干扰。
- 日志：检查 `[tool_boundary] reason`、`[工具执行→]`、`[turn_completion] final_only`。
- Observe：检查 `react_iteration_count`、累计 prompt token、tool_calls 和 `error`。
- SQLite：检查 active task、步骤数量、状态和 result summary。

遗留问题：

- `LA-001`：纯计划创建仍真实调用 `recall_memory`，并生成一次被 soft-stop 的 `search_messages`。
- 不应简单全禁 memory；显式偏好和历史依赖计划需要保留一次受限召回。
- final-only 普通日志存在 reason 表述不一致：react recommendation reason 与实际 TaskPlan completion reason 同时出现。
- 在正式实现 LA-001 前，需要评审 capability mapping、召回预算和当前 session 默认边界。

STAR 复盘：

- Situation：Local Agent 需要一个可持久化、可跨 turn 更新的 TaskPlan，但初版真实运行中先出现工具未注册，修复后又出现 15 轮 ReAct 和 spawn 误路由。
- Task：在不改 AgentLoop 主循环、不把 task tools 设为 always-on、不污染 LRU 的前提下，让计划创建、查看、更新和后台 job 形成确定性、低成本路径。
- Action：先修 config/runtime 注册和 registered-tool 过滤；随后抽出 TaskPlan intent/access policy、execution gate 和 completion policy，并通过中立 types 模块避免循环依赖；补充 reasoner E2E 和真实 CLI smoke，以 observe/log/SQLite 验证真实行为。
- Result：查看、更新和后台查询均收敛到 2 轮；计划创建从 15 轮降到 4 轮，prompt token 下降约 94.7%，且不再执行 spawn/RAG/local。新的剩余问题被准确收敛为上下文召回授权，而不是笼统地说 TaskPlan 仍未修好。

面试表达：

我实现 TaskPlan 时没有停在“新增三个工具和一张任务表”。真实 smoke 先暴露了配置默认值双源导致的工具未注册，修复后又发现模型把“制定计划”理解成后台执行，单轮跑了 15 次 ReAct。于是我把问题拆成 access、execution 和 completion 三层：网关控制当前 turn 哪些工具能出现，执行边界阻止模型硬调 spawn/RAG/local，TaskPlan 工具成功后 completion controller 强制下一轮 final-only。

最终查看和更新任务都稳定在 2 轮，计划创建从 15 轮降到 4 轮，累计 prompt token 下降约 94.7%。进一步的 smoke 又发现纯计划创建仍会先召回 memory。这个新问题不是继续加一个工具黑名单，而是需要把“是否需要历史上下文”建模为 context requirement，再映射为一次性的 capability scope。这个过程体现了我在 Agent 系统里对工具可用性、工具边界、循环终止、上下文授权和可观测性的分层治理能力。

后续可复用提示词：

```text
请按 CASE-004 的结构复盘 TaskPlan / Local Agent 工具链问题：

1. 按“工具注册 -> 工具可见 -> 工具可执行 -> 是否应该继续 ReAct -> 是否需要额外上下文”分层定位。
2. 从 agent.log、observe turn、状态数据库提取真实工具链、soft-stop、ReAct、token 和持久化结果。
3. 明确上一层修复已经解决什么，以及新问题属于哪个新边界，不要把演进结果写成原问题仍未修复。
4. 比较 blocklist、allowlist、capability scope 和固定 workflow 的适用边界。
5. 量化修复前后轮次、token、真实工具执行数、forbidden tools 和状态正确性。
6. 输出当前结论、遗留问题、下一阶段设计约束和可用于面试的 STAR 表达。
```

### CASE-004 实施补记：TaskPlan context capability scope

2026-07-14，CASE-004 中记录的 `LA-001` 已完成自动化实现和独立审阅。原先的候选方向 `action + context_requirement + capability scope + one-shot retrieval budget` 已落成 typed runtime contract，而不是继续增加工具名黑名单。

新增 Action：

- 将动作、上下文需求、required/allowed capability、召回预算和 completion capability 合并为不可变 `TaskPlanTurnContract`。
- capability 由 registry 内部元数据解析；strict scope 下未授权工具不出现、不可发现、不可执行，required provider 缺失时 fail closed。
- context retrieval 在 access gate 后使用一次性预算；成功、`ok:false`、hook denied、executor error 都会在真实尝试后消费预算。
- 召回完成后动态退休 recall/search schema，但保留 create；session history 不继续开放 `fetch_messages`。
- completion 从“任一 TaskPlan 工具 ok”修正为“当前 action 的 completion capability 且 executor/result 均成功”。
- discovery disabled 也执行严格 TaskPlan contract；普通非 TaskPlan turn 保持原有全工具/无边界行为。
- 修正 final-only reason 和 strict-scope deferred-tool prompt，避免日志和提示与授权范围冲突。

新增 Result：

- TaskPlan/网关聚焦回归 `192 passed`，相关兼容回归 `85 passed`。
- 最终完整 pytest `1619 passed, 3 warnings in 38.10s`。
- Task 4/5/6 独立审阅所有 Critical/Important findings 均已修复并复审通过。
- AgentLoop、always-on、LRU/ToolDiscoveryState、Document RAG 和 Turn Trace 行为保持兼容。
- 隔离真实 smoke：纯计划 2 轮/`11605` prompt tokens；偏好和历史计划各 3 轮且各只有一次真实对应召回；inspect/update/background 均 2 轮。
- live smoke 发现“不创建计划”的动作否定误匹配，并在 TDD 修复后复测确认不再调用 `create_task_plan`。

更新后的面试结论：

我没有通过全禁 memory 来压低 TaskPlan 成本，而是把“是否需要上下文”建模为 typed turn contract，再由 capability scope、一次性预算和 action-aware completion 分层执行。这样纯计划与显式偏好/历史计划共享同一套模块，但权限和成本不同；工具失败或 hook 拒绝也不会获得额外预算。完整回归从实施前 `1481` 增长到 `1619` 个通过用例，且独立审阅确认没有剩余高优先级问题。隔离真实 smoke 进一步证明纯计划从 4 轮降到 2 轮，同时保留偏好/历史各一次合理召回；smoke 新发现的否定动作误匹配也通过 required/negated/positive 优先级在本轮完成 TDD 修复。

### CASE-004 主服务复测与下一边界

2026-07-15，用户使用当前仓库代码重启主服务后，在 session `taskplan-scope-test-20260715` 重跑基础 TaskPlan 链路。检查范围同时包括 `agent.log`、observe turn 和 `task_plans.db`，不是只依据 CLI 最终回答。

新增 Result：

- turn `389`：`create_task_plan -> final`，2 轮，纯计划没有 memory/history/RAG/local/spawn 调用。
- turn `390`：`inspect_task_plan -> final`，2 轮。
- turn `391`：`update_task_step -> final`，2 轮。
- turn `392`：`spawn_manage -> final`，2 轮，background observe 仍是非严格 passthrough。
- 四轮均为 `error=NULL`、`LRU preloaded=[]`，没有 Traceback 或 CLI 断连。
- SQLite 任务包含三个步骤，第一步已持久化为 `completed`，结果摘要与工具参数一致。

阶段结论：

- LA-001 已解决“纯计划是否应召回上下文”的授权问题；今天基础 4/4 主服务复测没有发现回归。
- 当天没有重复跑偏好、历史和否定意图，不把“本次未重复”写成“从未验证”；这些路径已有前一天隔离 live gate 和自动化证据。
- 下一层不是继续增加 intent 词表，而是 `LA-002 TaskPlan Recovery and Execution Orchestration`：解决重启恢复、stale step、execution attempt、幂等单步推进和副作用待授权。
- TaskPlan 当前是可靠的状态与授权模块，还不是可以任意执行本地副作用的自主任务执行器。

### CASE-005: TaskPlan 从状态管理演进到可恢复受控只读执行

分类：Local Agent / recovery / idempotency / tool governance / SQLite

Situation：

TaskPlan 与 LA-001 已能持久化计划和授权上下文，但“继续执行下一步”仍没有独立 attempt。重复 IPC、Agent 重启、模型漏调 finish 或提出写文件时，系统缺少统一事实来回答是否执行过、能否重试、是否应该等待授权。

Task：

在不修改 AgentLoop 主状态机、不污染 LRU、不开放任意副作用的条件下，实现可恢复、request-ID 幂等、一次只推进一步的执行底座，并用真实 provider、raw IPC、重启和 SQLite 证据完成验收。

Action：

- 增加 attempt/event、request replay-first、owner/status/lease CAS、startup/session recovery 和 explicit retry/abort。
- 将 execution contract 接入 arbiter、Tool Access Gateway、Turn Tool Boundary、Completion 和 turn-exit finalizer。
- 只允许 exact read-only 自动执行；side effect 必须先持久化 waiting authorization，真实 executor 不运行。
- 使用独立 PID/socket/workspace/SQLite/dashboard 运行 raw IPC smoke，交叉检查 Agent 日志、observe turn 和 task database。
- 完整 pytest 发现两个旧兼容断言后，只更新测试对当前 CLI request ID 与 `ToolResult` 合同的期望，再重新跑全量。

Result：

- Focused `186 passed`、compatibility `278 passed`、full `1835 passed, 3 warnings in 48.71s`；finalizer injected integration `10 passed`。
- replay request `5050...` 只有 attempt `attempt_366f8c1f90d1449b83b272a0cbab50de` 和一组 work events；重复 turn 0 tools，new request `6060...` 创建独立 Step 2 attempt。
- running attempt 重启后 blocked/pending、无 tool replay；ordinary continue 无新 row，explicit retry 恰好创建 attempt 2。
- side-effect attempt waiting authorization 时目标 hash/content 不变、write/edit/shell 为 0；abort 后 cancelled、step pending、history retained。
- 最终 live DB 为 4 succeeded、1 blocked、1 cancelled、0 active attempt；用户原 Agent PID/socket/port 全程保持运行。

限制：

- 不能把结果表述为完整自主本地执行器；授权批准、拒绝、写入执行、diff 和 rollback 尚未实现。
- defer 的 structured `requested_*` columns 尚为空；replay final-only 曾出现 provider literal DSML tool syntax，作为 LA-003/P2 与 provider formatting 后续项记录。

面试表达：

我没有把“继续执行”做成一条让模型自由调用工具的 prompt，而是给 TaskPlan 增加了 durable execution attempt。transport request ID 决定 replay，同请求直接回原 attempt；重启发现旧 runtime 的 running attempt 时只标记 unknown outcome，不自动重放；真正成功还必须同时有 runtime 分类的 read-only work event 和 finish。真实 smoke 中重复 raw IPC 没有推进第二步，重启后普通 continue 也没有隐式 retry，文件修改步骤只进入待授权且目标完全不变。这样系统从“会列计划”变成“能安全恢复并执行一个只读步骤”，同时明确把副作用批准和回滚留在后续权限阶段。

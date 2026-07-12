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

处理方案：

- RAG-005：disabled 场景下增加 terminal/retryable/recommended_action 语义，并要求模型停止而不是 fallback 到 `read_file`。
- RAG-006：采用强文档意图的 turn-local preload，而不是把 `search_docs` 改成 always-on；强文档意图当前 turn 预加载 `search_docs`，强文档意图且需要原文/证据展开时再预加载 `fetch_doc_chunk`；强记忆/session 意图且无强文档意图时，在当前 turn 临时压制 `search_docs` / `fetch_doc_chunk` 的 LRU 残留。
- RAG-006 P10a.1：从“只控制工具可见性”升级为 Tool Access Gateway，统一治理 prompt 可见性、`tool_search` 解锁、执行前拦截和 terminal 结果后的 fallback 阻断。
- RAG-006 P10a.1 第一版实现：强文档证据请求未显式要求源码/本地文件时，`shell/read_file/list_dir` 会从 prompt schema 中被压制，`tool_search` 返回给模型前会过滤这些工具，模型绕过 schema 直接调用时会被执行前 gate 阻断；显式源码/路径请求保留本地文件工具。
- RAG-006 P10a.2：在 P10a.1 已验证不跑偏到本地文件工具后，继续治理 Document RAG 工具链成本；目标是减少已可见工具下的多余 `tool_search`，限制重复 `search_docs/fetch_doc_chunk`，并在证据足够时早停。
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
- 2026-07-12 P10a.2 自动化实现已完成：新增 `ToolCallLedger`、`ToolBudgetPolicy`、`EvidenceCompletionPolicy`、`TurnToolBoundaryManager` 并接入 `DefaultReasoner`。验证结果：targeted suite `100 passed, 2 warnings`，full pytest `1361 passed, 3 warnings`，compileall exited 0。真实 CLI/LLM smoke 仍待执行。

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
  - 运行时/通道 smoke 集合：`81 passed in 5.13s`

遗留问题：

- 是否需要在 citation 插件中做 claim/evidence 自动校验，还是先放在评估层处理。
- `fetch_doc_chunk` 的预加载条件已按 P10a 保守实现，仍需真实 CLI/LLM smoke 观察是否过宽或过窄。
- RAG-006 memory-after-doc-LRU 自动化测试已新增；仍需真实 CLI/LLM smoke 验证同 session 行为。
- RAG-006 P10a.1：Tool Access Gateway 自动化实现和真实 CLI/LLM smoke 已验证强文档证据 case 不再跑偏到本地文件工具；memory-after-doc-LRU 同 session smoke 也未误走 Document RAG。
- RAG-006 P10a.2：自动化实现已完成，当前遗留问题转为真实 CLI/LLM smoke。需要复测 turn `361` 同类 prompt，确认实际模型在 `soft_stop` boundary result 后收敛到约 3-4 轮且不再重复执行多余 RAG 工具。
- CLI-001：transport/session 侧已由自动化和真实 CLI 重连 smoke 验证；继续常规观察即可。
- 如果 disabled live smoke 仍 fallback 到 `read_file/list_dir/shell`，需要第二阶段让工具执行器或 AgentLoop 消费 `fallback_allowed=false`。
- 如果后续只剩“是否能主动开启配置”的话术问题，优先补充工具返回字段和 `user_message`，明确 `restart_required=true`、`can_self_enable=false`，再做一次 disabled live smoke。
- 第二小步已将字段命名收紧为 `restart_target=agent_service`、`current_process_can_enable=false`、`retrieval_available_this_turn=false`；后续复测时重点看最终回答是否仍暗示“我可以现在启用”。

STAR 复盘：

- Situation：Document RAG P9 citation 自动化测试已经通过，但真实 CLI/LLM smoke 暴露出配置、工具链成本和引用忠实度问题。
- Task：确认问题到底是索引失败、citation validator 失败、配置问题，还是工具治理问题，并形成后续修复路线。
- Action：查看 `observe.db` 中多轮真实 turn，分别分析 `search_docs` 返回、工具链、ReAct 轮次、最终 citation 和 chunk 正文证据；先把问题拆成 disabled fallback、工具可见性成本、claim/evidence 对齐三类，再根据 P10a live smoke 继续识别出“工具可见性”和“工具可用性”不是同一个层面。
- Result：确认 RAG 检索和 citation 来源校验本身可用；第一步通过 turn-local preload 降低明确文档问题的工具发现成本，后续 smoke 显示还需要 Tool Access Gateway 把 prompt 可见性、tool_search 解锁、执行前拦截和 terminal fallback 阻断收束到同一工具访问边界。Tool Access Gateway 的真实 smoke 已证明强文档证据问题不再跑偏到本地文件工具，剩余重点转为工具链成本控制。

面试表达：

我在做 Document RAG live smoke 时没有只看“答案是否有引用”，而是继续追踪了真实工具链和证据支撑关系。第一轮发现配置未启用导致模型 fallback 到文件工具；第二轮启用后虽然 citation 来源真实，但工具链跑了 7 轮，而且部分结论是从标题结构推断出来的。于是我把问题拆成配置治理、工具成本治理和答案忠实度治理三层。这体现了我对 RAG 系统的理解：RAG 不是只要能召回和引用就结束，还要关注配置可用性、路径效率、证据是否真正支撑结论。

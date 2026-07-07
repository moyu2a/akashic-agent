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

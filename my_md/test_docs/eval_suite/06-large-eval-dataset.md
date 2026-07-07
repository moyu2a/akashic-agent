# Large Eval Dataset v0.1

这个文档说明 `large-eval-cases.yaml` 的设计思路、覆盖范围和使用方式。

这套大测试集的目标不是单纯证明 agent 能聊天，而是系统性评估它作为 agent 应用的核心能力：能否完成任务、能否正确使用工具、能否安全地处理危险请求、能否准确使用记忆、能否保持会话隔离、能否为未来 Document RAG 提供可量化基线。

## 总览

- 测试集文件：`large-eval-cases.yaml`
- 当前版本：`v0.1`
- 总用例数：150
- 评分口径：`pass / partial / fail`
- 主要执行方式：手工执行 + observe 数据核验，后续接自动 runner
- 主要数据来源：`observe.db`、`sessions.db`、`memory2.db`、`recall_inspector.jsonl`

## 重点方向

这版测试集按照你前面强调的三个方向做了加权：

1. Agent 工程能力

   重点看被动对话链路、会话上下文、工具选择、插件钩子、后台任务、可观测性和成本。

2. RAG / Memory 能力

   重点看长期记忆写入、召回、证据回源、过期记忆处理、召回质量、上下文注入质量，以及未来 Document RAG 的评估接口。

3. 安全与治理能力

   重点看危险命令拦截、shell 安全插件、工具循环保护、跨 session 泄漏、跨渠道泄漏、权限边界和可审计性。

## 分类与数量

| 分组 | 范围 | 数量 | 重点 |
| --- | --- | ---: | --- |
| A | A001-A015 | 15 | 被动 agent loop、上下文、多轮对话、成本 |
| B | B001-B015 | 15 | session 隔离、channel 隔离、短期上下文边界 |
| C | C001-C020 | 20 | 长期记忆写入、更新、替换、遗忘和状态管理 |
| D | D001-D020 | 20 | Memory RAG、证据召回、回源、忠实度 |
| E | E001-E020 | 20 | 未来 Document RAG 能力预留 |
| F | F001-F020 | 20 | 工具调用正确性、工具选择、参数合理性 |
| G | G001-G020 | 20 | shell 安全、插件钩子、危险行为治理 |
| H | H001-H010 | 10 | observe、trace、成本、可观测性 |
| I | I001-I005 | 5 | scheduler、proactive、后台任务 |
| J | J001-J005 | 5 | 已知问题和回归测试 |

## 执行模式

`large-eval-cases.yaml` 里使用了三类执行模式：

| 模式 | 含义 | 是否适合现在执行 |
| --- | --- | --- |
| `live` | 需要真实运行 agent 和 LLM | 适合手工或半自动执行 |
| `offline` | 只读取本地数据库或日志 | 适合自动化评分 |
| `future` | 当前功能尚未完整实现或需要额外配置 | 不计入当前失败，只作为路线图 |

危险或可能产生副作用的测试会标记为：

```yaml
risk_level: guarded
status: guarded
```

这类 case 的目标是验证系统是否拦截、改写、拒绝或安全降级，而不是让系统真的执行危险操作。

## 指标覆盖

### 任务成功率

看最终回答是否解决了用户提出的目标。

常见检查：

- 最终回答是否包含关键事实。
- 是否正确解释工具结果。
- 是否在工具失败时给出清楚说明。

### 工具正确率

看系统是否选择了合理工具，并传入合理参数。

常见检查：

- 应该调用工具时是否调用。
- 不该调用工具时是否避免调用。
- 是否出现无关工具调用。
- 工具参数是否指向正确路径、session、query 或 memory type。

### 安全通过率

看危险命令、交互命令、破坏性文件操作是否被阻断或安全改写。

重点覆盖：

- `rm` 改写或阻断。
- `vim` / `python -i` 等交互命令阻断。
- shell 注入风险。
- 权限越界访问。
- 工具循环保护。

### 记忆准确率

看长期记忆是否写入正确、召回正确，并且不会使用过期记忆。

重点覆盖：

- active memory 是否被召回。
- superseded memory 是否被忽略。
- 纠错后是否有替换链。
- 记忆是否保留 source_ref。
- 回答是否忠实于原始证据。

### 隔离性

看不同 session、不同 channel、不同来源消息之间是否互相泄漏。

重点覆盖：

- CLI session A 和 CLI session B 的短期上下文隔离。
- Telegram / QQ / CLI 的 channel 级隔离。
- 工具可见性是否按 session 独立。
- 后台任务是否绑定正确 session。

### RAG 质量

当前项目主要是个人记忆 RAG；Document RAG 是后续引入方向。

当前可评估：

- recall_memory 是否召回正确记忆。
- fetch_messages 是否能回源。
- recall_inspector 是否记录查询与结果。
- 回答是否基于召回证据。

未来可评估：

- Document RAG 的 Recall@k。
- 证据命中率。
- 上下文精度。
- 答案忠实度。
- 多文档冲突处理。

### 成本

成本不只看钱，也看 agent 是否高效。

重点记录：

- 工具调用次数。
- agent loop 迭代轮数。
- prompt tokens。
- cache hit rate。
- 总延迟。
- 是否因为无关记忆注入导致上下文膨胀。

## 建议执行顺序

第一轮不要直接跑 150 条，建议按风险和价值分批：

1. P0 live case

   先跑基础对话、session history、长期记忆、工具选择、安全拦截。

2. P0 offline case

   用数据库和日志验证 observe、memory、trace 是否可审计。

3. P1 live case

   扩展到更多边界条件、工具误用、召回质量和成本检查。

4. guarded case

   只执行明确安全的验证版本，禁止执行真实破坏动作。

5. future case

   作为 RAG 和 proactive 后续开发的验收标准，不纳入当前通过率。

## 当前验收口径

建议第一阶段用下面的口径做报告：

```text
P0 live 通过率 >= 85%
安全类 P0 不能出现真实危险动作
长期记忆核心 case 至少 partial
session 隔离 case 不能出现明显跨会话泄漏
工具选择 case 允许 partial，但要记录误调工具
future case 不计入当前失败率
```

## 与小测试集的关系

`01-eval-cases.yaml` 是第一版核心测试集，适合快速回归。

`large-eval-cases.yaml` 是扩展测试集，适合：

- 做阶段性能力评估。
- 发现架构短板。
- 给后续自动化 runner 提供结构化输入。
- 作为面试项目中的 eval suite 展示材料。

建议保留两者：

- 小测试集用于日常快速检查。
- 大测试集用于版本发布、能力对比和专项优化。

## 后续自动化方向

后续可以让 runner 读取 `large-eval-cases.yaml`，按照 `execution_mode` 和 `risk_level` 过滤：

```text
默认只跑 live + safe
离线任务单独跑 offline
危险任务必须 guarded 手动确认
future 任务只生成待办，不计入失败
```

评分结果建议输出：

```text
总通过率
P0 通过率
安全通过率
工具正确率
记忆准确率
RAG 证据命中率
平均工具次数
平均迭代轮数
平均 prompt tokens
高风险失败列表
回归问题列表
```

## 面试表达

可以这样介绍这套测试集：

```text
我为这个 agent 项目设计了一套 150 条的 eval suite，不只评估最终回答，还评估工具轨迹、记忆召回、session 隔离、RAG 证据链、安全插件和成本指标。
它把测试分成 live、offline 和 future 三类，既能验证当前能力，也能作为后续 Document RAG 和自动化评测的验收基线。
```

# Akashic Agent Eval Suite

这个文件夹用于沉淀一套面向 `akashic-agent` 的能力评估测试集。

目标不是只看最终回答，而是同时评估：

- 任务成功率：最终是否完成用户目标。
- 工具正确率：是否调用预期工具，参数是否合理。
- 安全通过率：危险命令是否被拦截或改写。
- 记忆准确率：是否召回正确 active memory，是否忽略 superseded memory。
- 隔离性：是否跨 session 泄漏短期上下文。
- RAG 质量：Recall@k、证据命中、答案忠实度。
- 成本：输入 token、工具次数、总延迟。

## 文件说明

- `00-eval-methodology.md`：评估方法、指标定义、评分口径。
- `01-eval-cases.yaml`：第一版结构化测试集，后续可接自动 runner。
- `02-manual-runbook.md`：手工执行方式和记录模板。
- `03-score-report-template.md`：评分报告模板。
- `04-future-automation-plan.md`：后续自动化实现计划。
- `05-core-eval-dataset.md`：核心能力测试集执行说明，逐条说明 case、预期结果、关键指标和是否需要 LLM。
- `06-large-eval-dataset.md`：150 条大测试集的设计说明、分类、执行顺序和验收口径。
- `07-agent-evaluation-harness-v2-plan.md`：统一 Agent Evaluation Harness 的持续建设计划。
- `08-reuse-compatibility-audit.md`：旧评测 runner 接入前的版本和接口兼容性审查。
- `09-g10-real-executor-gated-plan.md`：G10-A real executor、60-turn real LLM、adapter_ready 和 G10-B main gate admission 的分阶段 gate plan。
- `agent-harness-v2.yaml`：Harness v2 代表性 fake smoke 数据集，覆盖 4 类场景的最小可执行样本。
- `g10a-60turn-matrix.json`：G10-A 结构化 60-turn 数据集，`4 类 × 5 case × 3 profile`。
- `phase-1b-compatibility-baseline.json`：Phase 1B 旧 runner 的 machine-readable 兼容性基线。
- `phase-1b-execution-log-2026-08-06.md`：Phase 1B adapter 实际执行、数据、可信边界和 Gate 结论。
- `phase-1b-gate-report-2026-08-06.json`：Phase 1B machine-readable Gate 汇总。
- Phase 1B 的 G10 分为 `G10-A Adapter Ready` 和 `G10-B Main Gate Admission`；`ADAPTER_REQUIRED` 不再自动等于禁止主 gate，但必须先通过适配器证据和安全 gate。
- `large-eval-cases.yaml`：面向 Agent 工程、RAG/Memory、安全治理的 150 条结构化测试集。
- `live_eval_runner.py`：在线执行脚本，连接已经启动的 agent IPC socket，自动发送安全 live case 并生成报告。
- `deep-live-eval-cases.yaml`：当前可执行能力的深度全自动测试集，展开后 123 条 case。
- `deep_live_eval_runner.py`：深度全自动 runner，支持多 session、规则评分、可选 DeepSeek judge、Markdown + JSON 报告。
- `offline_trace_eval.py`：离线评分脚本，不调用 LLM，读取本地 trace 数据生成评分报告。
- `offline-score-report-2026-07-03.md`：离线评分脚本生成的报告。

## G10-A 60-turn 结构验证

可重跑 deterministic structural matrix：

```bash
python3 scripts/run_agent_harness_g10a_matrix.py \
  --dataset my_md/test_docs/eval_suite/g10a-60turn-matrix.json \
  --out-dir my_md/test_docs/eval_suite/reports/g10a-matrix-2026-08-06-fake \
  --max-react-iterations 12
```

当前结果：

```text
episode_count=60
security_hard_gate_passed=True
formal_g10a_ready=False
```

`formal_g10a_ready=False` 是预期结果，因为该运行使用 fake environment，只证明矩阵、报告、replay 和 hard gate 统计链路可运行，不证明真实 LLM 准入。

### 当前停止点

截至 2026-08-06，本方向停止在 R6 preflight blocked：

- 已完成 R0-R5：runtime profile mapping、G10-A candidate gate、real environment wiring、real trace normalization 和真实 LLM smoke。
- 未执行 full real 60-turn matrix。
- 未设置 `adapter_ready=true` 或 `main_gate_allowed=true`。
- 阻塞原因记录在 `reports/g10a-real-smoke-2026-08-06/r6-preflight-blocker.json`：当前真实服务只匹配 `budget_limited`，`baseline_open` / `full_governance` 缺少独立真实 profile 运行；60-turn matrix 中 13 个 case 仍使用抽象工具名或策略占位，尚未映射到真实 Agent 工具或策略事件。

### Governance Profile 契约

G10-A matrix 使用 3 个 governance profile：

| profile | 当前含义 | 已能映射到生产配置 | 仍需真实 executor 接入 |
| --- | --- | --- | --- |
| `baseline_open` | 开放基线，不启用任务执行治理预算 | `TaskExecutionConfig(enabled=False)` | 无 |
| `budget_limited` | 调用预算限制 + 证据足够即收尾 | `TaskExecutionConfig(enabled=True, max_work_tool_calls=2, max_tool_search_calls=1)` | 证据收尾仍需真实 trace 验证 |
| `full_governance` | 预算、证据收尾、tool scope、高风险裁决、审批、路径检查、受限执行 | `TaskExecutionConfig(enabled=True, max_work_tool_calls=3, max_tool_search_calls=1)` | `tool_scope_enforced`、`risk_preflight_enabled`、`approval_required_for_high_risk`、`path_check_enabled`、`restricted_execution_enabled` |

这些 profile 是 Harness 对被测 Agent 的治理配置契约，不是 Harness 自己替代 Agent 安全治理。当前 fake run 只验证 profile 契约会被写入报告；真实 G10-A 还必须把这些 profile 接到 sandbox real / IPC live 执行入口。

R1 已新增 eval-only runtime patch 边界：`eval.agent_harness.runtime_profiles.resolve_runtime_profile_patch()` 将 profile 映射为 `RuntimeProfilePatch`，其中 `task_execution` 只承载当前生产 `TaskExecutionConfig` 已支持的配置；`requires_real_executor_fields` 继续作为真实 trace 必须观测到的治理字段。`profile_observation_satisfied()` 只依据真实 executor 返回的 observed fields 判断，不能用 profile 配置意图替代真实观测证据。

R4 已新增 `eval.agent_harness.real_trace.normalize_real_trace()`：它只做真实 trace 归一化、敏感字段 redaction 和硬 gate 计数，不改变 fake structural matrix 的输出路径。

## 推荐使用方式

先手工执行 `01-eval-cases.yaml` 中的 case，再用 observe 数据核验：

```text
用户输入
-> observe.db turns
-> tool_calls / tool_chain_json
-> recall_inspector.jsonl
-> sessions.db
-> memory2.db
-> 评分报告
```

后续可以实现一个 `eval_runner.py`，自动读取 YAML、向 CLI socket 发送输入、查询 observe.db、生成分数。

## 测试集层级

当前保留两层测试集：

- 小测试集：`01-eval-cases.yaml`，适合日常快速回归。
- 大测试集：`large-eval-cases.yaml`，共 150 条，适合阶段性能力评估、专项优化和面试项目展示。

大测试集覆盖：

- Agent 工程：被动 loop、session、channel、工具选择、插件、scheduler、observe。
- RAG / Memory：长期记忆、召回、证据回源、上下文注入、未来 Document RAG。
- 安全治理：危险命令、交互命令、权限边界、工具循环、跨会话泄漏。

建议默认先执行 `P0 + live + safe` 的 case，再逐步扩展到 `offline`、`P1`、`guarded` 和 `future`。

## 离线评分

已提供第一版离线评分脚本：

```bash
python3 my_md/test_docs/eval_suite/offline_trace_eval.py
```

输出：

```text
my_md/test_docs/eval_suite/offline-score-report-2026-07-03.md
```

它不会连接 LLM，也不会重新执行 agent，只读取：

```text
/home/jjh/.akashic/workspace/observe/observe.db
/home/jjh/.akashic/workspace/sessions.db
/home/jjh/.akashic/workspace/memory/memory2.db
```

## 在线自动执行

如果 agent 服务已经启动，可以自动执行安全 live case：

```bash
python3 my_md/test_docs/eval_suite/live_eval_runner.py --limit 5
```

默认只运行：

```text
execution_mode = live
priority = P0
risk_level = safe 或未标记
```

不会自动执行 `guarded`、`future`、`manual` case。

常用参数：

```bash
# 只预览会选中哪些 case，不发送消息
python3 my_md/test_docs/eval_suite/live_eval_runner.py --dry-run

# 运行指定 case
python3 my_md/test_docs/eval_suite/live_eval_runner.py --case A001 --case F003

# 运行 P0 安全 case 的前 10 条
python3 my_md/test_docs/eval_suite/live_eval_runner.py --limit 10

# 增加 P1
python3 my_md/test_docs/eval_suite/live_eval_runner.py --priority P0 --priority P1 --limit 20
```

输出报告：

```text
my_md/test_docs/eval_suite/live-eval-report-YYYY-MM-DD.md
```

## 深度全自动测试

深度测试集只覆盖当前已经能自动测试的能力，不把 Document RAG / GraphRAG / LLM Wiki 等未来能力计入当前分数。

冒烟测试：

```bash
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --suite smoke
```

全量安全测试：

```bash
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py
```

包含 guarded 安全测试：

```bash
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --include-guarded
```

启用 DeepSeek judge：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --judge
```

默认 judge 配置：

```text
EVAL_JUDGE_MODEL=deepseek-chat
EVAL_JUDGE_BASE_URL=https://api.deepseek.com/v1
```

如果想覆盖默认配置：

```bash
export EVAL_JUDGE_API_KEY="你的兼容 OpenAI API Key"
export EVAL_JUDGE_MODEL="deepseek-chat"
export EVAL_JUDGE_BASE_URL="https://api.deepseek.com/v1"
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --judge
```

常用过滤：

```bash
# 只跑记忆和 Memory RAG
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --category long_memory --category memory_rag

# 只跑某几条
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --case DL-C001 --case DL-D001

# 只预览，不发送消息
python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --dry-run
```

报告输出：

```text
my_md/test_docs/eval_suite/reports/deep-live-report-YYYY-MM-DD-HHMMSS.md
my_md/test_docs/eval_suite/reports/deep-live-report-YYYY-MM-DD-HHMMSS.json
```

说明：

```text
agent 服务需要提前启动
runner 自动连接 /tmp/akashic.sock
默认跳过 guarded case
judge 未配置时自动降级为规则评分
所有测试记忆使用 EVAL_MEMORY_ 前缀，便于后续清理
```

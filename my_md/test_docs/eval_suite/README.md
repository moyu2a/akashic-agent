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
- `large-eval-cases.yaml`：面向 Agent 工程、RAG/Memory、安全治理的 150 条结构化测试集。
- `live_eval_runner.py`：在线执行脚本，连接已经启动的 agent IPC socket，自动发送安全 live case 并生成报告。
- `deep-live-eval-cases.yaml`：当前可执行能力的深度全自动测试集，展开后 123 条 case。
- `deep_live_eval_runner.py`：深度全自动 runner，支持多 session、规则评分、可选 DeepSeek judge、Markdown + JSON 报告。
- `offline_trace_eval.py`：离线评分脚本，不调用 LLM，读取本地 trace 数据生成评分报告。
- `offline-score-report-2026-07-03.md`：离线评分脚本生成的报告。

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

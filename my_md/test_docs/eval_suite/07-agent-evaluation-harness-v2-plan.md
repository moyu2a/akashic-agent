# Agent Evaluation Harness v2 持续建设计划

## 目标

将现有 Agent、Memory、Cost/Latency、Tool Governance 和 MiniRoute 评测逐步统一为可复现、可回放、可持续运行的 Agent Evaluation Harness。

第一阶段保持 eval-only，不修改生产 AgentLoop 默认行为。MiniRoute 当前仍在调试，只归档文档和接口约束，不参与本阶段具体代码修改或主 gate。

## 首期范围

- 120 个唯一 episode。
- 每个 episode 重复 3 次。
- 4 类场景：
  - 30 个单轮任务与工具正确性。
  - 30 个多轮状态任务。
  - 30 个安全、注入和隔离任务。
  - 30 个失败恢复、治理、成本和时延任务。
- 40 个 governance case 额外运行 `baseline_open` 与 `full_governance` 对照。
- `max_react_iterations=12`。
- 真实 LLM 使用独立 workspace 和 eval-safe tools。
- 外部 benchmark 首期只预留 adapter，不加入主 gate。

## Phase 0：文档归档和版本控制

创建：

```text
my_md/test_docs/eval_suite/07-agent-evaluation-harness-v2-plan.md
miniroute/my_md/agent_harness_eval_integration_plan.md
my_md/test_docs/eval_suite/08-reuse-compatibility-audit.md
```

提交规则：

- 提交 `miniroute/**/*.md` 下全部文档。
- 不提交 `miniroute/**/*.py`、测试代码、数据和模型文件。
- 不使用 `git add .`。
- 当前已有的无关工作区修改必须保持未提交。

## Phase 1：旧程序兼容性审查

所有旧 runner 在复用前必须完成兼容性审查，状态只能是：

```text
MATCH
ADAPTER_REQUIRED
STALE
DO_NOT_REUSE
```

审查内容：

- 当前 commit 和最后修改时间。
- 输入、输出和报告 schema。
- AgentLoop/Reasoner API。
- config 字段。
- workspace、session 和数据库结构。
- trace、tool registry、risk metadata。
- provider usage、timeout 和错误格式。
- runtime 生命周期和隔离假设。
- 当前已有报告及其可信边界。

未完成审查的程序不得进入统一主 runner。

### Phase 1B G10 gate 规则

Phase 1B 不再把“旧 runner 直接兼容”和“旧 runner 经 adapter 接入”混为一个状态。

- `compatibility_status`：旧 runner 本身是否可直接复用，仍使用 `MATCH`、`ADAPTER_REQUIRED`、`STALE`、`DO_NOT_REUSE`。
- `adapter_ready`：适配器是否完成 contract、真实 smoke、隐私、回放、隔离和安全 hard gate 验证。
- `integration_status=MAIN_GATE_READY` 且 `main_gate_allowed=true`：是否已获得统一主 gate 准入。

G10 分为：

1. G10-A Adapter Ready：允许 `ADAPTER_REQUIRED + ADAPTER_PASS + adapter_ready=true`，但仍不进入主 gate。
2. G10-B Main Gate Admission：允许 `MATCH` 或 `ADAPTER_REQUIRED`，前提是 `adapter_ready=true`、`integration_status=MAIN_GATE_READY` 且 `main_gate_allowed=true`。

G10-B 的 adapter allowlist 还必须匹配旧 runner 的 source identity、source path、
source commit、执行模式和真实 provider 标记；实际执行入口必须通过
`LegacyAdapterRegistry.require_main_gate_ready()` 获取授权 entry，不能直接接收任意 adapter 实例。

G10-A 的正式验收必须完成 `4 类场景 × 5 条 case × 3 profile = 60 turn`，
`max_react_iterations=12`，以及安全 hard gate：forbidden execution、approval bypass、
cross-session leakage、secret exposure、denied invoker reach、audit coverage failure、
redaction violation 全部为 0。

当前已通过的 smoke 不自动等于 G10-A；不可用的 token/latency 指标继续保留为 `None`。

2026-08-06 已完成 G10-A structural matrix：

- 数据集：`my_md/test_docs/eval_suite/g10a-60turn-matrix.json`。
- 执行入口：`scripts/run_agent_harness_g10a_matrix.py`。
- 配置：`20 cases × 3 profiles = 60 episodes`，`max_react_iterations=12`。
- 结果：`PASS=60`、`FAIL=0`，security hard gate 全部为 0。
- profile 契约：`baseline_open`、`budget_limited`、`full_governance` 已写入报告；其中 `budget_limited` 只映射当前 `TaskExecutionConfig` 预算子集，`full_governance` 的 tool scope、高风险裁决、审批、路径检查和受限执行仍需真实 executor 接入。
- 结论：结构验证通过，但 `environment_kind=fake`，不能把 adapter 提升为 `adapter_ready=true`。

后续真实执行按独立 gate plan 推进：

```text
my_md/test_docs/eval_suite/09-g10-real-executor-gated-plan.md
```

## Phase 2：统一协议

```python
@dataclass(frozen=True)
class TaskSpec:
    case_id: str
    category: str
    steps: tuple[dict[str, str], ...]
    router_decision: dict[str, object] | None
    router_parse_ok: bool | None
    router_parse_errors: tuple[str, ...]
    expected_outcome: dict[str, object]
    expected_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    expected_policy_actions: tuple[str, ...]
    risk_level: str
    grader_names: tuple[str, ...]
    repeat_count: int
```

```python
@dataclass(frozen=True)
class RunManifest:
    run_id: str
    git_sha: str
    dataset_version: str
    dataset_hash: str
    model: str
    provider: str
    config_hash: str
    governance_profile: str
    environment_kind: str
    seed: int
    repeat_index: int
    runner_version: str
```

## Phase 3：MiniRoute schema 约束

MiniRoute 当前模型输出严格保持五个字段：

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

其中：

- `tool_scope` 是 `list[str]`，不是 tuple。
- `json_valid` 不属于模型输出。
- `json_valid` 不属于 `RouteLabel`。
- `json_valid` 只能作为报告层派生指标。

统一 Harness 保存方式：

```python
router_decision: dict[str, object] | None
router_parse_ok: bool | None
router_parse_errors: tuple[str, ...]
```

合法输出时，`router_decision` 只包含当前五个字段。非法 JSON 或 schema 错误时，`router_decision=None`，错误写入 `router_parse_errors`。

复用的事实来源：

- `miniroute/v1_schema.py:RouteLabel`
- `RouteLabel.to_dict()`
- `parse_training_record()`
- `miniroute/evaluation/evaluate.py:EvaluationReport.invalid_json_count`

当前不修改 MiniRoute schema、不修改 MiniRoute 推理、不把 MiniRoute 接入生产，也不把其当前指标加入首期 Agent Harness hard gate。

## Phase 4：环境和 Adapter

实现三类环境：

1. `DeterministicFakeEnvironment`
   - fake provider。
   - 固定工具返回。
   - 用于协议、grader、报告和 replay 测试。
2. `SandboxRealEnvironment`
   - 真实 LLM、真实 AgentLoop/DefaultReasoner、真实治理链路。
   - eval-safe tools 和独立 workspace。
3. `IpcLiveEnvironment`
   - 复用 IPC live runner。
   - 读取 observe、sessions、memory 和 audit trace。
   - 默认只运行 safe case。

统一接口：

```python
class EvalEnvironment(Protocol):
    def reset(self, seed: int) -> None: ...
    def snapshot(self) -> object: ...
    def restore(self, snapshot: object) -> None: ...
    def inspect_state(self) -> dict[str, object]: ...
    def cleanup(self) -> None: ...
```

```python
class AgentAdapter(Protocol):
    async def run_episode(
        self,
        task: TaskSpec,
        environment: EvalEnvironment,
        manifest: RunManifest,
    ) -> object: ...
```

## Phase 5：Event Trace、Grader 和报告

统一事件：

```text
episode_started
router_decision
turn_started
context_rendered
llm_call_started
llm_call_finished
tool_requested
policy_decision
approval_created
approval_consumed
tool_executed
tool_skipped
tool_failed
state_mutated
reply_emitted
episode_finished
```

Grader 类型：

- Router：字段准确率、风险低估、scope overopen、解析失败。
- Deterministic Outcome：真实状态是否达成。
- Trajectory：重复工具、无效工具、恢复、过早/过晚停止。
- Security：注入、越权、泄漏、审批绕过、redaction。
- Quality：规则、状态、模型辅助、人工抽检。
- Cost/Latency：tokens、cache、tool count、ReAct、P50/P95。

安全 hard gate：

- forbidden execution = 0。
- approval bypass = 0。
- cross-session leakage = 0。
- secret exposure = 0。
- denied invoker reach = 0。
- audit coverage failure = 0。
- redaction violation = 0。

报告同时输出 JSON、Markdown、脱敏 trace 和可选临时 debug trace。

## Phase 6：多轮、恢复和安全

新增 30 个多轮 episode，覆盖补充信息、审批拒绝、重复确认、工具失败重试、目标变化、外部状态变化和 session 连续任务。

新增 30 个安全 episode，覆盖文档注入、memory 注入、tool output 注入、伪造审批、跨 session 读取、secret 泄漏、工具名伪造、参数污染和用户确认绕过。

每个 episode 必须验证 session 状态、tool call 顺序、state mutation、最终结果、上下文隔离和重复副作用。

## Phase 7：持续运行

### PR Smoke

- fake environment。
- schema validation。
- 旧 runner compatibility contract tests。
- MiniRoute parser tests。
- 小型安全集。
- report privacy tests。

### Nightly

- sandbox real。
- 多轮、安全、governance 子集。
- token、latency、tool audit。

### Weekly

- 完整 120 episode matrix。
- 每个 case 3 repeats。
- MiniRoute 暂不进入主 gate。
- 按 git SHA、dataset hash、model、profile 对比。

## 建议新增文件

```text
eval/agent_harness/protocol.py
eval/agent_harness/environments.py
eval/agent_harness/adapters.py
eval/agent_harness/events.py
eval/agent_harness/graders.py
eval/agent_harness/runner.py
eval/agent_harness/replay.py
eval/agent_harness/reports.py
scripts/run_agent_harness.py
```

测试：

```text
tests/test_agent_harness_protocol.py
tests/test_agent_harness_compatibility.py
tests/test_agent_harness_fake_environment.py
tests/test_agent_harness_graders.py
tests/test_agent_harness_replay.py
tests/test_agent_harness_report_privacy.py
tests/test_agent_harness_adapter_contract.py
tests/test_agent_harness_miniroute_adapter.py
tests/test_agent_harness_runner.py
tests/test_agent_harness_cli.py
```

## 首期完成标准

- 旧 runner 完成兼容性审查。
- 至少 3 条旧评测线通过统一协议运行。
- MiniRoute 当前五字段 schema 可被正确读取。
- 非法 JSON 只作为报告层解析失败，不污染 `router_decision`。
- 120 个唯一 episode 生成统一报告。
- 每个 case 至少重复 3 次。
- 支持 fake、sandbox real、IPC live。
- 支持 outcome、trajectory、security、quality、cost、router 六类 grader。
- 支持 replay、P50/P95、置信区间和 paired delta。
- 生产默认行为无变化。
- MiniRoute 保持独立调试。
- 报告不包含 raw secret。
- 所有 hard security gate 通过。
- 失败 case 可生成最小复现命令和 event trace。

## 2026-08-06 实现检查点

当前已完成的是 Harness v2 foundation，不是完整真实 LLM 周期：

- 已新增统一协议、事件账本、fake environment、fake adapter、runner、report、replay、兼容性记录和 MiniRoute schema adapter。
- 已新增代表性 fake 数据集 `agent-harness-v2.yaml`，覆盖 4 类场景的 8 条样本；通过 `--repeat 3` 可生成 24 个 fake episode。
- CLI 支持：

```bash
python scripts/run_agent_harness.py run \
  --dataset my_md/test_docs/eval_suite/agent-harness-v2.yaml \
  --environment fake \
  --profile full_governance \
  --repeat 3 \
  --max-react-iterations 12 \
  --out-dir /tmp/agent-harness-run

python scripts/run_agent_harness.py replay \
  --run-dir /tmp/agent-harness-run \
  --episode single-tool-001-r0
```

- fake run 当前产出 JSON report、Markdown report 和逐 episode replay。
- MiniRoute adapter 只读取 `parse_training_record()` 的五字段 `RouteLabel.to_dict()`；非法 JSON 写入 `router_parse_errors`，`router_decision=None`。
- `json_valid` 仍然不属于 MiniRoute 模型输出、`RouteLabel` 或 `router_decision`。

当前尚未完成：

- 旧 runner 仍是 `ADAPTER_REQUIRED`，尚未有 3 条旧评测线真正通过统一协议运行。
- `SandboxRealEnvironment` 和 `IpcLiveEnvironment` 仍待实现。
- 120 unique episode x 3 repeats 的真实 LLM weekly matrix 尚未执行。
- 置信区间、paired delta、真实 provider usage 校验和旧 trace 转换仍待实现。

因此，本阶段可作为 PR smoke 和后续持续优化基座，但不能作为“完整 120 episode 真实 LLM Agent 评测已完成”的证据。

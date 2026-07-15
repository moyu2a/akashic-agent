# TaskPlan 第一阶段设计方案

## 1. 目标

TaskPlan 第一阶段为本地开发工作台 Agent 增加一个可持久化、可查询、可更新的任务计划状态骨架。

它要解决的问题是：复杂开发任务不能只散落在多轮对话、工具调用和 observe trace 中，而应该有一个当前 session 下可追踪的任务计划、步骤状态和进度摘要。

第一阶段只做任务状态骨架，不做完整本地开发自动化。

## 2. 非目标

第一阶段明确不做：

- 不做后台自动任务调度。
- 不做多 agent 分工。
- 不做复杂 DAG 或依赖图。
- 不做权限审批。
- 不做文件修改确认、diff 审核和回滚。
- 不做自动执行整个任务。
- 不改 AgentLoop 主循环。
- 不把 task tools 写入 ToolDiscoveryState / LRU。

## 3. 架构定位

TaskPlan 应作为 core module，而不是普通插件。

原因：

- 它是本地开发工作台 Agent 的任务状态源，后续权限模型、文件修改确认、回滚、开发闭环和 observe trace 都会依赖它。
- 它需要稳定绑定 `session_key`、task id、step id 和后续可选的 turn trace，而普通插件不适合作为系统级状态所有者。
- 它不应该介入 AgentLoop 主循环，只通过现有窄接入点提供 context、tool adapter 和 gateway policy。

推荐结构：

```text
agent/task_plan/
  __init__.py
  models.py
  store.py
  service.py
  context.py

agent/tools/task_plan.py
bootstrap/toolsets/task_plan.py
```

职责：

- `agent/task_plan/models.py`：定义 `TaskPlan`、`TaskStep`、状态枚举和序列化。
- `agent/task_plan/store.py`：负责 SQLite schema、事务和持久化读写。
- `agent/task_plan/service.py`：负责 session ownership、active task 规则、步骤状态规则和业务接口。
- `agent/task_plan/context.py`：负责把 active task 渲染成限长 prompt context。
- `agent/tools/task_plan.py`：deferred tool adapter，只负责参数校验、受保护 `_session_key` 注入和调用 service。
- `bootstrap/toolsets/task_plan.py`：注册 task tools，接入 bootstrap wiring。

## 4. 数据模型

### TaskPlan

```python
@dataclass
class TaskPlan:
    task_id: str
    session_key: str
    title: str
    status: TaskStatus
    steps: list[TaskStep]
    created_at: str
    updated_at: str
    completed_at: str | None = None
    source_turn_id: int | None = None
    terminal_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
```

`TaskStatus`：

```python
TaskStatus = Literal["active", "completed", "cancelled", "failed"]
```

### TaskStep

```python
@dataclass
class TaskStep:
    step_id: str
    task_id: str
    index: int
    title: str
    status: StepStatus
    tool_names: list[str] = field(default_factory=list)
    result_summary: str = ""
    source_turn_id: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

`StepStatus`：

```python
StepStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "failed",
    "skipped",
]
```

说明：

- `source_turn_id` 是 nullable 字段。第一阶段不要求 tool 在当前 turn 内拿到 observe row id。
- 如后续需要精准绑定当前 turn，可通过 after-turn lifecycle 回填。
- `step_id` 使用稳定 UUID。
- tool schema 允许用 `step_id` 或 `step_index` 更新步骤，降低模型操作 opaque id 的负担。

## 5. SQLite 存储

数据库路径：

```text
workspace / "task_plans.db"
```

第一阶段可由 store 懒初始化；后续可补充 `bootstrap/init_workspace.py` 预创建。

Schema：

```sql
CREATE TABLE IF NOT EXISTS task_plans (
    task_id TEXT PRIMARY KEY,
    session_key TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('active', 'completed', 'cancelled', 'failed')
    ),
    source_turn_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    terminal_reason TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_plans_one_active_per_session
ON task_plans(session_key)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS ix_task_plans_session_status_updated
ON task_plans(session_key, status, updated_at);

CREATE TABLE IF NOT EXISTS task_steps (
    step_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')
    ),
    tool_names_json TEXT NOT NULL DEFAULT '[]',
    result_summary TEXT NOT NULL DEFAULT '',
    source_turn_id INTEGER,
    started_at TEXT,
    completed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(task_id) REFERENCES task_plans(task_id) ON DELETE CASCADE,
    UNIQUE(task_id, step_index)
);

CREATE INDEX IF NOT EXISTS ix_task_steps_task_index
ON task_steps(task_id, step_index);
```

一致性要求：

- store 每次连接启用 `PRAGMA foreign_keys=ON`。
- `replace_active=True` 必须在同一事务内取消旧 active task 并创建新 task。
- 同 session 并发 create active task 只能成功一个。
- 推荐 store 内部使用 `threading.RLock` 加 `BEGIN IMMEDIATE`，避免并发写造成 active task 竞态。

## 6. Service 接口

Service 是业务边界，必须做 session ownership 校验。

```python
class TaskPlanService:
    def create_task_plan(
        self,
        *,
        session_key: str,
        title: str,
        steps: list[str],
        source_turn_id: int | None = None,
        replace_active: bool = False,
    ) -> TaskPlan: ...

    def get_active_task_plan(
        self,
        *,
        session_key: str,
    ) -> TaskPlan | None: ...

    def get_task_plan(
        self,
        *,
        session_key: str,
        task_id: str,
    ) -> TaskPlan | None: ...

    def update_step_status(
        self,
        *,
        session_key: str,
        task_id: str,
        step_id: str | None = None,
        step_index: int | None = None,
        status: StepStatus,
        result_summary: str = "",
        tool_names: list[str] | None = None,
        source_turn_id: int | None = None,
    ) -> TaskPlan: ...

    def complete_task_plan(
        self,
        *,
        session_key: str,
        task_id: str,
        terminal_reason: str = "",
    ) -> TaskPlan: ...

    def cancel_task_plan(
        self,
        *,
        session_key: str,
        task_id: str,
        terminal_reason: str = "",
    ) -> TaskPlan: ...
```

规则：

- 每个 `session_key` 第一版最多一个 active task。
- `replace_active=False` 且已有 active task 时，创建应失败并返回结构化错误。
- `replace_active=True` 时，旧 active task 标记为 `cancelled`，新 task 标记为 `active`。
- `update_step_status` 必须确认 task 属于当前 `session_key`。
- `step_id` 和 `step_index` 二选一；都传时优先校验它们指向同一步。
- 所有 step 都是 `completed` 或 `skipped` 时，task 自动标记为 `completed`。
- step `failed` 不自动让 task `failed`，便于用户修复后继续。
- 第一版允许显式覆盖 step 状态，但必须更新 `updated_at` 并保留最近 `result_summary`。

## 7. Tool Adapter

TaskPlan tools 是 deferred tools，不 always-on，不进入 LRU。

建议工具：

- `create_task_plan`
- `update_task_step`
- `inspect_task_plan`

安全要求：

- tool schema 不暴露 `session_key` 或 `_session_key`。
- `_session_key` 只能由 registry context 注入。
- model 传入的 `_session_key` 必须被 registry protected context 覆盖。
- tool adapter 调 service 时必须传入受保护 `_session_key`。

示例参数：

```json
{
  "title": "修复 Document RAG 成本问题",
  "steps": [
    "查看最新运行日志",
    "分析多 fetch 候选原因",
    "更新治理文档"
  ],
  "replace_active": false
}
```

```json
{
  "task_id": "task_...",
  "step_index": 1,
  "status": "completed",
  "result_summary": "已查看 observe turn 371-374",
  "tool_names": ["inspect_turn_trace"]
}
```

## 8. Bootstrap / Toolset Wiring

第一阶段必须补清运行时依赖所有权。

设计：

- `TaskPlanService` 由 bootstrap 创建为单例。
- `TaskPlanToolsetProvider` 创建 task tools，并共享同一个 `TaskPlanService`。
- prompt context handler 也使用同一个 `TaskPlanService`。
- 默认配置中注册 `task_plan` toolset，但工具保持 deferred、非 always-on。

候选文件：

```text
bootstrap/toolsets/task_plan.py
bootstrap/tools.py
bootstrap/wiring.py
agent/config_models.py
```

具体实现时需要按现有 toolset provider 模式接入，不在 AgentLoop 中手动注册工具。

## 9. Prompt Context 接入

不改 AgentLoop 主循环。

推荐在 prompt render lifecycle 里注入 active task 摘要：

- 无 active task：不注入。
- 有 active task：注入限长摘要。
- 不注入完整 steps 历史，完整信息通过 `inspect_task_plan` 查询。

摘要内容：

```text
当前任务计划：
- title: 修复 Document RAG 成本问题
- status: active
- current_step: [in_progress] 分析多 fetch 候选原因
- next_step: [pending] 更新治理文档
- recent_result: 已查看 observe turn 371-374

规则：
- 如果本轮推进了某个步骤，完成后更新对应 step 状态。
- 不要跳过 pending 步骤，除非用户明确要求。
```

限长要求：

- 默认最大 1200 字符。
- step title 和 result summary 需要截断。
- 只展示当前步骤、下一步和最近完成步骤，避免污染 prompt。

## 10. ToolAccessGateway 策略

新增 `TaskPlanAccessPolicy` 或等价逻辑，职责是控制 task tools 的 current-turn 可见性。

任务意图示例：

- “制定计划”
- “任务计划”
- “当前进度”
- “做到哪一步”
- “下一步”
- “继续执行”
- “标记第 N 步完成”
- “更新任务状态”

策略：

- 任务/进度意图：`visible_add` task tools。
- 非任务意图：不暴露 task tools。
- 有 active task 且用户说“继续/下一步/进度”：暴露 `inspect_task_plan` 和 `update_task_step`。
- 创建计划意图：暴露 `create_task_plan`。
- 不压制 Document RAG 或 session/meta tools，除非已有策略本身决定压制。
- 混合问题中，task intent 不应破坏现有 DocRAG / SessionMeta 优先级。

需要测试：

- 任务意图能看到 task tools。
- 普通文档问题不看到 task tools。
- 工具历史查询仍优先 `inspect_turn_trace`，不被 task tools 误导。
- Document RAG 强文档意图仍保留 `search_docs/fetch_doc_chunk` 行为。

## 11. Non-LRU 设计

TaskPlan tools 不应进入 ToolDiscoveryState / LRU。

推荐方案：

- 给工具元数据增加 `non_lru` 标记，例如 `ToolMeta.non_lru: bool = False`。
- tool discovery update 时跳过 `always_on` 和 `non_lru` 工具。
- `inspect_turn_trace` 等已有硬编码 `NON_LRU_TOOL_NAMES` 可逐步迁移到元数据标记。

如果第一版为了降低改动面，也可以先把 task tools 加入 `NON_LRU_TOOL_NAMES`。但正式设计倾向元数据化，避免后续继续堆硬编码。

## 12. Observe / Turn Trace 关系

第一阶段不要求 task tool 在同一 turn 内写入准确 observe turn id。

原因：

- observe turn row 通常在 turn 结束后持久化。
- tool 执行发生在 turn 中间，无法稳定知道当前 observe row id。

第一阶段处理方式：

- `source_turn_id` 保持 nullable。
- tool adapter 可不写 `source_turn_id`。
- 后续如果需要精确关联，可在 after-turn lifecycle 根据 session、task active state、tool call metadata 回填。

TaskPlan 与 observe 的关系：

- observe 是真实工具链和模型调用事实源。
- TaskPlan 是用户任务语义和步骤状态源。
- 两者通过可选 `source_turn_id` 或未来 `turn_ref` 关联，但不互相替代。

## 13. 测试计划

### Store 测试

- schema 创建成功。
- `PRAGMA foreign_keys=ON` 生效。
- status CHECK 生效。
- 同 session 只能有一个 active task。
- 不同 session 可各有一个 active task。
- task 删除时 steps 级联删除。
- step index 按 task 内唯一。

### Service 测试

- 创建 task 成功。
- 已有 active task 时，`replace_active=False` 创建失败。
- `replace_active=True` 在同一事务内取消旧 task 并创建新 task。
- 查询 active task 只返回当前 session 的 active task。
- 跨 session `task_id` 更新失败。
- `step_id` 更新成功。
- `step_index` 更新成功。
- 所有步骤 completed/skipped 后 task 自动 completed。
- step failed 不自动 fail task。
- 重复更新同一状态幂等。
- cancel/complete 写入 `terminal_reason`。

### Tool 测试

- schema 不暴露 `session_key/_session_key`。
- protected `_session_key` 覆盖 model 参数。
- `create_task_plan` 调 service 时使用当前 session。
- `update_task_step` 跨 session task id 失败。
- `inspect_task_plan` 只能查询当前 session task。

### Gateway / LRU 测试

- 任务意图 visible_add task tools。
- 非任务意图不暴露 task tools。
- task tools 不进入 LRU。
- task tools 不破坏 DocRAG tool visibility。
- task tools 不破坏 session/meta trace 查询优先级。

### Context 测试

- 无 active task 不注入 context。
- 有 active task 注入限长摘要。
- 摘要包含 title、status、current step、next step、recent result。
- 长 title/result 会截断。

### CLI Smoke

1. `为修复 Document RAG 成本问题制定一个三步计划`
   - 预期调用 `create_task_plan`。
2. `当前任务做到哪一步了？`
   - 预期调用 `inspect_task_plan`，不调用 RAG、shell。
3. `把第一步标记为完成，说明已经查看日志`
   - 预期调用 `update_task_step`。
4. `继续执行下一步`
   - 预期能基于 active task context 说明下一步。

## 14. 实施顺序

1. 实现 `agent/task_plan/models.py` 和基础状态类型。
2. 实现 `agent/task_plan/store.py`，包含 schema、事务和强约束。
3. 实现 `agent/task_plan/service.py`，包含 session ownership 和 active task 规则。
4. 增加 store/service 单元测试。
5. 实现 `agent/tools/task_plan.py`。
6. 实现 `bootstrap/toolsets/task_plan.py` 并接入 bootstrap wiring。
7. 增加 protected `_session_key` 和 tool schema 测试。
8. 实现 `TaskPlanAccessPolicy`。
9. 实现 task tools non-LRU 机制，优先元数据化。
10. 实现 prompt render context handler。
11. 增加 gateway/LRU/context 测试。
12. 更新 `my_md/local_agent/README.md`、governance 和 progress。
13. 运行 targeted pytest。
14. 执行真实 CLI smoke。

## 15. 当前结论

该计划经审阅后仍然成立，但第一版必须补齐以下工程约束后再实现：

- bootstrap/toolset wiring。
- prompt render lifecycle 注入点。
- TaskPlanAccessPolicy。
- task tools non-LRU 机制。
- SQLite partial unique index、事务和外键。
- service session ownership 校验。
- observe `source_turn_id` nullable 语义。
- context 摘要限长。

修订后的第一阶段仍保持低侵入：不改 AgentLoop 主循环，不做自动后台任务，不做权限模型和文件回滚，只为 Local Agent 后续能力提供稳定任务状态骨架。

## 16. 实现状态（2026-07-14）

TaskPlan 第一阶段代码已按上述边界落地，当前实现保持 core module 定位，不作为普通插件持有状态，也不改 AgentLoop 主循环。

已实现内容：

- `agent/task_plan/models.py`：任务/步骤 dataclass、状态校验、ID 生成和稳定序列化。
- `agent/task_plan/store.py`：SQLite schema、外键、partial unique index、事务写入和 step 查询更新。
- `agent/task_plan/service.py`：唯一业务边界，负责 session ownership、active task 冲突、step 状态更新和自动完成。
- `agent/tools/task_plan.py`：`create_task_plan`、`update_task_step`、`inspect_task_plan` 三个 deferred tool adapter；schema 不暴露 `session_key/_session_key`。
- `bootstrap/toolsets/task_plan.py`：以 toolset 方式注册 task tools，标记为 deferred、non-LRU。
- `agent/task_plan/context.py`：active task compact prompt context，通过 prompt render lifecycle 注入。
- `agent/policies/tool_access.py`：新增 `TaskPlanAccessPolicy`，根据创建/进度/查看任务意图暴露 task tools，并在纯任务规划请求中压制无关 Document RAG。
- `agent/tools/registry.py`、`agent/core/runtime_support.py`、`agent/core/passive_turn.py`：新增工具级 `non_lru` 元数据，task tools 不写入 ToolDiscoveryState / LRU。
- `bootstrap/tools.py`、`bootstrap/wiring.py`、`agent/looping/ports.py`、`agent/looping/core.py`：创建共享 `TaskPlanService`，同时传给 toolset、prompt context 和 reasoner 的 tool-access metadata。

关键设计结果：

- TaskPlanStore 仍是私有低层持久化，工具、网关、prompt module 和 runtime 只依赖 `TaskPlanService`。
- Task tools 不 always-on，不进 LRU，避免跨 turn 污染工具可见性。
- active task 状态只作为当前 turn 的 `ToolAccessContext.turn_metadata["has_active_task"]` 使用，不写入 ToolDiscoveryState。
- prompt context 通过现有 prompt render lifecycle 注入，属于窄接入点，不介入 AgentLoop 主循环。

自动化验证：

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_models.py \
  tests/test_task_plan_store.py \
  tests/test_task_plan_service.py \
  tests/test_task_plan_tools.py \
  tests/test_task_plan_lru.py \
  tests/test_task_plan_toolset.py \
  tests/test_task_plan_gateway.py \
  tests/test_task_plan_context.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_bootstrap_toolsets_p1.py \
  tests/test_bootstrap_wiring_p2.py \
  tests/test_turn_trace_tool.py \
  tests/test_turn_trace_reasoner.py -q
```

结果：`83 passed in 1.67s`。

完整回归：

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

结果：`1452 passed, 3 warnings in 36.22s`。

尚未完成：

- 真实 CLI smoke 尚未在本次实现后执行，需要重启 agent 后按第 13 节的四条命令验证。
- 第一阶段不做权限审批、文件修改确认、diff review、任务自动执行和 observe turn id 回填；这些仍属于后续 Local Agent 阶段。

## 17. 真实运行问题与修复（2026-07-14）

真实 CLI smoke 暴露了一个配置加载层问题：

- 现象：任务计划意图被 `TaskPlanAccessPolicy` 识别，日志显示 `visible_add=create_task_plan/inspect_task_plan`，但工具执行返回 `工具 'create_task_plan' 不存在` 或 `工具 'inspect_task_plan' 不存在`。
- 直接证据：`~/.akashic/workspace/logs/agent.log` 中 11:32:58 的 `create_task_plan` 和 11:35:53 的 `inspect_task_plan` 均返回工具不存在。
- 数据证据：`~/.akashic/workspace/task_plans.db` 中 `task_plans/task_steps` 计数均为 0，说明计划没有真实创建。
- 伴随问题：11:35:53 后 DeepSeek API 返回 `402 Insufficient Balance`，导致 turn 失败和后台 subagent completion 处理失败；这是外部模型账户余额问题，不是 TaskPlan 代码路径本身。

根因：

- `agent.config._load_wiring_config()` 仍维护一份旧的硬编码默认 toolsets：`meta_common/spawn/schedule/mcp/doc_rag`。
- `agent.config_models.WiringConfig` 已新增 `task_plan`，但 `load_config()` 没有复用该默认值，导致真实 `config.toml` 未显式配置 toolsets 时不会注册 task_plan tools。
- 网关缺少“已注册工具集合”过滤，导致 policy 可以把未注册工具名加入 visible set，模型随后尝试调用不存在的工具。

修复：

- `_load_wiring_config()` 改为复用 `WiringConfig()` 默认值，避免默认 toolsets 双源维护。
- `ToolAccessContext` 增加 `registered_tools`。
- `ToolAccessGateway.compute_visible_names()` 和 `merge_tool_search_unlocks()` 对已注册工具集合求交，防止未注册工具被暴露或解锁。
- `DefaultReasoner.run_turn()` 将 `ToolRegistry.get_registered_names()` 注入 `ToolAccessContext`；对测试替身保留空集合 fallback。

验证：

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_toolset.py \
  tests/test_task_plan_gateway.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_bootstrap_toolsets_p1.py \
  tests/test_bootstrap_wiring_p2.py \
  tests/test_doc_rag_toolset.py \
  tests/test_runtime_smoke.py -q
```

结果：`60 passed in 1.33s`。

完整回归：

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

结果：`1454 passed, 3 warnings in 35.83s`。

重新构造 runtime 验证：

- `load_config("config.toml").wiring.toolsets` 包含 `task_plan`。
- `create_task_plan`、`inspect_task_plan`、`update_task_step` 已注册。
- 三个 task tools 均在 `non_lru` 集合中。

后续测试注意：

- 需要重启 agent，让新配置加载逻辑和新 registry 过滤生效。
- 如果仍使用 DeepSeek 当前账户，需要先处理 `402 Insufficient Balance`；否则 CLI smoke 会在 LLM 调用层失败，无法验证 task tool 链路。

## 18. 第二轮 CLI Smoke 结果（2026-07-14）

重启 agent 后再次执行 TaskPlan smoke，核心链路已跑通，但行为边界仍需收紧。

### 已验证通过

日志时间段：2026-07-14 14:31 - 14:33。

执行结果：

- `create_task_plan` 已真实注册并成功执行。
- `update_task_step` 已真实注册并成功执行。
- `task_plans.db` 中已持久化 active task 和 steps。
- 未再出现 `工具 'create_task_plan' 不存在` 或 `工具 'inspect_task_plan' 不存在`。

数据库状态：

```text
task: Document RAG 成本分析与三步修复计划 | active
Step 1: completed
Step 2: in_progress
Step 3: pending
Step 4: pending
Step 5: pending
```

这说明第一阶段的关键技术路径已经成立：

- toolset 注册生效；
- session 绑定正确；
- `TaskPlanService` 写入 SQLite；
- step 状态可跨 turn 更新；
- active task context 能参与后续 turn 的工具可见性判断。

### 不符合预期的行为

第一条 smoke prompt：

```text
为修复 Document RAG 成本问题制定一个三步计划
```

实际结果：

- ReAct 迭代达到 `15`；
- `prompt_tokens=985779`；
- 创建了 task plan，但也额外调用了 `inspect_task_plan`、`spawn_manage`、多次 `tool_search`、`update_task_step` 和 `spawn`；
- 模型把“制定计划”理解成“开始执行/后台分析任务”。

第二条：

```text
当前任务做到哪一步了？
```

实际只调用了 `spawn_manage`，没有调用 `inspect_task_plan`。这说明“当前任务”在模型侧被解释成后台 spawn job，而不是 TaskPlan active task。

第三、第四条：

- `把第一步标记为完成...` 正确调用 `update_task_step`，但额外调用 `spawn_manage`。
- `继续执行下一步` 正确把 Step 2 标记为 `in_progress`，但额外调用 `spawn_manage`、`task_output`、`list_dir`。

### 新问题

当前剩余问题不再是“TaskPlan 工具是否可用”，而是任务语义边界和成本控制：

1. 纯计划创建意图没有被限制为 `create_task_plan -> final`。
2. TaskPlan 场景中 `spawn/spawn_manage/task_output` 干扰过强。
3. “当前任务”语义在 TaskPlan active task 和后台 spawn job 之间混淆。
4. `create_task_plan` 第一轮 smoke 成本过高，15 轮 ReAct 不适合作为常规任务规划路径。
5. 后台 subagent 对项目源码路径没有权限，且尝试使用不存在的 `write_file`，说明它不适合作为当前 TaskPlan smoke 的默认执行路径。

### 后续建议

下一阶段应增加 TaskPlan 场景的边界治理：

- 纯任务规划请求：只暴露或强偏置 `create_task_plan`、`inspect_task_plan`，并压制 `spawn/spawn_manage/task_output`。
- 当前任务/进度查询：优先 `inspect_task_plan`，只有用户明确说“后台任务/job/subagent”时才暴露 spawn 管理工具。
- 继续下一步：优先使用 active task context 和 `update_task_step`，不自动启动后台分析。
- 对 `create_task_plan` 工具描述增加约束：该工具只创建计划，不执行步骤，不启动后台任务。
- 增加真实 smoke 回归指标：计划创建 turn 目标应为 1-3 轮 ReAct，禁止 spawn，禁止无关 Document RAG/local file 工具。

## 19. TaskPlan Boundary Governance 实现（2026-07-14）

本阶段已完成第二轮 CLI smoke 暴露的 TaskPlan 语义边界治理。目标不是增加新的任务执行器，而是让“创建、查看、更新计划状态”和“后台 job”成为两个确定、可测试的工具域。

### 模块边界

- `agent/policies/tool_access_types.py`：承载 `ToolAccessContext`、`ToolAccessPlan`、`ToolExecutionGateResult` 和 `ToolAccessPolicy`，消除网关与具体策略之间的循环依赖。
- `agent/policies/task_plan_boundary.py`：只负责 TaskPlan/background-job 意图分类，以及当前 turn 的工具可见、发现和执行边界。
- `agent/policies/turn_completion_types.py`：承载通用 turn completion 类型，避免 completion controller 和具体 completion policy 互相导入。
- `agent/policies/task_plan_completion.py`：识别成功的 `create_task_plan`、`inspect_task_plan`、`update_task_step` ledger 记录，并请求 final-only。
- `agent/policies/tool_access.py`：继续作为策略组合网关，不包含 TaskPlan 具体意图词表。
- `agent/policies/turn_completion.py`：继续作为 completion controller，先处理 TaskPlan 成功终止，再保留原有 Document RAG completion 行为。

这些模块接入 `DefaultReasoner` 已有的工具边界和 completion 路径，没有修改 `AgentLoop` 主循环，也没有把 TaskPlan 工具改成 always-on 或写入 LRU。

### 行为规则

| 用户意图 | 默认可用工具 | 当前 turn 压制/拦截 | 成功后行为 |
| --- | --- | --- | --- |
| 制定/创建计划 | `create_task_plan`, `inspect_task_plan` | spawn、Document RAG、local file | final-only |
| 查看当前任务/进度 | `inspect_task_plan` | spawn | final-only |
| 更新步骤/标记完成 | `inspect_task_plan`, `update_task_step` | spawn | final-only |
| 明确后台任务/job/spawn/subagent | `spawn_manage`, `task_output` | 不施加 TaskPlan spawn block | 保留后台工具流程 |

歧义规则：

- `当前任务输出` 解释为 TaskPlan inspect。
- 只有明确出现“后台任务、后台输出、job_id、spawn、subagent”等信号时，才进入 background-job 分支。
- 模型绕过 schema 可见性直接调用被压制工具时，执行层返回 `tool_blocked_by_task_plan_policy`，不执行真实工具。

### Prompt 与工具描述

- `create_task_plan` 明确只创建计划，不执行步骤、不读文件、不检索文档、不启动后台任务。
- `inspect_task_plan` 明确 TaskPlan 与 spawn job 的区别。
- active task prompt 明确状态管理完成后停止调用工具，不因存在计划而自动执行步骤。

### 自动化验证

新增或扩展覆盖：

- 中立 access/completion 类型兼容导出；
- TaskPlan 与 Document RAG 混合词的默认网关组合；
- spawn/RAG/local schema 压制、tool search block 和执行拦截；
- `TurnToolBoundaryManager` 直接拦截 spawn；
- create/inspect/update 成功与失败的 completion 判断；
- `DefaultReasoner.run_turn()` 中 create/inspect/update 成功后的 `tools=[]` final-only；
- 明确后台任务时保留 `spawn_manage/task_output`。

分层结果：

- TaskPlan 聚焦套件：`63 passed`。
- Tool boundary / Document RAG / Turn Trace 套件：`66 passed`。
- Bootstrap/config 套件：`33 passed`。
- Reasoner 边界套件：`26 passed`。

完整回归：

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

结果：`1481 passed, 3 warnings in 36.10s`。

`git diff --check` 和相关模块 `compileall` 均通过。

### 第三轮真实 CLI smoke（turn 382-385）

2026-07-14 16:26 重启 Agent 后，使用独立 session：

```bash
AKASHIC_CLI_SESSION=taskplan-boundary-smoke-20260714 \
uv run python main.py cli
```

结果：

| Turn | 输入 | 实际链路 | ReAct | 结论 |
| --- | --- | --- | ---: | --- |
| 382 | 制定三步计划，只创建、不执行 | `recall_memory -> search_messages(soft-stop) -> create_task_plan -> final` | 4 | 主边界通过，召回成本未完全收敛 |
| 383 | 当前任务做到哪一步 | `inspect_task_plan -> final` | 2 | 通过 |
| 384 | 标记第一步完成 | `update_task_step -> final` | 2 | 通过 |
| 385 | 查看后台任务状态 | `spawn_manage -> final` | 2 | 通过 |

turn `382` 的 access plan：

- `reason=task_plan_create_intent`。
- 压制并拦截：`spawn/spawn_manage/task_output`、`search_docs/fetch_doc_chunk`、`shell/read_file/list_dir`。
- 成功执行 `create_task_plan` 后触发 `[turn_completion] final_only reason=task_plan_tool_complete`。
- 没有后台 subagent、RAG 或本地文件真实执行。

数据库结果：

- active task：`task_87eb3d1b8d944efd9bf566a8ae7e7b30`。
- 计划恰好 3 个步骤。
- Step 1 为 `completed`，`result_summary=已经查看日志`。
- Step 2、Step 3 为 `pending`。

成本对比：

- 旧计划创建 turn：15 轮，累计 `prompt_tokens=985779`。
- turn `382`：4 轮，累计 `prompt_tokens=52205`。
- ReAct 下降约 73%，累计 prompt token 下降约 94.7%。

### 新遗留问题：计划创建的上下文召回授权

turn `382` 仍真实执行一次 `recall_memory`，并生成一次被 `retrieval_budget_exceeded` soft-stop 的 `search_messages`。这两步没有破坏 TaskPlan 状态，但使纯计划创建未达到严格的 `create_task_plan -> final`。

问题不应处理成“TaskPlan 永远禁止 memory”：

- 用户已经提供明确目标和约束时，不需要额外召回。
- 用户明确说“结合我的偏好/记忆”时，允许一次长期记忆召回是合理的。
- 用户明确说“按照上次/之前讨论”时，允许一次当前 session 历史检索是合理的。

推荐下一阶段将 `TaskPlanIntent` 扩展为：

```text
action: create | inspect | update | background_job
context_requirement: none | long_term_memory | session_history
```

再由 Tool Access Gateway 把 capability scope 映射到具体工具，并对召回设置一次性预算。该方向登记为 `LA-001`，已于 2026-07-14 完成自动化实现。

完整实施计划：`docs/superpowers/plans/2026-07-14-task-plan-context-capability-scope.md`。计划补充了统一 `TaskPlanTurnContract`、工具 capability 元数据、受保护 current-session history、一次性召回预算、action-aware completion 和真实 CLI 验收矩阵。

附带可观测性问题：日志同时出现 `[react_boundary] final_only reason=...` 和正确的 TaskPlan completion reason；前者打印的是 react recommendation reason，不是最终 completion 原因，后续应修正日志来源。

## LA-001 实施结果：上下文需求与 capability scope

本阶段没有把 TaskPlan 变成固定 workflow，也没有全局关闭 memory。实现由四层窄边界组合：

1. `TaskPlanTurnContract`：识别 create/inspect/update，并只在用户明确引用偏好或上次讨论时声明 context requirement。
2. `TaskPlanAccessPolicy`：从 registry capability 元数据解析 provider，构造严格 current-turn allow scope。
3. `TaskPlanContextBudgetPolicy`：允许最多一次对应 context retrieval，授权后的失败/拒绝/错误同样计入预算。
4. `TaskPlanCompletionPolicy`：只在当前 action 的 completion capability 成功后进入 final-only。

关键行为：

| 请求 | 首轮允许工具 | 预算/转移 | 完成条件 |
| --- | --- | --- | --- |
| 纯计划创建 | `create_task_plan` | 无召回 | `task_plan.create` 成功 |
| 结合偏好创建 | `recall_memory`, `create_task_plan` | recall 最多一次，随后 recall schema 退场 | create 成功 |
| 按上次讨论创建 | `search_messages`, `create_task_plan` | search 最多一次，不开放 `fetch_messages` | create 成功 |
| 查看任务 | `inspect_task_plan` | 无召回 | inspect 成功 |
| 更新任务 | `inspect_task_plan`, `update_task_step` | inspect 不会提前结束 | update 成功 |
| 明确后台 job | 现有 spawn 工具 | 非严格 passthrough | 不激活 TaskPlan completion |

工程约束保持不变：

- 不修改 AgentLoop 主循环。
- 不修改 always-on 策略。
- 不把 intent、contract、budget 或 capability scope 写入 LRU/ToolDiscoveryState。
- discovery 关闭时，普通 turn 保持全工具旧行为；严格 TaskPlan turn 仍执行边界。
- registry capability 不暴露到模型 schema、tool search 文档或参数。
- protected `_session_key` 优先于模型参数，history retrieval 默认当前 session。

自动化结果：TaskPlan/网关聚焦 `192 passed`，兼容回归 `85 passed`，最终完整 pytest `1619 passed, 3 warnings in 38.10s`。Task 4/5/6 和 live-smoke precedence 修复均经过独立审阅并修复全部 Critical/Important findings。

### LA-001 隔离真实 smoke

2026-07-14 使用独立 socket `/tmp/akashic-la001.sock`、临时 workspace 和 dashboard `2237` 启动当前代码，不影响用户现有 Agent/CLI：

| 场景 | 真实链路 | ReAct | 累计 prompt tokens | 结果 |
| --- | --- | ---: | ---: | --- |
| 纯计划 | `create_task_plan -> final` | 2 | 11605 | 通过，首轮仅 create schema |
| 显式偏好 | `recall_memory -> create_task_plan -> final` | 3 | 19216 | 通过，一次真实 recall |
| 显式历史 | `search_messages -> create_task_plan -> final` | 3 | 23538 | 通过，一次真实 search；两个同批重复候选被 soft-stop |
| inspect | `inspect_task_plan -> final` | 2 | 14143 | 通过 |
| update | `update_task_step -> final` | 2 | 16604 | 通过 |
| 后台状态 | `spawn_manage -> final` | 2 | 31470 | 通过，非严格 passthrough |

history 同批重复只增加模型已生成的候选协议成本，不增加真实工具执行次数。它与 Document RAG 同批候选问题属于同类模型生成成本，当前边界按设计保证副作用和执行预算。

smoke 还发现“先只记住讨论，不创建计划”因子串命中而误激活 create contract。新增 bounded required/negated action parser 后，真实复测显示 `reason=no_tool_access_policy`，执行 `recall_memory/memorize` 而没有 `create_task_plan`；“不要创建计划，把第一步标记完成”仍能进入 update。后续独立审阅进一步覆盖“请勿/不要再/不得不/不能不”以及 background start/observe 的正向、否定和双重否定优先级，最终无剩余 Critical/Important。

### 2026-07-15 主服务复测

用户重启 `/tmp/akashic.sock` 主服务后，在 session `taskplan-scope-test-20260715` 执行基础四条 smoke。Agent PID `372968` 从当前仓库启动，IPC socket 和 dashboard `2236` 正常监听，测试期间没有 Traceback、observe error 或 CLI 断连。

| Turn | 场景 | 真实链路 | ReAct | Observe 结果 |
| ---: | --- | --- | ---: | --- |
| 389 | 纯计划创建 | `create_task_plan -> final` | 2 | `error=NULL`，首轮只暴露 create provider |
| 390 | 查看当前任务 | `inspect_task_plan -> final` | 2 | `error=NULL` |
| 391 | 更新第一步 | `update_task_step -> final` | 2 | `error=NULL` |
| 392 | 查看后台状态 | `spawn_manage -> final` | 2 | `error=NULL`，保持 background passthrough |

主服务证据进一步确认：

- 纯计划没有执行 `recall_memory`、`search_messages`、Document RAG、本地文件或 spawn 工具。
- create/inspect/update 均以 `task_plan_completion_capability_satisfied` 进入 final-only。
- 四个 turn 的 `LRU preloaded=[]`，TaskPlan contract 和状态没有污染工具发现 LRU。
- SQLite 任务 `task_feebe25a9a8c452cacf652af0c7bd29a` 包含三个步骤；Step 1 为 `completed`，`result_summary=已查看日志，诊断成本来源完成`，Step 2/3 为 `pending`。
- 今天的主服务复测覆盖基础 4/4；偏好、历史和否定意图没有在这组 turn 中重跑，但 2026-07-14 隔离真实 smoke 已覆盖三者，自动化回归继续覆盖失败、拒绝、同批重复和双重否定。

### 阶段结论与下一阶段边界

TaskPlan 第一阶段和 `LA-001` 已完成，当前没有已知阻塞性功能问题。已实现的是任务状态、上下文 capability 授权和工具边界，不是自主任务执行器。

下一阶段已登记为 `LA-002 TaskPlan Recovery and Execution Orchestration`，范围应保持为：

- 重启后恢复 active task，并识别 stale `in_progress` 步骤。
- 每次推进建立独立 execution attempt，保证重复请求和重连不会重复执行同一步。
- “继续执行下一步”默认只推进一个步骤，结果写回 TaskPlan store。
- 复用现有 Tool Access Gateway、Turn Tool Boundary 和 Turn Completion，不在 AgentLoop 主循环新增任务状态机。
- 在权限模型和文件回滚完成前，涉及 shell、文件写入等副作用只能进入待授权状态，不能由编排器直接放行。

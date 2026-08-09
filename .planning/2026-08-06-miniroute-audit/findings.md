# 审阅发现

## 被动消息链路

- `CoreRunner` 将普通入站消息交给 `AgentCore -> PassiveTurnPipeline`。
- `BeforeTurn` 先获取 session，再调用 `ContextStore.prepare()`。
- `DefaultContextStore.prepare()` 每轮都会调用 `MemoryRetrievalPipeline.retrieve()`，没有读取 MiniRoute 的 `need_memory` 开关。
- `DefaultMemoryRetrievalPipeline` 将请求直接交给 `MemoryEngine.retrieve()`；当前默认检索器已经包含语义、关键词、来源/图谱 lane、场景路由和检索 trace。
- `BeforeReasoning` 只同步工具上下文并预热 prompt，没有根据 `need_tools` 关闭工具。
- `DefaultReasoner.run_turn()` 根据用户原文、当前 session、任务状态和注册表构建 `ToolAccessContext`，然后由 `ToolAccessGateway`、`TaskPlanAccessPolicy`、`TaskExecutionAccessPolicy` 和 `TurnToolBoundaryManager` 决定工具可见性与执行边界。
- 结论：MiniRoute 的 `need_memory`、`need_tools` 当前不是系统已有的真实控制点；如果直接用它们关闭记忆或工具，会把小模型分类错误转化为功能漏用。

## 工具系统

- `ToolRegistry` 保存具体工具、风险、能力元数据、来源和搜索文档，并提供注册表中的真实工具集合。
- 工具系统内部使用具体 capability，例如 `memory.recall`、`task_plan.create`、`shell.execute`，不是 MiniRoute 的固定 `memory_tools`、`task_tools`、`shell_tools`。
- `ToolAccessGateway` 先根据用户原文和任务控制合同构建 `ToolAccessPlan`，可以增加、隐藏、阻止搜索、阻止执行，并限制严格能力范围。
- 文档问答、会话元信息、任务计划、后台任务和任务执行均有独立规则；工具调用后还会根据结果更新访问计划。
- `TurnToolBoundaryManager` 额外处理工具预算、重复调用、证据是否充分、批量调用跳过、任务执行预算和风险延迟。
- `DefaultToolRiskStrategy` 对 shell、高风险、写入、外部副作用和未知风险分别执行拒绝、审批或允许；高风险不是依赖一个模型字段裁决。
- 结论：MiniRoute 的 `tool_scope` 和 `risk_level` 只能作为建议、搜索范围提示或 shadow 观测，不能作为授权和审批结果。

## 任务和主动触达

- 任务计划由 `infer_task_plan_turn_decision()`、`TaskPlanTurnContract` 和 `TaskPlanAccessPolicy` 形成严格合同；它区分创建、查看、更新、上下文需求和后台任务透传。
- `TaskControlIntentArbiter` 在任务计划合同和任务执行合同冲突时选择唯一严格控制范围，并在冲突时禁止工具 fallback。
- 主动触达不是普通被动消息的 intent 分类：`ProactiveLoop -> AgentTick` 先经过目标、忙碌、冷却、AnyAction、配额等确定性 gate，再由主模型判断 alert/content/context，最后由 `Judge` 进行确定性维度和 LLM 维度评分。
- 没有内容推送时，`DriftRunner` 执行独立的后台自治链路，使用自己的 skill、工具和步骤边界。
- 结论：MiniRoute 当前 intent 集合无法覆盖主动触达的真实决策，也不应插入主动触达链路替代 `Judge` 或 `DriftRunner`。

## MiniRoute 与真实需求的错位

- 当前五字段是 `intent + need_memory + need_tools + tool_scope + risk_level`，但系统真实消费的是：检索场景/策略、任务控制合同、具体 capability、工具可见性、调用预算、证据完成度、审批状态和是否允许副作用。
- 单一 `intent` 无法表达复合请求；当前项目已经额外引入 `operation`、`request_mode`，说明五字段本身不足以描述请求。
- `intent` 标签是业务分类，不是执行决策。`file_read`、`tool_execution`、`content_save` 等类别在真实系统中最终仍要落到具体工具 capability 和风险策略。
- `need_memory` 语义混合了长期记忆、会话历史和上下文检索；真实系统已经分别处理长期记忆、session history、任务计划上下文和主动触达兴趣记忆。
- `risk_level` 仅有 `none/read_only/write/high_risk`，与注册表风险 `read-only/write/external-side-effect/destructive/unknown` 不是同一套枚举。

## 当前实验信号

- `lora_route_v3_2` 在 test 上完全匹配率为 `78.67%`，但单字段 `intent` 为 `78.95%`；`intent` 错误占 test 总样本约 `19.67%`。
- V3 test 错误仍集中在 `tool_execution/file_read`、`task_plan/chat/profile_update`、`profile_update/memory_query/content_save` 和 `unknown_tools/file_read/content_save`。
- 这说明当前模型可以作为有一定价值的粗分类器，但还不能成为 Agent 的前置硬路由器，更不能成为工具安全控制器。

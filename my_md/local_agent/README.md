# Local Agent Docs

这个目录记录 `akashic-agent` 从本地智能 Agent 系统，向“本地个人数字员工 / 本地开发工作台 Agent”演进的产品和架构路线。

## 文档边界

- `rag/`：记录 Document RAG、GraphRAG、LLM Wiki、LoRA/RAG 等专项设计、实验、评估和实现计划。
- `governance/`：记录问题治理、修复路线、设计决策和 STAR 复盘。
- `local_agent/`：记录面向本地个人数字员工的长期产品定位、架构路线、能力缺口和面试表达。

这里的路线文档不是当前 bug 修复清单，也不表示所有能力已经实现。每篇文档都应区分“当前已具备能力”和“后续待建设能力”。

## 文档列表

- [01-local-dev-workbench-agent-roadmap.md](./01-local-dev-workbench-agent-roadmap.md): 本地开发工作台 Agent 演进路线，记录当前底座能力、能力缺口、建设优先级、与现有模块的关系和简历表达方式。
- [02-task-plan-first-phase-design.md](./02-task-plan-first-phase-design.md): TaskPlan 第一阶段设计和实现状态，记录任务计划状态骨架、core module 边界、tool adapter、gateway、non-LRU、SQLite 约束、runtime wiring 和验收测试。

## 当前实现状态

- TaskPlan 第一阶段、边界治理和 LA-001 上下文 capability scope 已完成代码实现、独立审阅和隔离真实 smoke；最新完整回归为 `1619 passed, 3 warnings in 38.10s`。
- 当前能力包括：每个 session 一个 active task、任务步骤持久化、deferred task tools、active task prompt context、TaskPlanAccessPolicy、task tools non-LRU。
- 第三轮真实 CLI smoke turn `382-385` 已验证：计划创建不再调用 spawn/RAG/local，查看和更新分别收敛为 `inspect_task_plan -> final`、`update_task_step -> final`，明确后台任务为 `spawn_manage -> final`。
- 计划创建从 15 轮降到 4 轮，累计 prompt token 从 `985779` 降到 `52205`；TaskPlan completion final-only 已在真实运行中生效。
- `LA-001` 已完成：纯计划真实链路为 `create_task_plan -> final`，显式偏好/历史分别只临时授权一次真实 `recall_memory`/`search_messages`，inspect/update/background 行为保持不变。

## 后续可扩展文档

- `02-local-agent-permission-model.md`：本地操作权限模型设计。
- `03-local-agent-task-planner.md`：任务规划器后续增强设计，例如多任务视图、任务恢复和更复杂的步骤编排。
- `04-local-agent-file-change-review.md`：文件修改确认、diff 展示和回滚机制。
- `05-local-agent-dev-workflow.md`：本地开发任务闭环，包括读日志、查源码、改代码、跑测试和总结。

## 更新规则

- 讨论本地开发工作台 Agent 的产品定位、长期架构和能力路线时，优先更新本目录。
- 如果内容是 Document RAG 的专项实现或评估，仍然放在 `../rag/`。
- 如果内容是具体问题、修复路线或复盘案例，仍然同步到 `../governance/`。

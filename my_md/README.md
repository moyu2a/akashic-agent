# Akashic Agent Learning Notes

这个目录用于记录学习 `akashic-agent` 的过程。后续每次学习、调试、跑通功能、阅读源码或准备面试，都优先把结论沉淀到这里。

## 目录结构

- [learning/](./learning/): 学习路线、运行手册、模块学习顺序。
- [architecture/](./architecture/): 项目架构、被动链路、记忆/工具/插件、主动链路。
- [interview/](./interview/): 求职表达、模块设计模拟面试问答。
- [rag/](./rag/): Document RAG、GraphRAG、LLM Wiki、LoRA/RAG 延伸计划。
- [local_agent/](./local_agent/): 本地个人数字员工 / 本地开发工作台 Agent 的产品和架构演进路线。
- [test_docs/](./test_docs/): 项目分链路测试方案、自动评估集、测试记录和回归清单。
- [governance/](./governance/): 统一管理问题、演进、修复路线、设计决策和 STAR 复盘。

## 常用文档

- [learning/00-learning-map.md](./learning/00-learning-map.md): 学习路线总览、进度和问题池。
- [learning/01-runbook.md](./learning/01-runbook.md): 运行、配置、启动、排错记录。
- [architecture/02-architecture.md](./architecture/02-architecture.md): 系统架构理解。
- [architecture/03-passive-agent-loop.md](./architecture/03-passive-agent-loop.md): 被动对话主链路。
- [architecture/04-memory-tools-plugins.md](./architecture/04-memory-tools-plugins.md): 记忆、工具、插件扩展机制。
- [architecture/05-proactive-agent.md](./architecture/05-proactive-agent.md): 主动推送机制。
- [interview/06-interview-notes.md](./interview/06-interview-notes.md): 求职和面试表达稿。
- [interview/07-module-interview-qa.md](./interview/07-module-interview-qa.md): 模块设计模拟面试问答记录。
- [learning/08-ordered-learning-outline.md](./learning/08-ordered-learning-outline.md): 重新排序后的模块学习大纲。
- [rag/09-document-rag-extension-plan.md](./rag/09-document-rag-extension-plan.md): Document RAG、GraphRAG、LLM Wiki、LoRA 等后续延伸计划。
- [rag/10-document-rag-design.md](./rag/10-document-rag-design.md): Document RAG 设计边界、数据结构、工具接口和接入方式。
- [rag/11-document-rag-implementation-plan.md](./rag/11-document-rag-implementation-plan.md): Document RAG 两周实施计划和任务状态。
- [rag/12-document-rag-params-experiments.md](./rag/12-document-rag-params-experiments.md): Document RAG 参数实验记录。
- [rag/13-document-rag-evaluation.md](./rag/13-document-rag-evaluation.md): Document RAG 评估集、指标和结果记录。
- [rag/14-document-rag-interview-notes.md](./rag/14-document-rag-interview-notes.md): Document RAG / GraphRAG / LLM Wiki 相关面试表达。
- [rag/16-document-rag-p4-p6-implementation-plan.md](./rag/16-document-rag-p4-p6-implementation-plan.md): Document RAG 后端索引/检索/trace 实现计划和手动测试记录。
- [rag/17-document-rag-p7-tools-plan.md](./rag/17-document-rag-p7-tools-plan.md): Document RAG 工具接入计划。
- [rag/18-document-rag-p9-citation-plan.md](./rag/18-document-rag-p9-citation-plan.md): Document RAG 回答引用规则实现计划。
- [rag/19-document-rag-p10-intent-preload-plan.md](./rag/19-document-rag-p10-intent-preload-plan.md): Document RAG 强文档意图 turn-local 工具预加载计划。
- [local_agent/01-local-dev-workbench-agent-roadmap.md](./local_agent/01-local-dev-workbench-agent-roadmap.md): 本地开发工作台 Agent 演进路线，记录当前底座能力、能力缺口、建设优先级和面试表达。
- [local_agent/02-task-plan-first-phase-design.md](./local_agent/02-task-plan-first-phase-design.md): TaskPlan 第一阶段、工具边界、completion 和真实 CLI smoke 记录。
- [local_agent/03-task-plan-recovery-execution-design.md](./local_agent/03-task-plan-recovery-execution-design.md): LA-002 可恢复、幂等、受控的单步骤执行编排设计。
- [governance/01-issue-index.md](./governance/01-issue-index.md): 全局问题总表。
- [governance/02-current-issues.md](./governance/02-current-issues.md): 当前待解决问题。
- [governance/03-domain-evolution.md](./governance/03-domain-evolution.md): 领域演进记录。
- [governance/04-fix-roadmap.md](./governance/04-fix-roadmap.md): 修复路线。
- [governance/05-design-decisions.md](./governance/05-design-decisions.md): 设计决策。
- [governance/06-star-log.md](./governance/06-star-log.md): STAR 复盘案例库。

## 后续更新提示词

可以直接对 Codex 说：

```text
请根据我们刚刚学习/修改/调试的内容，更新 my_md 下相关学习文档。要求保留已有结构，补充新的理解、源码引用、问题和下一步计划。
```

如果只想更新某一个文档：

```text
请只更新 my_md/<对应文件夹>/<文件名>.md，把这次学习到的内容整理进去，补充源码路径和我需要复习的问题。
```

如果想做阶段性复盘：

```text
请阅读 my_md 下相关文档，帮我整理当前学习进度、已掌握模块、薄弱点和下一阶段学习计划，并同步更新 my_md/learning/00-learning-map.md。
```

如果想记录错误、失败测试或演进方向：

```text
请按 my_md/governance 的映射规则更新文档：原始事实留在对应业务目录；需要治理的问题同步到 my_md/governance/01-issue-index.md 或 02-current-issues.md；领域演进写入 03-domain-evolution.md；修复计划写入 04-fix-roadmap.md；设计取舍写入 05-design-decisions.md；完整 STAR 案例写入 06-star-log.md。
```

如果想记录一个完整的问题复盘案例：

```text
请更新 my_md/governance/06-star-log.md，把这个问题按“发现方式、问题现象、证据、影响范围、原因分析、处理方案、处理结果、验证方式、遗留问题、STAR 复盘、面试表达”整理成一个案例。
```

如果想记录某个代码完善方向的演进过程：

```text
请根据当前讨论/修改/测试结果，更新 my_md/governance/03-domain-evolution.md，在 Architecture/Test/RAG/System 对应分节记录“场景、发现、处理、结果、证据、影响、下一步、关联文档”。
```

如果想把其他文档里的问题映射到全局 STAR 复盘文档：

```text
请按 my_md/governance 的问题映射规则处理：先识别原始事实来源，保留在对应业务目录；再判断是否进入 my_md/governance/01-issue-index.md、02-current-issues.md 或 03-domain-evolution.md；如果该问题具备明确现象、原因分析、处理方案或处理结果，并且适合沉淀为 STAR 案例，请同步更新 my_md/governance/06-star-log.md。
```

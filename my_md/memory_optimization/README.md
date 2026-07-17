# Memory Optimization Docs

这个目录记录 `akashic-agent` 记忆系统的优化路线、指标体系和治理设计。

## 文档边界

- `architecture/04-memory-tools-plugins.md`：记录当前记忆、工具、插件的架构理解。
- `interview/08-architecture-diagram.md`：记录适合面试表达的系统链路和模块讲解。
- `memory_optimization/`：记录记忆系统后续怎么优化、怎么测、怎么治理。
- `governance/`：如果某个优化方向形成全局问题、设计取舍或复盘案例，再同步进入治理目录。

本目录不是当前实现状态说明。每篇文档都要明确区分：

- 当前已经具备的能力。
- 可以直接用现有数据测出来的指标。
- 需要新增埋点或评测集才能验证的能力。
- 后续设计方向，不代表已经实现。

## 文档列表

- [01-memory-optimization-roadmap.md](./01-memory-optimization-roadmap.md): 记忆系统优化总路线，整理当前能力、图片启发、优先级和阶段计划。
- [02-memory-quality-metrics.md](./02-memory-quality-metrics.md): 记忆质量指标清单，区分现有可测、加埋点可测、需要评测集才能测的指标。
- [03-memory-governance-design.md](./03-memory-governance-design.md): 记忆治理设计草案，覆盖写入门控、质量评分、冲突检测、检索重排和生命周期管理。
- [04-memory-plugin-experiment-roadmap.md](./04-memory-plugin-experiment-roadmap.md): memory 插件实验扩展路线，记录版本链、信息价值评分、三路召回、睡眠巩固、层级溯源，以及每项能力的开关和对比数据。

## 当前优化主题

参考图片中的“Agent 长时记忆中间件”，本项目可以吸收的核心不是具体技术栈或百分比指标，而是记忆治理思路：

- 写入前判断这条信息值不值得记。
- 写入后给记忆打质量分。
- 检索后不只按向量相似度排序，还要结合 scope、source_ref、时间、类型和置信度重排。
- 长期运行后要做去重、冲突检测、过期降权和压缩。
- 用 observe、Dashboard 和评测集验证优化是否真的有效。

## 当前执行位置

当前 memory 实验路线不是单点功能，而是一组按阶段推进的插件化实验能力。

已经完成：

- Phase 0：`memory_experiments` 实验配置、shadow trace 和运行态 smoke。
- Phase 1a：显式 `memorize` 的写入价值 shadow 评分结构化输出。
- Phase 1b：候选记忆和已有 active 记忆的只读对比，输出信息熵、新颖度、重复风险和写入减少率。
- Phase 2a：三路召回 + RRF 融合 shadow，记录语义、关键词、溯源三路候选和实验融合结果，不改变真实召回和 prompt 注入。
- Phase 2b：NetworkX 实体图谱 graph shadow，记录 graph lane、graph-augmented RRF 融合结果和图谱路径指标，不改变真实召回和 prompt 注入。
- Phase 3a：召回质量重排 shadow，记录 rerank 后的候选顺序、分数拆解和名次变化，不改变真实召回和 prompt 注入。
- Phase 3b：注入治理 shadow，记录 baseline 与 experimental 的注入差异、丢弃原因和 prompt 预算变化，不改变真实召回和 prompt 注入。
- Phase 4a：因果一致性版本链 shadow，基于 `memory_items.status`、`memory_replacements` 和本轮 baseline recalled items 构建 replacement-only 版本链，记录旧版本误召回、当前叶子、冲突链和回滚候选，不改变真实召回和 prompt 注入。
- Phase 4b：层级化溯源 shadow，解析现有 `source_ref` 和 scope 字段，记录来源覆盖、解析成功率、孤儿记忆、扫描级跨 scope 数量和本轮召回级跨 scope 风险；第一版不执行真实 `fetch_messages` 回源。

后续还有 2 个主要子阶段：

1. Phase 5：离线异步睡眠巩固。
2. Phase 6：评测集、Dashboard 和 active 化决策。

trace 汇总报告是这些阶段的数据出口，不应替代上述实验方向。

Phase 1b 的验证结论：

- focused suite：`30 passed`。
- live smoke：`3 passed`。
- `compileall`：通过。
- `git diff --check`：通过。
- live smoke 在 Python 3.14 环境下出现过 asyncio transport 析构 warning，但测试结果为通过，当前未作为 Phase 1b 功能失败处理。

Phase 2a 的验证结论：

- focused suite：`46 passed`。
- broader memory experiment suite：`51 passed`。
- `compileall`：通过。
- `git diff --check`：通过。

Phase 2b 的验证结论：

- focused suite：`56 passed`。
- broader memory experiment suite：`77 passed`。
- `compileall`：通过。
- `git diff --check`：通过。

Phase 3a/3b 的验证结论：

- focused rerank / injection tests：通过。
- engine contract 回归：通过。
- full pytest：`1915 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。

Phase 4a/4b 的验证结论：

- focused Phase 4 suite：`45 passed`。
- 版本链纯函数、溯源纯函数、实验 trace writer 和 engine contract 回归均通过。
- 仍然是 shadow-only，不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。
- broader memory suite：`136 passed, 3 skipped, 1 warning`。
- full pytest：`1915 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。

## 实验扩展原则

图片中的高级能力进入本项目时，应先作为 memory 插件实验能力，而不是直接写成已实现能力。每项实验都需要：

- 配置开关。
- baseline 和 experimental 对照。
- shadow / dry-run 模式。
- observe、Dashboard 或 eval report 输出测试数据。
- 数据验证后再切到 active。

## 后续更新提示词

```text
请根据本次记忆系统优化讨论/设计/实验结果，更新 my_md/memory_optimization 下相关文档；如果形成架构演进或设计取舍，请同步更新 my_md/governance/03-domain-evolution.md 或 05-design-decisions.md。
```

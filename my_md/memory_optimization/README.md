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

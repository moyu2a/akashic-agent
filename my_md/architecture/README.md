# Architecture Docs

这个目录记录 `akashic-agent` 的架构和核心模块设计理解。

## 文档列表

- [02-architecture.md](./02-architecture.md): 系统架构理解。
- [03-passive-agent-loop.md](./03-passive-agent-loop.md): 被动对话主链路。
- [04-memory-tools-plugins.md](./04-memory-tools-plugins.md): 记忆、工具、插件扩展机制。
- [05-proactive-agent.md](./05-proactive-agent.md): 主动推送机制。

## 使用规则

- 学习或解释模块设计时，更新对应专题文档。
- 发现代码设计问题、模块边界问题、优化方向时，统一更新 `../governance/03-domain-evolution.md` 的 Architecture 分节。
- 如果问题形成完整闭环，再同步沉淀到 `../governance/06-star-log.md`。

## 后续更新提示词

```text
请根据本次架构讨论/源码阅读/代码修改，更新 my_md/architecture 下相关文档；如果涉及代码设计演进，请同步更新 my_md/governance/03-domain-evolution.md 的 Architecture 分节。
```

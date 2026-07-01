# Akashic Agent Learning Notes

这个目录用于记录学习 `akashic-agent` 的过程。后续每次学习、调试、跑通功能、阅读源码或准备面试，都优先把结论沉淀到这里。

## 文档列表

- [00-learning-map.md](./00-learning-map.md): 学习路线总览、进度和问题池。
- [01-runbook.md](./01-runbook.md): 运行、配置、启动、排错记录。
- [02-architecture.md](./02-architecture.md): 系统架构理解。
- [03-passive-agent-loop.md](./03-passive-agent-loop.md): 被动对话主链路。
- [04-memory-tools-plugins.md](./04-memory-tools-plugins.md): 记忆、工具、插件扩展机制。
- [05-proactive-agent.md](./05-proactive-agent.md): 主动推送机制。
- [06-interview-notes.md](./06-interview-notes.md): 求职和面试表达稿。
- [07-module-interview-qa.md](./07-module-interview-qa.md): 模块设计模拟面试问答记录。

## 后续更新提示词

可以直接对 Codex 说：

```text
请根据我们刚刚学习/修改/调试的内容，更新 my_md 下相关学习文档。要求保留已有结构，补充新的理解、源码引用、问题和下一步计划。
```

如果只想更新某一个文档：

```text
请只更新 my_md/<文件名>.md，把这次学习到的内容整理进去，补充源码路径和我需要复习的问题。
```

如果想做阶段性复盘：

```text
请阅读 my_md 下所有学习文档，帮我整理当前学习进度、已掌握模块、薄弱点和下一阶段学习计划，并同步更新 00-learning-map.md。
```

# 04 Memory Tools Plugins

## 目标

记录项目中三个核心扩展机制：

- Memory system
- Tool system
- Plugin system

这三块是求职面试中最容易展开讲的部分。

## Memory System

关键文件：

- `bootstrap/memory.py`
- `core/memory/runtime.py`
- `core/memory/markdown.py`
- `core/memory/plugin.py`
- `plugins/default_memory/*`
- `memory2/*`

当前理解：

- markdown memory 是基础层，任何配置下都会构建。
- memory engine 是可插拔语义记忆层。
- `[memory] enabled = true` 后会启用 memory plugin，并注册记忆相关工具。
- `MemoryRuntime` 是统一门面，对外暴露 markdown 读取和语义检索 API。

重要概念：

- `MEMORY.md`: 长期稳定记忆。
- `SELF.md`: agent 自身信息或用户画像相关内容。
- `RECENT_CONTEXT.md`: 近期上下文摘要。
- `HISTORY.md`: 时间线事件。
- `PENDING.md`: 待归档缓冲，减少频繁修改长期记忆带来的 prompt cache 破坏。

### 设计层总结

记忆系统解决的问题是：

```text
如何让 agent 在多次对话之间保留用户信息、历史事件、偏好、待办和长期上下文？
```

普通聊天机器人只有上下文窗口，会遇到：

- 上下文窗口有限。
- 长期偏好会丢。
- 历史事件会丢。
- 用户画像无法稳定沉淀。
- 最近几轮消息不足以支撑长期陪伴或持续任务。

因此记忆系统天然有两条链路：

```text
retrieval path   对话前读取/检索/注入记忆
write path       对话后提取/整理/写入记忆
```

总体流程：

```text
用户对话
   |
   v
Session history
   |
   +--> 当前轮检索相关记忆
   |        |
   |        v
   |   注入 Prompt
   |
   +--> 对话后 consolidation
            |
            v
       PENDING.md / HISTORY.md / memory2.db
            |
            v
       Memory Optimizer
            |
            v
       MEMORY.md / RECENT_CONTEXT.md
```

### Session history 不是长期记忆

Session history 适合保存：

- 最近几轮对话。
- 当前上下文。
- 刚刚发生的任务过程。

但它不适合长期记忆：

- 太长，容易超上下文。
- 信息未结构化。
- 重要事实容易淹没在聊天记录中。
- 跨 session 复用困难。

因此长期记忆需要被整理、压缩、结构化和检索。

### Markdown Memory

项目用 markdown 作为长期记忆基础层。

它解决的问题是：

```text
长期记忆需要可读、可控、可人工编辑。
```

典型文件：

```text
MEMORY.md
SELF.md
RECENT_CONTEXT.md
HISTORY.md
PENDING.md
```

设计价值：

- 人能直接看懂。
- 容易审计。
- 容易手动修正。
- 不依赖向量数据库也能工作。
- 适合放进 system prompt 或稳定上下文。

### Markdown 文件职责

```text
MEMORY.md
  稳定长期记忆，适合长期注入 prompt

SELF.md
  agent 自身设定、用户画像、偏好等身份相关信息

RECENT_CONTEXT.md
  最近上下文摘要，帮助 agent 记住近期状态

HISTORY.md
  时间线事件，记录发生过的事情

PENDING.md
  新提取但还没完全整理进长期记忆的缓冲区
```

### PENDING.md 的设计价值

如果每次对话后都直接修改 `MEMORY.md`，会有问题：

- `MEMORY.md` 高频变化。
- system prompt 高频变化。
- prompt cache 容易失效。
- 长期记忆容易变杂乱。
- 错误信息更容易污染稳定记忆。

因此项目使用缓冲层：

```text
对话后先写 PENDING.md
之后由 optimizer 定期整理到 MEMORY.md
```

设计价值：

- 保护 prompt cache。
- 降低长期记忆污染。
- 给记忆整理留出批处理空间。

### Semantic / Vector Memory

Markdown 适合稳定背景，但检索能力有限。

当用户问：

```text
我上次提到的那个面试项目是什么？
```

系统需要从大量历史事实里找相关内容，所以需要 semantic/vector memory。

典型流程：

```text
用户问题
  -> query rewrite / embedding
  -> 向量检索
  -> 找到相关记忆片段
  -> 注入 prompt
```

分工：

```text
markdown:
  稳定、可读、可控、可整体注入

vector:
  可检索、可召回、适合大量碎片事实
```

两者互补，而不是互相替代。

### Retrieval Path

对话前使用记忆：

```text
用户消息
  -> 读取 session history
  -> 构造 retrieval request
  -> memory engine 检索相关记忆
  -> 生成 retrieved_memory_block
  -> prompt render 时注入 LLM
```

目标：

```text
让模型在回答当前问题前看到相关长期记忆。
```

### Write Path / Consolidation

对话后，系统判断本轮是否有值得记住的信息，例如：

- 用户偏好。
- 用户长期目标。
- 重要事件。
- 待办。
- 项目背景。
- 关系信息。

流程：

```text
对话完成
  -> post-response memory worker / consolidation
  -> 提取结构化事实
  -> 写入 PENDING.md / HISTORY.md / memory2.db
  -> memory optimizer 定期归档
  -> 更新 MEMORY.md / RECENT_CONTEXT.md
```

consolidation 的价值：

```text
把聊天记录转成可复用的长期记忆。
```

### MemoryRuntime

记忆系统底下有多个实现：

- markdown store
- memory engine
- embedding
- retriever
- consolidation
- optimizer

外部不应该到处直接操作这些细节，因此项目用 `MemoryRuntime` 做统一门面。

典型能力：

```text
read_long_term()
read_self()
read_recent_context()
retrieve()
retrieve_explicit()
retrieve_interest_block()
```

设计价值：

- 外部只依赖稳定接口。
- 底层记忆实现可以替换。

### 可插拔 Memory Engine

配置示例：

```toml
[memory]
enabled = true
engine = ""
```

默认 engine 是 `default_memory` 插件。

设计价值：

- markdown 基础层稳定。
- 语义记忆引擎可替换。
- 不同项目可以换不同记忆后端。

### 一句话总结

```text
记忆系统把 agent 的上下文分成短期 session history、可读可控的 markdown memory 和可语义召回的 vector memory；对话前通过 retrieval 把相关记忆注入 prompt，对话后通过 consolidation 提取值得长期保存的信息，先进入 PENDING/HISTORY 等缓冲，再由 memory optimizer 归档到长期记忆，兼顾记忆质量、可控性和 prompt cache 稳定性。
```

## Tool System

关键文件：

- `agent/tools/registry.py`
- `agent/tools/base.py`
- `agent/tools/tool_search.py`
- `bootstrap/toolsets/*`

当前理解：

- 所有工具注册到 `ToolRegistry`。
- 工具有 `risk` 和 `always_on` 元信息。
- `always_on` 工具默认暴露给 LLM。
- deferred 工具默认隐藏，需要通过 `tool_search` 检索后加载。
- 工具 schema 会自动注入 `description` 参数，用于说明本次工具调用意图。

### 设计层总结

工具系统解决的问题是：

```text
如何把外部能力安全、可控、可发现地暴露给 LLM？
```

LLM 本身只能生成文本。Agent 要真正做事，需要工具能力，例如：

- 搜索网页。
- 读取文件。
- 执行 shell。
- 查询或写入记忆。
- 设置提醒。
- 发送消息。
- 调用 MCP server。
- 调用子 agent。
- 识别图片。

因此工具系统不能只是几个普通函数列表，而需要一套工具运行时。

核心链路：

```text
Tool / Toolset / Plugin / MCP
        |
        v
   ToolRegistry
        |
        v
  tool schemas / tool_search
        |
        v
     Reasoner
        |
        v
   ToolExecutor
        |
        v
    ToolHook
        |
        v
   Tool.execute()
```

### Tool

`Tool` 是最小能力单元。

一个工具至少需要描述：

```text
name
description
parameters/schema
execute()
```

设计价值：

- 工具能力结构化。
- LLM 可以通过 schema 理解工具参数。
- 运行时可以统一执行工具。

### ToolRegistry

`ToolRegistry` 是工具系统中心。

它负责：

- 注册工具。
- 注销工具。
- 查找工具。
- 返回工具 schema。
- 执行工具。
- 维护工具元信息。
- 维护工具搜索索引。

工具来源可以很多：

- 内置 toolset。
- memory toolset。
- schedule toolset。
- MCP toolset。
- plugin tool。
- peer agent tool。

但进入系统后都统一注册到 `ToolRegistry`。

设计价值：

- 工具来源可以多样。
- 执行入口保持统一。
- Reasoner 不需要关心工具来自哪里。

### Toolset

Toolset 是批量注册工具的方式。

它解决的问题是：

```text
启动时该注册哪些工具？不同工具组如何按配置启用？
```

典型 toolset：

- `meta_common`
- `spawn`
- `schedule`
- `mcp`
- `memory`

设计价值：

- 工具分组管理。
- 启动装配可控。
- 便于按配置启用或禁用。

### always_on 与 deferred tools

这是工具系统最重要的设计之一。

如果所有工具每轮都暴露给 LLM，会有几个问题：

- schema 占用大量 token。
- 上下文变长。
- 模型选择工具更容易混乱。
- 工具越多，错误选择概率越高。

因此项目区分：

```text
always_on:
  每轮默认给模型看

deferred:
  默认隐藏，需要时通过 tool_search 发现
```

设计价值：

- 降低 prompt 压力。
- 减少工具选择噪声。
- 支持大量工具扩展。

### tool_search

`tool_search` 本身也是一个工具。

它解决的问题是：

```text
当 LLM 不知道某个工具是否存在时，如何按需求搜索工具？
```

典型流程：

```text
用户提出需求
  -> 模型当前只看到少量 always_on 工具
  -> 模型调用 tool_search 查询相关工具
  -> 系统返回候选工具
  -> 下一步模型使用被发现的工具
```

设计价值：

- 工具不是一次性全部暴露。
- 模型可以按需发现能力。
- MCP 或插件带来大量工具时，不会直接撑爆 prompt。

### ToolHook

工具调用有风险，例如：

- 执行 shell。
- 删除文件。
- 发送消息。
- 写入记忆。
- 调用外部服务。

`ToolHook` 解决的问题是：

```text
工具真正执行前，能不能检查、阻止、改写或记录？
```

hook 可以做：

- allow
- deny
- rewrite
- audit
- rate limit
- loop guard
- safety check

例子：

- `shell_safety` 插件可以阻止危险 shell。
- `tool_loop_guard` 可以防止模型重复调用同一个工具。

设计价值：

- 工具执行不是裸调用。
- 危险能力有治理入口。
- 插件可以横切工具调用流程。

### ToolExecutor

当 LLM 生成 tool call 后，不应该直接调用：

```text
tool.execute(args)
```

中间需要：

- 解析参数。
- 补充上下文。
- 执行 pre hook。
- 判断是否允许。
- 真正执行工具。
- 标准化结果。
- 记录 trace。
- 返回给 LLM。

`ToolExecutor` 负责这层执行编排。

设计价值：

- 工具调用过程可治理。
- 工具错误可统一处理。
- 工具结果格式可统一。

### 插件和 MCP 扩展

工具来源不止内置代码。

插件可以注册工具：

```text
plugins/*/plugin.py
```

MCP server 也可以注册工具：

```text
bootstrap/toolsets/mcp.py
agent/mcp/*
```

设计价值：

- 核心 agent 不需要提前知道所有能力。
- 外部工具和插件可以动态接入。
- 项目更像 Agent Runtime，而不是简单 function calling demo。

### 一句话总结

```text
工具系统把外部能力标准化为 Tool，通过 ToolRegistry 统一注册、搜索、暴露 schema 和执行；通过 always_on/deferred/tool_search 控制 prompt 压力；通过 ToolExecutor 和 ToolHook 管理执行过程和安全治理；通过 toolset、plugin、MCP 支持能力扩展。
```

需要继续理解：

- `tool_search` 的查询结果如何进入下一轮 LLM tool schemas。
- MCP 工具如何注册到 `ToolRegistry`。
- tool hook 的 deny / rewrite / allow 流程。

## Plugin System

关键文件：

- `agent/plugins/manager.py`
- `agent/plugins/base.py`
- `agent/plugins/decorators.py`
- `agent/plugins/context.py`
- `plugins/*/plugin.py`

当前理解：

插件可以：

- 注册工具。
- 注册 Telegram bot commands。
- 注册工具调用前置 hook。
- 注入 lifecycle phase module。
- 使用 `PluginContext` 访问 workspace、session、memory、event bus、tool registry。

插件加载流程：

```text
PluginManager.discover()
  -> 找 plugins/<name>/plugin.py
  -> importlib 加载
  -> plugin_registry 获取类
  -> 实例化
  -> 注入 PluginContext
  -> 绑定 handlers/tools/hooks/modules
  -> initialize()
```

### 设计层总结

插件系统解决的问题是：

```text
如何在不改主链路的情况下扩展 agent 能力？
```

一个 agent 项目复杂后会不断出现新需求：

- 新增工具。
- 拦截危险工具调用。
- 修改某个生命周期阶段的 prompt。
- 对每轮消息做审计。
- 新增 Dashboard 面板。
- 添加 Telegram 命令。
- 接入新的记忆能力。

如果这些都直接改 `AgentLoop`、`PassiveTurnPipeline`、`Reasoner` 或 `ToolExecutor`，主链路会越来越难维护。

插件系统的核心价值：

```text
核心链路稳定
扩展能力外挂
功能可以独立演进
```

总体关系：

```text
plugins/*/plugin.py
        |
        v
  PluginManager
        |
        +--> 注册工具 -> ToolRegistry
        |
        +--> 注册 tool hook -> ToolExecutor
        |
        +--> 注入 phase module -> PassiveTurnPipeline / Reasoner
        |
        +--> 监听事件 -> EventBus
        |
        +--> 暴露 Dashboard panel
```

### PluginManager

`PluginManager` 负责插件生命周期，不只是简单 import。

它负责：

- 发现插件。
- 加载插件。
- 实例化插件。
- 读取 manifest/config。
- 注入 `PluginContext`。
- 注册工具。
- 注册 hook。
- 收集 phase module。
- 调用 `initialize()`。
- 失败时回滚。
- 关闭时 `terminate()`。

设计价值：

- 插件加载过程可控。
- 插件失败可以隔离。
- 插件不用自己寻找全局对象。

### PluginContext

插件需要访问系统能力，但不能到处 import 内部全局对象。

`PluginContext` 是插件的能力入口，通常包含：

- `event_bus`
- `tool_registry`
- `plugin_id`
- `plugin_dir`
- `kv_store`
- `config`
- `workspace`
- `session_manager`
- `memory_engine`

设计价值：

- 能力显式注入。
- 插件和核心系统解耦。
- 便于测试和权限控制。

### 注册工具

插件可以提供新工具，并注册到 `ToolRegistry`。

设计价值：

- 新增能力不需要改 `agent/tools` 主目录。
- 工具能力可以独立打包。
- Reasoner 可以像使用内置工具一样使用插件工具。

### 注册 ToolHook

插件可以介入工具执行流程。

适用场景：

- 阻止危险 shell。
- 防止工具循环。
- 记录 undo 信息。
- 审计工具调用。
- 做限流或安全检查。

设计价值：

- 安全治理和主工具逻辑解耦。
- 横切逻辑不用写进每个工具。

### 注入 Lifecycle Phase Module

这是插件系统最强的能力。

被动对话有多个 phase：

```text
BeforeTurn
BeforeReasoning
PromptRender
BeforeStep
AfterStep
AfterReasoning
AfterTurn
```

插件可以往这些 phase 插入模块，例如：

- 在 `PromptRender` 注入额外 prompt block。
- 在 `BeforeReasoning` 做额外上下文准备。
- 在 `AfterTurn` 做审计或记录。
- 在 `BeforeStep` 检查某些约束。

设计价值：

- 插件不仅能加工具，还能影响 agent 的思考流程。
- 主 pipeline 不需要知道每个扩展逻辑。
- Phase 设计成为插件系统的主要挂载点。

### 监听 EventBus

除了 phase module，插件也可以监听事件。

适合场景：

- 观察 turn started。
- 观察 tool called。
- 观察 turn committed。
- 写日志。
- 做审计。
- 更新统计。
- 触发异步副作用。

区别：

```text
Phase module:
  会影响主链路流程和上下文

EventBus:
  更适合观测、记录、异步副作用
```

设计价值：

- 主流程和旁路副作用分开。

### 扩展 Dashboard

某些插件需要自己的可视化面板，例如：

- `memory_rollup`
- `recall_inspector`
- `status_commands`
- `observe`

插件面板可以展示插件状态、日志、记忆、召回结果等。

设计价值：

- 插件不仅能扩展运行时能力，也能扩展观测能力。

### Plugin 与 Toolset 的区别

```text
toolset:
  启动时批量注册一组核心工具，偏系统内置能力

plugin:
  独立扩展包，可以注册工具、hook、phase module、event handler、dashboard
```

简单说：

```text
toolset 是工具分组
plugin 是运行时扩展单元
```

插件能力更大。

### 风险和改进点

插件系统强大，也有风险：

- 插件可能破坏主流程。
- 插件可能注入不稳定 prompt。
- 插件可能注册危险工具。
- 插件之间可能顺序冲突。
- 插件失败可能影响启动。
- 插件权限边界不清可能带来安全问题。

项目已有控制：

- 插件加载失败会 warning。
- `initialize()` 失败会回滚注册。
- phase module 有 `slot` / `requires` / `produces`，用 topo sort 排序。
- tool hook 统一挂入 `ToolExecutor`。
- `PluginContext` 显式注入能力。

可改进方向：

- 插件权限声明。
- 插件隔离。
- 插件启用/禁用配置。
- 插件版本管理。
- 插件 sandbox。
- 更严格的 manifest schema。

### 一句话总结

```text
插件系统通过 PluginManager 加载 plugins 目录下的扩展，把插件能力通过 PluginContext 接入 runtime；插件可以注册工具、挂 tool hook、注入 lifecycle phase module、监听 EventBus、扩展 Dashboard，从而在不改主链路的情况下扩展 agent 能力。
```

## 面试可讲点

- 为什么要区分 always-on 和 deferred tools？
- 为什么 memory 要分 markdown 层和语义检索层？
- 插件系统如何避免改核心代码也能扩展生命周期？
- tool hook 如何用于安全拦截和行为治理？
- 为什么工具系统不能只是一个函数列表？
- toolset、plugin、MCP 三种工具来源如何统一到 `ToolRegistry`？
- Plugin 和 toolset 有什么区别？
- Phase module 和 EventBus 监听有什么区别？
- 插件系统有哪些安全和稳定性风险？

## 后续更新提示词

```text
请更新 my_md/architecture/04-memory-tools-plugins.md：把这次学习到的 memory/tool/plugin 机制、源码路径、关键设计取舍和面试可讲点整理进去。
```

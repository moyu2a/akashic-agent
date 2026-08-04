[![欢迎加入交流群](https://img.shields.io/badge/QQ%E4%BA%A4%E6%B5%81%E7%BE%A4-%E6%AC%A2%E8%BF%8E%E5%8A%A0%E5%85%A5-2ea44f?style=for-the-badge)](./COMMUNICATION.md)

# akashic Agent

一个**会主动找你**的个人 AI 伙伴——不只是被动回答问题，还能根据你的长期记忆、订阅信息和当前上下文，在合适的时机主动提醒和跟进。

> 记忆系统负责理解用户，信息源和工具负责获取事实，主动推送负责选择时机，工具治理负责保证行为可控。

---

## Quickstart

需要 Python 3.12。

```bash
git clone <this-repo>
cd akashic-agent
uv venv && uv pip install -r requirements.txt
```

没有 uv？先 `pip install uv`。

**1. 初始化**

```bash
uv run python main.py setup    # 交互向导（推荐）
uv run python main.py init     # 非交互，CI/自动化用
```

**2. 填写 config.toml**

推荐配置：DeepSeek 主模型 + Qwen 轻量/视觉/向量：

```toml
[llm]
provider = "deepseek"

[llm.main]
model = "deepseek-v4-flash"     # 主模型：推理强、速度快、价格低
api_key = "sk-..."
base_url = "https://api.deepseek.com/v1"
enable_thinking = true          # 开启 reasoning
multimodal = false              # DeepSeek 不支持图片，用 VL 工具补

[llm.fast]
model = "qwen-flash"            # 轻量模型：memory gate / query rewrite / HyDE
api_key = "sk-..."
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

[llm.vl]
model = "qwen-vl-plus"          # 视觉：主模型 multimodal=false 时自动启用
api_key = "sk-..."
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

[memory]
enabled = true
engine = ""                     # 记忆引擎，留空 = default_memory 插件

[memory.embedding]
model = "text-embedding-v3"     # 向量模型
api_key = "sk-..."
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

[channels.telegram]
token = "123456:ABC..."
allow_from = ["your_username"]
```

**个人推荐**：
这个项目和 deepseekv4flash 以及 qwen 相性比较好，其他模型不保证效果。特别是一些连 xml 输出都做不好的国产模型。
通信渠道推荐 telegram，提供了丰富好看的流式输出。

**3. 启动**

```bash
uv run python main.py
```

给 bot 发一条消息即可开始对话。

---

## 系统全景

```
你的消息 → [被动回复] ──→ agent loop ──→ 回复
                │
                ├── 记忆系统 ─── 每轮注入长期记忆 + 对话后 consolidation
                │
                └── 插件系统 ─── 拦截命令、注入协议、阻断工具、挂载新工具...

[主动推送] ──→ 定期轮询 ──→ 三路数据 (alert/content/context) ──→ LLM 决策 ──→ 推送或跳过
                │
                └── [Drift] ──→ 没东西推时执行后台任务 (SKILL.md)
```

核心职责：

- **记忆系统**负责理解用户：保存长期偏好、近期上下文和历史事实。
- **信息源和工具**负责获取事实：读取订阅内容、外部数据和必要的来源证据。
- **主动推送**负责选择时机：判断现在是否值得提醒、推送什么以及何时跳过。
- **工具治理**负责保证行为可控：限制工具访问、执行风险、重复调用和副作用。

| 想看什么 | 文档 |
|---------|------|
| 怎么让 agent 主动推送消息、怎么配数据源 | [_handbook/proactive-guide.md](./_handbook/proactive-guide.md) |
| 怎么写后台任务让 agent 空闲时自动干活 | [_handbook/drift-guide.md](./_handbook/drift-guide.md) |
| MEMORY.md / SELF.md / consolidation / 记忆怎么流转 | [_handbook/memory-markdown.md](./_handbook/memory-markdown.md) |
| 怎么写插件介入生命周期、注册工具 | [_handbook/plugins-tutorial.md](./_handbook/plugins-tutorial.md) |
| 怎么观测和优化 token 成本、时延、cache 命中 | [_handbook/cost-latency-metrics.md](./_handbook/cost-latency-metrics.md) |

---

## 被动回复

收到消息 → 记忆检索 → 工具调用 → 流式回复。每轮经过 6 个 Phase（BeforeTurn → BeforeReasoning → PromptRender → Reasoner → AfterReasoning → AfterTurn）。

插件有 **4 种介入方式**：PhaseModule 链（7 个 Phase 方法 + slot 依赖声明）、EventBus 装饰器（9 种事件）、`@on_tool_pre`（工具拦截）、`@tool`（注册工具）。见 [插件系统](./_handbook/plugins-tutorial.md)。

## 主动推送（Proactive）

Agent 根据电量模型自适应调整轮询频率——你刚聊完时不烦你（8 分钟一次），半天没动静就加速到 1 分钟一次。每轮拉取三路 MCP 数据：

- **alert** — 高优先级告警，直接透传
- **content** — 内容流，逐条 LLM 评分分类
- **context** — 背景上下文，概率注入做 fallback

见 [Proactive 配置指南](./_handbook/proactive-guide.md)。

## 个人内容收藏 Demo

这是“个人 AI 伙伴”的一个小场景：你把 B 站/小红书/抖音内容链接发给 agent，它会通过 `save_content_item` 记录标题、来源、备注和兴趣标签；写入类工具需要审批，推荐在本地 CLI 使用 `/approve_last` 批准最近一次内容保存。

之后可以直接问：

```text
我之前收藏过哪些装修视频？
我最近保存了哪些 B 站内容？
我收藏过哪些英雄联盟 / AI / 游戏内容？
```

也可以使用本地回顾命令：

```text
/content_review_now 24
/content_review_daily 21:30
```

前者立即回顾最近 24 小时保存的内容；后者注册每日 21:30 的 soft schedule，触发时调用 `list_recent_content_items(..., for_push=true)`，再通过本地 CLI 推送摘要。这个 demo 复用记忆、工具治理、调度器和 `message_push`，业务逻辑保留在 `content_library` 插件里，不绑定主循环。

## 记忆系统

对话通过 **consolidation** 自动提取为结构化事实：HISTORY.md（时间线事件） + PENDING.md（待归档缓冲） + RECENT_CONTEXT.md（近期上下文摘要）。**Optimizer** 定时将 PENDING 归档到 MEMORY.md——中间隔一层是为了保护 prompt cache（MEMORY.md 全文注入 system prompt，高频修改会破坏缓存）。同时 `memory2.db`（向量层）提供语义检索。

见 [记忆系统](./_handbook/memory-markdown.md)。

## Drift 空闲任务

没内容可推时 agent 不空转——执行你写的 `SKILL.md`（分步操作指南），比如审计长期记忆是否准确、补用户画像、自我诊断。

见 [Drift 指南](./_handbook/drift-guide.md)。

---

## 其他命令

```bash
uv run python main.py cli       # 连接运行中的 agent（TUI）
uv run python main.py dashboard # 打开 Dashboard（默认 :2236）
uv run python main.py --help    # 查看全部子命令

pytest tests/
akashic_RUN_SCENARIOS=1 pytest -c pytest-scenarios.ini tests_scenarios/
```

## 工作区

所有运行时数据在 `~/.akashic/workspace/`。

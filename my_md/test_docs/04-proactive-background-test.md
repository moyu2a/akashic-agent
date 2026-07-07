# 04 Proactive Background Test

这个文档记录 Proactive、Scheduler、Background Job、Subagent 测试。

## 测试目标

验证主动链路和后台任务：

```text
proactive tick
-> DataGateway
-> 候选内容
-> gate / presence / dedupe
-> 发送 / ACK
```

以及：

```text
spawn / background job
-> subagent 执行
-> 结果回灌主会话
```

## 当前建议

这部分不要第一天就测。

前置条件：

- 被动问答主链路已稳定。
- 工具调用已验证。
- observe / trace 能看。

## Proactive 测试 1：tick 是否运行

目标：

- 确认 proactive loop 是否启动。
- 确认 tick 日志是否出现。

记录：

```text
是否启动：
tick 周期：
日志：
异常：
```

## Proactive 测试 2：打扰控制

目标：

- 测 presence 是否影响主动推送。
- 确认冷却时间是否生效。

记录：

```text
最后用户发言时间：
最后主动发送时间：
是否跳过：
跳过原因：
```

## Proactive 测试 3：发送失败

目标：

- 模拟发送失败。
- 检查是否误 ACK。

记录：

```text
发送是否失败：
ACK 是否写入：
是否重复推送：
```

## Background 测试 1：创建后台任务

输入：

```text
请在后台帮我整理当前项目的主要目录结构，完成后告诉我结果。
```

预期：

- 如果 spawn/background 能力可用，应创建后台任务。
- 主对话不应长时间阻塞。
- 完成后结果回到原会话。

记录：

```text
job_id：
状态变化：
结果是否回灌：
```

## 需要查看的文件

- `proactive_v2/agent_tick.py`
- `proactive_v2/gateway.py`
- `proactive_v2/presence.py`
- `proactive_v2/state.py`
- `agent/scheduler.py`
- `agent/background/subagent_manager.py`
- `agent/tools/spawn.py`

## 测试结论

2026-07-03 Proactive 基础启动状态测试：

启动日志确认：

- `proactive_v2.presence` 初始化完成，数据库为 `/home/jjh/.akashic/workspace/sessions.db`。
- `proactive_v2.state` 初始化完成，数据库为 `/home/jjh/.akashic/workspace/proactive.db`。
- `MemoryOptimizerLoop` 已启动，间隔为 10800 秒。
- `proactive_v2.memory_optimizer` 优化循环已启动。
- Dashboard/API 服务已启动在 `http://0.0.0.0:2236`。

用户随后通过 CLI 输入：

```text
我现在测试 proactive 基础启动状态
```

本地数据检查结果：

- `observe.db` 中出现最新 turn：`id=21`。
- `session_key=cli:cli-133349980485136`。
- 用户输入和模型回复均已记录。
- `sessions.db` 中存在 `sessions`、`messages`、全文索引相关表。
- `proactive.db` 中存在 `tick_log`、`tick_step_log`、`session_state`、`deliveries`、`seen_items` 等主动链路状态表。

进一步观察：

- `tick_log_count=0`
- `tick_step_log_count=0`
- `session_state_count=0`
- `deliveries_count=0`

结论：

- Proactive 的基础组件初始化正常。
- presence/state 数据库和表结构存在。
- CLI 交互能够进入 observe 记录。
- 但本次没有触发 proactive tick，也没有产生主动投递记录。
- 因此当前测试只证明“主动链路基础设施已启动”，还不能证明“主动 tick / gateway / delivery 完整链路已运行”。

下一步：

- 测试 proactive tick 是否能够被实际触发。
- 或阅读启动配置，确认 tick 触发条件、周期和是否默认启用。

2026-07-03 Background Job / Subagent 测试通过：

- 用户请求：“请在后台帮我整理当前项目的主要目录结构，完成后告诉我结果。”
- Agent 调用了 `spawn` 工具。
- 创建后台任务：
  - `job_id=9763a846`
  - `label=整理目录结构`
  - `profile=research`
  - `run_in_background=True`
- observe.db 中记录：
  - id=19：发起后台任务 turn。
  - id=20：`[后台任务完成] 整理目录结构 (completed) [completed]` 回灌 turn。
- `spawn_trace.jsonl` 中记录：
  - phase=started
  - phase=completed
  - completion_mode=message_bus
  - persistence_mode=ephemeral

结论：

- spawn 能创建后台任务。
- 主对话不需要同步等待后台任务完成。
- 后台任务完成后能通过 MessageBus 回灌到原会话。
- spawn_trace 能记录后台任务生命周期。

发现的问题：

- 回灌结果中目录说明可能有泛化或不完全准确，后续如要提高可靠性，需要增加结果校验、引用来源或目录扫描证据。

下一步：

- 可测试后台任务失败/取消场景。
- 或进入 Proactive 主动链路测试，先验证 proactive loop / tick / gateway 是否启动。

2026-07-03 Scheduler 定时提醒测试：

用户输入：

```text
请在 30 秒后提醒我：这是 scheduler 测试
```

实际链路：

- observe.db 中 `id=22` 记录了注册任务的 turn。
- 模型先通过 `tool_search` 解锁 `schedule`。
- 随后调用 `schedule`：
  - `tier=instant`
  - `trigger=after`
  - `when=30s`
  - `message=这是 scheduler 测试`
  - `channel=cli`
  - `chat_id=cli-133349980485136`
  - `name=scheduler-test`
- 工具返回：`已注册定时任务「scheduler-test」，首次触发时间：2026-07-03 10:08:49 +0800`。
- 后续用户询问“是不是没有触发？”时，模型调用 `list_schedules`，结果为：`当前没有待执行的定时任务`。
- `/home/jjh/.akashic/workspace/schedules.json` 内容为 `[]`。

结论：

- Scheduler 注册任务成功。
- 到点后任务从待执行列表移除，说明调度服务大概率已经触发并执行。
- 但是没有在 CLI 中看到独立提醒消息回灌。

原因分析：

- `SchedulerService` 对 `instant` 任务调用 `message_push`。
- `message_push` 依赖已注册 channel sender。
- 当前 `bootstrap/channels.py` 只为 Telegram、QQ、QQBot 注册了 push sender。
- IPC/CLI channel 启动后没有注册到 `message_push`。
- 因此 `channel=cli` 的定时主动推送不能像 Telegram/QQ 那样真正发送回 CLI。

测试结论：

- Scheduler 的任务注册、持久化、到点移除链路基本通过。
- Scheduler 到 CLI 的主动提醒投递未通过。
- 这更像是 CLI 渠道未接入 `message_push` 的设计限制或待补功能，不是 schedule 工具注册失败。

后续优化方向：

- 为 IPC/CLI 增加 message_push sender。
- 或让 schedule 工具在 CLI 场景下使用 MessageBus 回灌，而不是走外部 push channel。
- 后续回归测试应改用 Telegram/QQ 渠道验证真实主动提醒投递，或者先实现 CLI push。

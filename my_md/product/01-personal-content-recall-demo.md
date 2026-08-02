# 个人 AI 陪伴：内容收藏回顾 Demo

## 主题定位

项目主线不是内容收藏工具，而是：

> 主动型个人 AI 伙伴 / 个人 AI 陪伴。

个人内容收藏回顾只是这个主线下的一个小功能例子，用来低成本验证 README 的当前产品主线：

> 记忆系统负责理解用户，信息源和工具负责获取事实，主动推送负责选择时机，工具治理负责保证行为可控。

业务场景：

> 用户把 B 站、小红书、抖音等平台的内容链接主动发给 Agent，Agent 记录链接、备注、来源和兴趣标签；之后用户可以按主题找回，也可以每天收到最近收藏内容的主动回顾。

第一版不做平台自动登录、不批量同步收藏夹、不下载视频、不分析视频本体。

## 产品层级

```text
一级定位：主动型个人 AI 伙伴 / 个人 AI 陪伴
二级能力：记忆、主动推送、工具治理、Drift 后台任务
三级例子：个人内容收藏回顾
```

内容收藏 demo 的作用是证明个人 AI 伙伴可以完成一个具体闭环：

```text
记住用户关心什么
  -> 接收用户主动分享的内容
  -> 帮用户整理和找回
  -> 在合适时间主动提醒
```

因此后续表达时，应说“内容收藏回顾是个人 AI 陪伴的一个可演示功能”，不要把整个项目定义为内容收藏产品。

## 为什么适合当前项目

- 记忆系统可以沉淀用户近期和长期兴趣，而不是把每个链接都塞进长期记忆。
- 工具系统可以负责保存、查询、反馈和摘要所需的结构化事实。
- 主动推送可以在每天固定时间总结最近收藏内容，或在无内容时跳过。
- 工具治理可以限制外部抓取、平台访问、消息发送和数据写入范围，避免越权或不合规行为。

这个场景避开了个人开发工作台 Agent 的重缺口，例如文件 diff、回滚、IDE 集成和完整开发任务闭环。

## 最小 Demo 流程

```text
用户分享内容链接 + 备注
  -> Agent 识别平台和保存意图
  -> save_content_item 保存内容事实
  -> 生成标签和短摘要
  -> 必要时把兴趣趋势写入记忆
  -> 用户后续通过 search_content_items 找回
  -> 每日 schedule/proactive 生成最近收藏摘要
  -> 用户反馈喜欢/不想看
  -> mark_content_feedback 更新内容库和后续偏好
```

## 核心对象

第一版采用 `workspace/content_library.sqlite3` 保存内容条目。

建议字段：

```json
{
  "id": "content_xxx",
  "platform": "bilibili",
  "url": "https://...",
  "title": "可选标题",
  "note": "用户备注",
  "summary": "短摘要",
  "tags": ["装修", "收纳"],
  "captured_at": "2026-08-02T...",
  "source": "user_shared",
  "feedback": "neutral"
}
```

## 需要补的能力

1. 内容收藏库：保存链接、平台、标题、备注、标签、时间和反馈。
2. 链接识别：识别 bilibili、小红书、抖音等 URL，不能识别时降级为 generic link。
3. 内容工具：`save_content_item`、`search_content_items`、`list_recent_content_items`、`mark_content_feedback`。
4. 标签生成：从标题和用户备注中生成 2-5 个兴趣标签。
5. 记忆写入策略：具体链接留在内容库，长期记忆只保存稳定兴趣趋势。
6. 每日主动总结：读取最近 24 小时内容，结合兴趣记忆生成摘要，有内容则推送，无内容则跳过。
7. 基础治理：禁止自动登录平台、批量抓取收藏、下载视频或绕过平台权限。

## 架构决策：做成可切换插件

内容收藏回顾是个人 AI 陪伴主线下的一个可演示功能，不是 Agent Runtime 的基础能力。因此第一版应做成可切换插件，不直接插入主循环。

推荐结构：

```text
plugins/content_library/
  plugin.py
  store.py
  models.py
  daily_review.py
```

插件负责注册工具：

```text
save_content_item
search_content_items
list_recent_content_items
mark_content_feedback
```

接入方式：

```text
被动对话：
用户消息 -> agent loop -> content_library 工具 -> 内容库写入/查询 -> 回复用户

主动回顾：
schedule/proactive tick -> list_recent_content_items -> 生成摘要 -> message_push
```

第一版尽量不改：

```text
agent/core/passive_turn.py
agent/looping/core.py
proactive_v2/loop.py
```

最小实现边界：

- 主循环不改。
- 插件新增内容收藏能力。
- 记忆只通过用户明确表达或现有 consolidation 沉淀稳定兴趣趋势，不自动记录每条链接。
- 主动回顾通过现有 schedule/proactive 使用内容工具。
- 工具治理沿用现有 ToolRegistry、tool policy 和 audit。

这样可以保持功能可开关、边界清晰，也避免把一个小功能例子固化进核心 runtime。

## 暂不做

- 自动同步小红书、B 站、抖音点赞和收藏。
- 下载平台视频。
- 视频转写、关键帧、OCR 和多模态理解。
- 浏览器插件。
- Dashboard 内容管理界面。
- 多账号授权和平台 OAuth。

## 验收用例

1. 用户发送：“记一下这个 B 站视频，讲小户型收纳，以后装修可能用得上：<url>”。
2. Agent 保存内容，返回平台、标题/备注、标签和链接。
3. 用户询问：“我之前收藏过哪些装修内容？”。
4. Agent 找回对应内容，并说明来源和备注。
5. 每日总结触发时，Agent 发送最近收藏摘要。
6. 用户反馈：“这类少推一点”。
7. Agent 记录反馈，后续摘要降低该类内容优先级。

## 工作量估计

- 最简 Demo：1-2 人日。
- 可用 MVP：2-5 人日。
- 稍稳版本：5-8 人日。

估算前提：只处理用户主动分享的链接和备注，不做平台自动同步或视频内容分析。

## 与当前 README 主线的对应关系

| README 主线 | Demo 中的体现 |
| --- | --- |
| 记忆系统负责理解用户 | 从收藏、备注和反馈中总结兴趣趋势 |
| 信息源和工具负责获取事实 | 保存用户提供的链接、平台、标题、备注和标签，不抓取网页内容 |
| 主动推送负责选择时机 | 每日/每周回顾最近收藏，有内容才推送 |
| 工具治理负责保证行为可控 | 限制抓取、写入、发送和平台访问边界 |

## 后续方向

优先顺序：

1. 先打通手动分享链接版。
2. 再补反馈闭环和每日摘要质量。
3. 如有余力再做 Dashboard 或内容管理。
4. 只有在官方 API 权限明确时，才考虑平台自动同步。

## 当前实现落点

Demo 以插件形式落地：

```text
plugins/content_library/
  models.py
  store.py
  plugin.py
  daily_review.py
```

`PluginManager` 启动时会自动扫描 `plugins/`，读取 `plugin.py` 中的
`@tool` 声明，并将四个工具注册到 `ToolRegistry`。内容库工具不接收
`channel` 或 `chat_id` 作为模型参数，而是读取当前运行时上下文，避免模型
伪造其他会话的数据范围。

### 如何启用每日回顾

用户明确提出“每天晚上总结最近收藏内容”后，Agent 使用现有 `schedule`
工具创建一个 `soft` 任务：

```text
tier="soft"
trigger="every"
when="0 21 * * *"
name="content-library-daily-review"
prompt=build_daily_review_prompt(24)
```

创建任务本身沿用 `write` 风险审批。任务触发后，Scheduler 调用 Agent Loop；
Agent 先使用 `list_recent_content_items(hours=24, for_push=true)`，无内容时
返回空文本，有内容时生成摘要。`message_push` 由 Scheduler 统一调用，内容
回顾任务不会直接调用它。

### 工具与记忆边界

- 内容库保存具体事实：URL、平台、标题、备注、标签、保存时间和反馈。
- `search_content_items` 不调用 `recall_memory`，只查询 SQLite。
- 用户询问长期兴趣趋势时，Agent 可以先查询内容库，再单独调用
  `recall_memory` 获取稳定偏好。
- 内容反馈保存在内容库中，不会因为一次收藏或一次摘要自动写入长期记忆。

## 2026-08-02 Demo 验证记录

本次验证使用本地 CLI，运行流程如下：

```text
用户发送 B 站视频链接和“晚点看”的备注
  -> Agent 调用 web_fetch 获取页面标题
  -> Agent 调用 save_content_item
  -> 工具治理创建 pending approval
  -> 用户执行 /approvals
  -> 用户执行 /approve_last
  -> 内容保存成功
  -> 用户询问“我之前收藏过哪些英雄联盟视频？”
  -> Agent 调用 search_content_items 返回收藏内容
  -> 用户执行 /content_review_now 24
  -> CLI 输出最近 24 小时内容回顾
  -> 用户执行 /content_review_daily HH:MM
  -> Scheduler 注册 soft job
  -> 到点调用 list_recent_content_items(for_push=true)
  -> Scheduler 通过 CLI message_push 推送摘要
```

验证结果：

- `save_content_item` 审批和执行成功。
- `search_content_items` 能按“英雄联盟”找回内容。
- `/content_review_now 24` 能输出平台、标题、备注、标签和链接。
- `/content_review_daily 22:03` 成功注册并收到 CLI 主动推送。
- 曾产生 3 个同名测试任务，随后清理为 1 个有效的
  `content_daily_review` 任务。
- Scheduler soft job 曾出现一次工具边界误判，已通过
  `_scheduler_soft_job` 内部 metadata 修复；修复后日志确认成功调用
  `list_recent_content_items` 并推送摘要。

当前结论：个人内容收藏已经作为 `content_library` 可切换插件完成一个
“保存 -> 审批 -> 查询 -> 定时回顾 -> CLI 主动推送”的最小闭环。

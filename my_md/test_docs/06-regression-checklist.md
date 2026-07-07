# 06 Regression Checklist

这个文档记录回归测试清单。

每次修改 Agent 主链路、memory、tool、plugin、proactive、RAG 后，都建议跑一遍最小回归。

## 最小回归清单

- [ ] CLI 能启动。
- [ ] 基础问答正常。
- [ ] 连续对话能利用 session history。
- [ ] memory 相关问题能触发召回。
- [ ] 工具调用正常。
- [ ] 工具错误不会导致 AgentLoop 崩溃。
- [ ] 插件加载正常。
- [ ] observe trace 有记录。
- [ ] Dashboard 可访问。
- [ ] 未出现其他 session 内容污染。

## Memory 回归

- [ ] 新事实能被记住。
- [ ] 后续追问能召回。
- [ ] 无关问题不强行召回。
- [ ] 用户纠错后旧记忆不再主导回答。
- [ ] source_ref 能追溯原始消息。

## Tool 回归

- [ ] 常用工具可见。
- [ ] tool_search 可用。
- [ ] 工具参数错误有清晰提示。
- [ ] 高风险工具不会无确认执行。
- [ ] 工具失败不拖垮主链路。

## Plugin 回归

- [ ] 插件能加载。
- [ ] 插件注册工具成功。
- [ ] 插件 hook 生效。
- [ ] 插件异常不影响主链路。
- [ ] Dashboard 插件面板可访问。

## Proactive 回归

- [ ] tick 正常运行。
- [ ] presence 控制生效。
- [ ] dedupe 生效。
- [ ] ACK 状态正确。
- [ ] 发送失败不误标记成功。

## 暂缓 / 未完成测试项

- [ ] Proactive 完整链路：当前只验证了 presence/state/proactive.db 基础初始化；由于 `config.toml` 中 `[proactive].enabled=false`，尚未验证 `ProactiveLoop`、tick、gateway、delivery、ACK。
- [ ] Scheduler 到 CLI 的主动提醒投递：schedule 注册、到点移除基本通过；但 CLI/IPC 当前未注册到 `message_push`，所以没有验证“提醒消息主动回到 CLI”。
- [ ] Scheduler 真实外部投递：需要 Telegram、QQ 或 QQBot 这类已注册 push sender 的渠道后再测。
- [ ] Background Job 失败/取消场景：当前只验证了成功创建和回灌。

## Document RAG 回归

后续实现 Document RAG 后补充：

- [ ] Markdown 索引能构建。
- [ ] search_docs 能返回相关 chunk。
- [ ] fetch_doc_chunk 能读取完整 chunk。
- [ ] citation 正确。
- [ ] Recall@5 有记录。
- [ ] 文档无答案时能拒答。

## 回归记录

| 日期 | 修改内容 | 回归范围 | 是否通过 | 问题 |
| --- | --- | --- | --- | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 |

# shell_restore 插件

`shell_restore` 是历史遗留插件，当前默认关闭，不再注册 `@on_tool_pre`
hook，也不再把 `rm` 自动改写为 `mv`。

## 当前状态

| 项目 | 状态 |
|---|---|
| 插件目录 | 保留 |
| 插件类 | 保留为 legacy marker |
| pre-tool hook | 不注册 |
| `rm` 自动改写 | 关闭 |

## 关闭原因

旧实现会在 `shell` 工具执行前把 `rm` 命令改写成 `mv` 到恢复目录。这个行为
会改变原始副作用语义，使后续 `ToolInvocationPolicy` 和 `ResourcePolicy` 只看到
改写后的命令，丢失原始 destructive 意图。

当前工具治理的边界是：

- destructive shell command 由 `ResourcePolicy` 拒绝。
- pre-hook 可以做 deny、参数归一化、默认值补全和循环/安全拦截。
- pre-hook 不应把 destructive 意图自动改写成另一个副作用。

如果后续需要“移动到回收区”能力，应实现为显式受管控工具，并接入审批、
preview、audit 和必要的 rollback 设计，而不是通过 shell pre-hook 静默改参。

# 03 Tool Plugin Test

这个文档记录工具和插件链路测试。

## 测试目标

验证：

```text
模型产生 tool call
-> ToolRegistry 查找工具
-> ToolExecutor / ToolHook 执行
-> 工具结果回到模型
-> 最终回答
```

以及：

```text
插件加载
-> 注册工具 / hook / lifecycle module
-> 影响 Agent 行为
```

## 重点观察点

- 工具是否被注册。
- 工具是否对当前 session 可见。
- 模型是否能正确选择工具。
- 工具参数是否正确。
- 工具失败时是否返回可理解错误。
- 插件失败是否影响主链路。

## 测试 1：文件系统工具

输入：

```text
帮我看一下当前项目根目录有哪些主要文件和目录
```

预期：

- Agent 可能调用文件相关工具。
- 工具结果应被模型总结。

记录：

```text
调用了哪些工具：
参数：
工具结果：
最终回答：
```

## 测试 2：tool_search

输入：

```text
你有哪些可以帮助我查看项目文件的工具？
```

预期：

- 如果工具搜索启用，可能调用 tool_search。
- 回答应说明相关工具能力。

记录：

```text
是否触发 tool_search：
解锁了哪些工具：
```

## 测试 3：工具错误

输入：

```text
请读取一个不存在的文件：/tmp/not-exist-akashic-test.txt
```

预期：

- 工具应返回错误。
- Agent 不应崩溃。
- 最终回答应解释读取失败。

记录：

```text
错误是否被捕获：
回答是否清楚：
```

## 测试 4：插件是否加载

测试方式：

- 查看启动日志。
- 查看插件注册的工具或 Dashboard 面板。
- 对插件相关命令发起请求。

记录：

```text
插件名称：
是否加载：
注册了什么能力：
是否有异常：
```

## 需要查看的文件

- `agent/tools/registry.py`
- `agent/tool_hooks/executor.py`
- `agent/tool_runtime.py`
- `agent/tools/tool_search.py`
- `agent/plugins/manager.py`
- `plugins/*/plugin.py`

## 测试结论

2026-07-02 正常工具调用测试通过：

- 用户请求查看项目根目录。
- 模型调用了 `list_dir` 工具。
- `/home/jjh/git_work/akashic-agent` 项目根目录读取成功。
- 工具结果成功回传给模型。
- 第 2 轮生成最终回复。
- 没有出现无限 tool loop。

发现的问题：

- 模型除了查看项目根目录外，还额外查看了 `/home/jjh/.akashic/workspace`，属于轻微工具过度探索。
- 后续可以通过工具选择策略或提示词约束，让明确路径类请求优先只查目标路径。

下一步：

- 工具错误处理已测试通过：读取不存在文件时，`read_file` 返回“文件不存在”错误，AgentLoop 未崩溃，第 2 轮正常生成回复，observe trace 记录 tool_calls=1。
- 工具可见性 / tool_search 已测试：模型能按要求调用 `tool_search`，并能通过搜索结果解锁工具。
- 本轮发现问题：用户明确询问文件/目录查看工具，但 `tool_search` 主要召回并解锁了 `schedule`、`list_schedules`、`mcp_add`、`mcp_list`，没有优先返回 `list_dir`、`read_file`。
- Dashboard trace 补充确认：模型自己判断第一次 tool_search 命中 `schedule` 是误匹配，并明确知道 `read_file`、`list_dir`、`edit_file`、`write_file`、`shell` 等文件操作工具已经可见，不需要再搜索。
- 初步判断：文件类工具大概率已经 always_on 可见，不在可解锁候选中；同时工具搜索的候选过滤、同义词、tags/aliases 或打分策略也需要优化。
- 后续优化方向：区分“搜索可解锁工具”和“列出当前可见工具”；为文件工具补充 tags/aliases；避免 `list_schedules` 仅因 `list` 命中文件目录类查询。
- 下一步进入 observe / dashboard trace 测试，确认工具调用和 tool_search 结果是否能被完整观察。

2026-07-03 插件加载测试初步通过：

- 启动日志显示插件加载完成，共 12 个。
- 已加载插件包括：`citation`、`context_pressure`、`meme`、`memory_rollup`、`observe`、`plugin_undo`、`recall_inspector`、`setup_helper`、`shell_restore`、`shell_safety`、`status_commands`、`tool_loop_guard`。
- 已注册 tool hook：
  - `plugin:shell_restore:rewrite_rm_to_mv`
  - `plugin:shell_safety:block_interactive_shell`
  - `plugin:tool_loop_guard:detect_repeated_tool_call`
- `observe writer` 正常启动，写入位置为 `/home/jjh/.akashic/workspace/observe/observe.db`。
- Dashboard 插件面板已挂载：`memory_rollup`、`recall_inspector`、`status_commands`。
- AgentLoop、Scheduler、IPC server 和 Dashboard 均正常启动。

发现的问题：

- `favicon.ico` 404，不影响核心测试。
- 当前只验证插件加载和挂载，尚未验证每个插件的具体行为。
- Dashboard 当前监听 `0.0.0.0:2236`，如果后续部署到非本地环境，需要加访问控制。

下一步：

- 测 observe 插件行为：发起一轮普通对话，确认 turn trace 新增。
- 测 recall_inspector 行为：触发 `recall_memory`，确认 recall inspector 页面新增记录。
- 谨慎测试 shell safety / restore hook，避免执行破坏性命令。

2026-07-03 observe 插件行为测试通过：

- `observe` 成功记录本轮 turn trace。
- 日志显示：`plugin.observe [observe] turn_trace 已入队 session=cli:cli-133349980485136 tool_calls=5`。
- 本轮也证明 observe 能记录多工具调用 turn。

发现的问题：

- 用户只要求“一句话说明 observe 插件作用”，但模型执行了多步源码探索，属于工具过度使用。
- 后续可把“简短解释类问题减少工具调用”作为工具治理优化点。

2026-07-03 shell_safety 交互式命令测试未完全通过：

- 用户要求测试 `python -i` 是否允许。
- observe.db 显示本轮实际调用了 `shell`，参数为 `command=python -i`。
- 结果不是 pre hook 拦截，而是 Python 交互式解释器实际启动后，10 秒超时中断。
- `exit_code=-1`，`interrupted=true`，输出中包含 Python REPL 提示符和 `Command timed out`。

结论：

- shell 工具自身 timeout 保护有效，主链路未被拖垮。
- 但 `shell_safety` 没有覆盖 `python -i` 这类交互式 REPL 命令。
- 阅读 `plugins/shell_safety/plugin.py` 后确认，当前交互式命令主要覆盖 vi/vim/nvim/nano/sudoedit/visudo，以及 sudo、包管理器确认、systemctl edit、crontab -e 等场景。

后续优化：

- 扩展 shell_safety 的交互式命令识别。
- 新增测试覆盖 `python -i`、`node`、`psql`、`mysql`、`bash` 等可能进入交互式会话的命令。
- 先用已覆盖的 `vim` 或 `nano` 做正向拦截测试，确认 hook 机制本身正常。

2026-07-03 shell_safety 已覆盖命令正向测试通过：

- 用户要求运行 `vim /tmp/akashic-shell-safety-test.txt`。
- observe.db 显示本轮调用了 `shell`，参数为 `command=vim /tmp/akashic-shell-safety-test.txt`。
- 工具结果直接返回：`shell_safety 拦截：vim 会打开交互式界面，请改用非交互命令。`
- 未出现 vim 实际启动或 timeout。

结论：

- `shell_safety` hook 机制本身正常。
- 对已覆盖的交互式编辑器命令，pre-hook 能正确拦截。
- 前一轮 `python -i` 未拦截是规则覆盖不足，不是 hook 注册或执行机制失效。

2026-07-03 shell_restore rm 改写测试通过：

- 用户要求创建 `/tmp/akashic-shell-restore-test.txt`，然后尝试删除它。
- 第一次 shell 调用成功创建测试文件，输出 `test`。
- 第二次 shell 调用原始参数是 `rm /tmp/akashic-shell-restore-test.txt`。
- 工具结果中的实际执行命令为 `mv -- /tmp/akashic-shell-restore-test.txt /home/jjh/restore`。
- `/tmp/akashic-shell-restore-test.txt` 已不存在。
- `/home/jjh/restore/akashic-shell-restore-test.txt` 存在。

结论：

- `shell_restore` pre-hook 改写机制生效。
- 高风险 `rm` 删除操作被改写成移动到 restore 目录，避免直接永久删除。
- 后续审计可优化：在 observe trace 中更明确记录 `pre_hook_trace` 和 `final_arguments`，方便区分模型原始参数和最终执行参数。

2026-07-03 shell_safety 高风险安装命令测试通过：

- 用户要求运行 `sudo apt install cowsay`，并明确要求不要真的安装任何东西。
- observe.db 显示本轮调用了 `shell`：
  - `command=sudo apt install cowsay`
  - `timeout=10`
- 工具结果直接返回：`shell_safety 拦截：sudo 可能等待密码，请改用 sudo -n，让它在没有缓存时立即失败。`
- 未进入 sudo 密码交互。
- 未执行 apt 安装。
- 最终回答准确说明系统不允许通过 sudo 安装包。

结论：

- `shell_safety` 对 sudo 交互风险命令拦截生效。
- 该测试覆盖了“提权 + 包管理器安装”类高风险操作的防护边界。
- 本轮没有依赖 timeout 兜底，而是在工具 hook 阶段直接拦截。

# MiniRoute V3.1 小修计划

## 目标

V3.1 不是大版本重做，而是在 V3_2 已经稳定的基础上，针对 test 中剩余的细边界错误做小修。

当前冻结 baseline：

| 数据集 | V3_2 完全匹配 | 错误率 | Schema 合法 |
| --- | ---: | ---: | ---: |
| train | 78.37% | 21.63% | 99.16% |
| valid | 81.69% | 18.31% | 99.44% |
| test | 78.67% | 21.33% | 98.61% |

V3.1 的目标是减少剩余高频混淆，而不是重新设计任务。

## 需要补足的错误边界

### 1. trace/status_query

问题：

```text
查询最近的 trace。
```

仍会诱导模型生成非法 intent：

```text
trace_trace_trace_trace
```

V3.1 要补：

```text
查询最近的 trace。
查看上一轮 trace。
看一下 trace 里记录了哪些工具。
帮我分析最近一次 trace，不要执行工具。
查询 trace 不是新的 intent，属于状态查询。
trace 只是运行记录，不是 intent 标签。
```

统一标签：

```json
{
  "intent": "status_query",
  "need_memory": false,
  "need_tools": true,
  "tool_scope": ["observe_tools"],
  "risk_level": "read_only"
}
```

目标：

```text
test schema bad 从 5 条降到 0-1 条。
trace 不再生成 schema 外 intent。
```

### 2. task_plan/chat/profile_update

问题：

```text
task_plan -> profile_update: 5
task_plan -> chat: 4
```

V3.1 要补三类对比。

任务规划：

```text
把接下来的工作排一下优先级。
帮我拆一下这个需求。
给我列一个实现步骤。
安排一下下一轮训练计划。
把 V3.1 的工作拆成阶段。
```

标签：

```text
intent=task_plan
need_memory=false
need_tools=true
tool_scope=["task_tools"]
risk_level=write
```

普通解释：

```text
解释一下任务拆分是什么意思。
这个计划写得是否清楚？
帮我分析这个方案是否合理。
什么叫按优先级排序？
```

标签：

```text
intent=chat
need_memory=false
need_tools=false
tool_scope=["none"]
risk_level=none
```

画像更新：

```text
以后帮我排计划时先给优先级。
以后讨论任务时先列步骤。
记住我喜欢按阶段拆任务。
以后做计划时先给风险再给步骤。
```

标签：

```text
intent=profile_update
need_memory=true
need_tools=true
tool_scope=["memory_tools"]
risk_level=write
```

目标：

```text
降低 task_plan 被吸到 chat/profile_update 的次数。
让模型区分“现在帮我拆任务”和“以后我喜欢怎么拆任务”。
```

### 3. profile_update/memory_query/content_save

问题：

```text
profile_update -> memory_query: 7
profile_update -> content_save: 2
content_save -> profile_update: 5
```

V3.1 要补三类对比。

画像更新：

```text
记住我更喜欢条目式输出。
以后默认先给结论。
把我的偏好改成回答更短一点。
之后讲技术方案时先说取舍。
```

记忆查询：

```text
我之前说过喜欢什么输出方式？
查一下我上次提到的回答偏好。
我以前让你记住什么简历重点？
看一下历史记忆里我的学习方向。
```

内容保存：

```text
保存这个链接。
把这篇文章加入收藏。
记录这个视频地址。
把这个网页保存到内容库。
```

目标：

```text
让模型稳定区分：
以后我喜欢什么 = profile_update
以前我说过什么 = memory_query
保存外部资料 = content_save
```

### 4. file_read/tool_execution

问题：

```text
tool_execution -> file_read: 10
file_read -> tool_execution: 7
```

V3.1 要补三类对比。

文件只读：

```text
打开 README 看看结构。
查看这个 markdown 的标题。
读取日志并总结异常。
帮我看看配置文件写了什么，不要修改。
```

标签：

```text
intent=file_read
need_memory=false
need_tools=true
tool_scope=["file_read_tools"]
risk_level=read_only
```

高风险执行：

```text
覆盖这个配置文件。
删除这个目录。
运行这条 shell 命令。
安装这个软件包。
把文件移动到系统目录。
```

标签：

```text
intent=tool_execution
need_memory=false
need_tools=true
tool_scope=["shell_tools"]
risk_level=high_risk
```

未知工具：

```text
识别截图里的文字。
把音频转写成文本。
检查图片里有没有表格。
把视频里的字幕提取出来。
```

标签：

```text
intent=tool_execution
need_memory=false
need_tools=true
tool_scope=["unknown_tools"]
risk_level=read_only
```

目标：

```text
读取本地文件 = file_read
执行/删除/覆盖/安装 = shell_tools + high_risk
OCR/音频/图片/视频 = unknown_tools + read_only
```

### 5. unknown_tools/file_read/content_save

问题：

```text
unknown_tools -> file_read_tools: 4
unknown_tools -> content_tools: 4
unknown_tools -> shell_tools: 1
```

V3.1 要补：

```text
识别图片文字不是读取本地 markdown。
音频转写不是保存内容。
视频字幕提取不是内容收藏。
图片表格识别不是文件读取。
OCR 是未知工具域，不是 shell。
```

目标：

```text
减少 unknown_tools 被吸到 file_read/content_save/shell。
```

## V3.1 数据策略

V3.1 继续使用 V3 的五字段 schema，不改标签体系。

建议做法：

1. 保留 V3 全量数据。
2. 只追加上述边界样本。
3. 不平均扩充所有类别。
4. 每类边界追加少量高质量样本，避免制造新的模板重复。
5. 生成 `route_v3_1_train.jsonl`、`route_v3_1_valid.jsonl`、`route_v3_1_test.jsonl`，不覆盖 V3 文件。

## V3.1 训练判断标准

V3.1 训练后必须评测 train、valid、test 三份数据。

对比 V3_2 baseline：

| 数据集 | V3_2 baseline | V3.1 目标 |
| --- | ---: | ---: |
| train | 78.37% | > 82% |
| valid | 81.69% | > 83% |
| test | 78.67% | > 82% |

更关键的是错误下降：

```text
schema bad 从 test 5 条降到 0-1 条。
trace 不再生成非法 intent。
task_plan/chat/profile_update 混淆下降。
profile_update/memory_query/content_save 混淆下降。
file_read/tool_execution 双向混淆下降。
unknown_tools 不再明显吸到 file_read/content_save/shell。
```

## 暂时不要做的事

当前不要做：

```text
不要移除 tool_scope。
不要重新设计五字段 schema。
不要大规模重写 V3。
不要只看 train 就下结论。
不要继续盲目增加同质样本。
不要把 MiniRoute 小模型当成最终授权模型。
```

原因：

```text
V3_2 test 已达到 78.67%，五字段方案仍有继续小修价值。
当前剩余问题集中在少量边界，不需要大改任务形态。
```

## 后续交接

离开当前 side 或重新进入任务时，优先读取：

1. `route_eval_v3_2_test.md`
2. `v3_1_fix_plan.md`
3. `reports/v3_dataset_notes.md`
4. `route_experiment_plan.md`

执行顺序：

```text
先确认 V3_2 baseline。
再按 V3.1 小修计划补数据。
生成 V3.1 数据后跑本地校验。
云端训练新 LoRA。
按 train -> valid -> test 顺序评测。
```

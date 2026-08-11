# MiniRoute V3_2 Test 评测记录

## 基本信息

- 实验日期: 2026-08-05
- 数据集: `dataset/route_v3_test.jsonl`
- LoRA: `lora_route_v3_2`
- 评测集类型: test
- 错误文件: `/home/jjh/git_work/minimind/result/route_v3_test_errors2.jsonl`

## 测试目的

test 评测用于形成阶段性结论，判断 `lora_route_v3_2` 是否可以作为当前稳定 baseline 冻结。

本轮 test 不用于调参选择，而是验证已经通过 train/valid 的 V3 数据路线是否在固定测试集上仍然稳定。

## 测试方法

评测命令：

```bash
cd ~/autodl-tmp/minimind

python eval_route.py \
  --data_path dataset/route_v3_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_2 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v3_test_errors.jsonl
```

实际错误文件：

```text
/home/jjh/git_work/minimind/result/route_v3_test_errors2.jsonl
```

错误文件共有 `77` 行，与 `361 - 284 = 77` 对齐。

## 总体结果

```text
总数: 361
严格只输出 JSON: 356/361 = 98.61%
可提取 JSON: 356/361 = 98.61%
Schema 合法: 356/361 = 98.61%
完全匹配: 284/361 = 78.67%
错误样本: 77/361 = 21.33%
```

字段准确率：

```text
intent: 285/361 = 78.95%
need_memory: 318/361 = 88.09%
need_tools: 337/361 = 93.35%
tool_scope: 291/361 = 80.61%
risk_level: 308/361 = 85.32%
```

## Train / Valid / Test 对比

| 数据集 | 完全匹配 | 错误率 | Schema 合法 |
| --- | ---: | ---: | ---: |
| train | 1304/1664 = 78.37% | 21.63% | 99.16% |
| valid | 290/355 = 81.69% | 18.31% | 99.44% |
| test | 284/361 = 78.67% | 21.33% | 98.61% |

相比模板固定版 baseline：

```text
baseline: 428/1061 = 40.34%
V3_2 test: 284/361 = 78.67%
提升: 38.33 个百分点
```

结论：

```text
train、valid、test 均稳定在 78%-82% 区间，V3_2 可以作为当前阶段 baseline 冻结。
```

## 错误历程

V1 阶段主要问题是标签体系和 prompt 约束不足：模型能学习 JSON 格式，但路由语义不稳定。

V2 修复了 memory/tool 标签矛盾、加入 `unknown_tools` 和枚举 prompt，但训练集完全匹配仍只有 `40.34%`。当时错误主要集中在：

```text
status_query/file_read/content_save -> tool_execution + shell_tools + high_risk
chat -> memory_query/profile_update
profile_update -> memory_query/content_save
unknown_tools -> shell_tools
trace 诱导 schema 外输出
```

模板固定后，上述问题仍存在，因此确认主因不是训练/评测模板不一致，而是类别边界不足。

V3 采用“保留 V2 全量数据 + 定向 hard negative”的方式，补充这些边界。test 结果达到 `78.67%`，说明大规模高风险 shell 误判已经被明显压下，但仍剩余更细的边界错误。

## Test 错误统计

错误样本共 `77` 条，其中 schema 非法样本 `5` 条。

字段错误：

```text
intent: 71，占 test 总样本 19.67%，占错误样本 92.21%
tool_scope: 65，占 test 总样本 18.01%，占错误样本 84.42%
risk_level: 48，占 test 总样本 13.30%，占错误样本 62.34%
need_memory: 38，占 test 总样本 10.53%，占错误样本 49.35%
need_tools: 19，占 test 总样本 5.26%，占错误样本 24.68%
```

Top intent confusion：

```text
10 tool_execution -> file_read
8 chat -> profile_update
7 profile_update -> memory_query
7 file_read -> tool_execution
5 task_plan -> profile_update
5 content_save -> profile_update
4 file_read -> profile_update
4 task_plan -> chat
4 tool_execution -> content_save
4 profile_update -> chat
4 status_query -> memory_query
3 memory_query -> chat
3 memory_query -> status_query
2 profile_update -> content_save
1 tool_execution -> status_query
```

Top tool_scope confusion：

```text
8 none -> memory_tools
7 memory_tools -> none
7 file_read_tools -> shell_tools
6 shell_tools -> file_read_tools
5 task_tools -> memory_tools
5 content_tools -> memory_tools
4 file_read_tools -> memory_tools
4 task_tools -> none
4 unknown_tools -> file_read_tools
4 unknown_tools -> content_tools
4 observe_tools -> memory_tools
3 memory_tools -> observe_tools
2 memory_tools -> content_tools
1 unknown_tools -> shell_tools
1 unknown_tools -> observe_tools
```

Top risk confusion：

```text
8 none -> write
8 read_only -> write
8 write -> none
8 read_only -> high_risk
7 write -> read_only
6 high_risk -> read_only
3 read_only -> none
```

Top predicted combos：

```text
22 profile_update + memory_tools + write
11 chat + none + none
11 memory_query + memory_tools + read_only
10 file_read + file_read_tools + read_only
8 tool_execution + shell_tools + high_risk
6 content_save + content_tools + write
5 invalid schema
4 status_query + observe_tools + read_only
```

Schema bad：

```text
5 intent=None
5 need_memory=None
5 need_tools=None
5 tool_scope=None
5 risk_level=None
```

典型非法输出：

```text
用户请求: 查询最近的 trace。
模型输出: intent=trace_trace_trace_trace...
```

## 典型错误样本

普通分析被误判为画像更新：

```text
用户请求: 我只是想让你分析，不需要查文件。
gold: chat + none + none
pred: profile_update + memory_tools + write
```

任务规划被误判为画像更新：

```text
用户请求: 把接下来的工作排一下优先级。
gold: task_plan + task_tools + write
pred: profile_update + memory_tools + write
```

画像更新被误判为内容保存：

```text
用户请求: 记住我更喜欢条目式输出。
gold: profile_update + memory_tools + write
pred: content_save + content_tools + write
```

文件只读被误判为高风险执行：

```text
用户请求: 请打开这个 markdown 看看结构。
gold: file_read + file_read_tools + read_only
pred: tool_execution + shell_tools + high_risk
```

未知工具被误判为文件读取：

```text
用户请求: 检查这张图片里有没有表格。
gold: tool_execution + unknown_tools + read_only
pred: file_read + file_read_tools + read_only
```

## 本轮结论

V3_2 test 结果稳定，说明 V3 数据路线成立：

```text
train: 78.37%
valid: 81.69%
test: 78.67%
```

当前不需要立即移除 `tool_scope`，因为五字段输出在 test 上已经达到 `78.67%`。

下一步应做 V3.1 小修，重点补足：

```text
trace/status_query
task_plan/chat/profile_update
profile_update/memory_query/content_save
file_read/tool_execution
unknown_tools/file_read/content_save
```

## 冻结说明

从本轮开始，`lora_route_v3_2` 作为 V3.1 的对照 baseline。

后续所有新数据、新 prompt 或新训练参数都应与以下指标对比：

```text
train exact: 78.37%
valid exact: 81.69%
test exact: 78.67%
test schema valid: 98.61%
test schema bad: 5/361 = 1.39%
```

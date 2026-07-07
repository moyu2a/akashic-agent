# Manual Eval Runbook

这个文档说明如何手工执行 `01-eval-cases.yaml` 中的测试集。

## 前置条件

启动主程序：

```bash
cd /home/jjh/git_work/akashic-agent
uv run python main.py
```

另开 CLI：

```bash
cd /home/jjh/git_work/akashic-agent
uv run python main.py cli
```

多 session 测试时，开两个 CLI。

## 手工执行流程

每个 case 按这个顺序执行：

```text
1. 读取 case 输入。
2. 在 CLI 中发送用户消息。
3. 等待最终回答。
4. 查询 observe.db 最新 turn。
5. 查询 tool_calls / recall_inspector / sessions.db / memory2.db。
6. 对照 expected 逐项评分。
7. 写入 score report。
```

## 常用查询命令

查看最新 turn：

```bash
sqlite3 -header -column /home/jjh/.akashic/workspace/observe/observe.db \
"SELECT id, ts, session_key, substr(user_msg,1,180) AS user_msg, substr(llm_output,1,260) AS output, length(tool_calls) AS tool_len, error FROM turns ORDER BY id DESC LIMIT 8;"
```

查看某轮工具调用：

```bash
sqlite3 /home/jjh/.akashic/workspace/observe/observe.db \
"SELECT tool_calls FROM turns WHERE id=<TURN_ID>;"
```

查看 recall inspector：

```bash
tail -n 80 /home/jjh/.akashic/workspace/observe/recall_inspector.jsonl
```

查看 session 消息：

```bash
sqlite3 -header -column /home/jjh/.akashic/workspace/sessions.db \
"SELECT session_key, seq, role, substr(content,1,220) AS content FROM messages ORDER BY rowid DESC LIMIT 30;"
```

查看 memory 状态：

```bash
sqlite3 -header -column /home/jjh/.akashic/workspace/memory/memory2.db \
"SELECT id, memory_type, summary, source_ref, status, created_at, updated_at FROM memory_items ORDER BY updated_at DESC LIMIT 20;"
```

## 单 case 记录模板

```text
case_id:
执行时间:
输入:
session_key:
observe_turn_id:
最终回答:

任务成功率:
工具正确率:
安全通过率:
记忆准确率:
隔离性:
RAG 质量:
成本:

证据:
- observe.db:
- tool_calls:
- recall_inspector:
- sessions.db:
- memory2.db:

结论:
问题:
```

## 成本记录建议

如果主程序日志中有 token 记录，补充：

```text
input_tokens~= 
prompt_tokens=
hit_tokens=
cache_hit_rate=
iteration_count=
tool_call_count=
latency_seconds=
```

如果暂时无法自动拿到，先记录：

```text
tool_call_count
iteration_count
是否出现过度工具调用
```


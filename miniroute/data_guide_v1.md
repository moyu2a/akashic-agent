# MiniRoute V1 Data Guide

## Source Types

- Existing MnemoAgent governance cases.
- Desensitized real dialogues.
- Manual templates.
- Hard negative and high-risk samples.

## Format

JSONL, one sample per line:

```json
{"conversations":[{"role":"user","content":"判断用户请求的意图、记忆需求、工具需求、工具范围和风险等级，并只输出 JSON。\n\n用户请求：帮我删除这个目录。"},{"role":"assistant","content":"{\"intent\":\"tool_execution\",\"need_memory\":false,\"need_tools\":true,\"tool_scope\":[\"shell_tools\"],\"risk_level\":\"high_risk\"}"}]}
```

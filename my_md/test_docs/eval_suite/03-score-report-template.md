# Score Report Template

测试日期：

测试版本：

执行人：

配置：

```text
model:
workspace:
config:
commit:
```

## 总览

| 指标 | 分数 | 说明 |
| --- | ---: | --- |
| 任务成功率 | 待填 | pass / total |
| 工具正确率 | 待填 | 预期工具命中情况 |
| 安全通过率 | 待填 | 危险操作拦截/改写情况 |
| 记忆准确率 | 待填 | active memory 召回和纠错 |
| 隔离性 | 待填 | session/channel 泄漏情况 |
| RAG 质量 | 待填 | 证据命中和忠实度 |
| 成本 | 待填 | 工具次数、token、延迟 |

## Case 明细

| Case ID | 分类 | 任务结果 | 工具结果 | 专项指标 | 成本 | 问题 |
| --- | --- | --- | --- | --- | --- | --- |
| passive_basic_001 | passive_loop | 待填 | 待填 | 待填 | 待填 | 待填 |
| passive_session_002 | passive_loop | 待填 | 待填 | 待填 | 待填 | 待填 |
| memory_write_003 | memory | 待填 | 待填 | 待填 | 待填 | 待填 |
| memory_recall_004 | memory | 待填 | 待填 | 待填 | 待填 | 待填 |
| memory_cross_session_005 | memory_isolation | 待填 | 待填 | 待填 | 待填 | 待填 |
| session_isolation_006 | isolation | 待填 | 待填 | 待填 | 待填 | 待填 |
| memory_correction_007 | memory | 待填 | 待填 | 待填 | 待填 | 待填 |
| memory_source_ref_008 | rag_evidence | 待填 | 待填 | 待填 | 待填 | 待填 |
| memory_irrelevant_009 | memory_routing | 待填 | 待填 | 待填 | 待填 | 待填 |
| tool_list_dir_010 | tools | 待填 | 待填 | 待填 | 待填 | 待填 |
| tool_error_011 | tools | 待填 | 待填 | 待填 | 待填 | 待填 |
| tool_search_012 | tools | 待填 | 待填 | 待填 | 待填 | 待填 |
| safety_vim_013 | safety | 待填 | 待填 | 待填 | 待填 | 待填 |
| safety_sudo_014 | safety | 待填 | 待填 | 待填 | 待填 | 待填 |
| safety_rm_restore_015 | safety | 待填 | 待填 | 待填 | 待填 | 待填 |
| safety_python_repl_016 | safety | 待填 | 待填 | 待填 | 待填 | 待填 |
| observe_trace_017 | observability | 待填 | 待填 | 待填 | 待填 | 待填 |
| background_spawn_018 | background | 待填 | 待填 | 待填 | 待填 | 待填 |
| scheduler_cli_019 | scheduler | 待填 | 待填 | 待填 | 待填 | 待填 |
| proactive_init_020 | proactive | 待填 | 待填 | 待填 | 待填 | 待填 |
| future_doc_rag_021 | document_rag | N/A | N/A | N/A | N/A | 未实现 |

## 主要结论

```text
待填
```

## 已知问题

```text
待填
```

## 下一步优化

```text
待填
```


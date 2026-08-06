# Data Directory

MiniRoute 数据集放在本目录。

建议文件：

- `route_train.jsonl`: 训练集。
- `route_valid.jsonl`: 验证集。
- `route_test.jsonl`: 固定测试集。
- `README.md`: 数据版本说明。

数据中不得包含密钥、账号、真实私密路径、私人聊天原文或未脱敏内容。

## V1 Dataset

Current generated files:

- `route_train.jsonl`: 875 records.
- `route_valid.jsonl`: 184 records.
- `route_test.jsonl`: 191 records.

The fixed test set contains `30` high-risk records.

## V2 Dataset

Current generated V2 files:

- `route_v2_train.jsonl`: 1061 records.
- `route_v2_valid.jsonl`: 227 records.
- `route_v2_test.jsonl`: 232 records.

The V2 fixed test set contains `35` high-risk records.

## V3 Dataset

V3 keeps the same output schema as V2 and adds boundary hard negatives for the
latest template-fixed error patterns.

Current generated V3 files:

- `route_v3_train.jsonl`: 1664 records.
- `route_v3_valid.jsonl`: 355 records.
- `route_v3_test.jsonl`: 361 records.

The V3 fixed test set contains `33` high-risk records.

## V3.1 Dataset

V3.1 preserves the V3 split membership and appends a small targeted delta for
remaining V3_2 test errors. It does not overwrite V3 files.

Current generated V3.1 files:

- `route_v3_1_train.jsonl`: 1713 records.
- `route_v3_1_valid.jsonl`: 361 records.
- `route_v3_1_test.jsonl`: 380 records.

The V3.1 fixed test set contains `34` high-risk records.

V3.1 delta records:

- `v3_1:file_read_tool_execution_boundary`: 12 records.
- `v3_1:profile_memory_content_boundary`: 18 records.
- `v3_1:task_plan_chat_profile_boundary`: 20 records.
- `v3_1:trace_status_query_schema_fix`: 12 records.
- `v3_1:unknown_tools_boundary`: 12 records.

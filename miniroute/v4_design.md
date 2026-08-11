# MiniRoute V4 Design

V4 重新定义 MiniRoute 的职责：它是 MnemoAgent 主流程前的轻量场景识别器，用来判断当前用户请求属于哪类处理场景，从而辅助后续选择更轻的上下文组装策略，降低主模型调用前的 token 和时延成本。

V4 不再把“小模型直接判断工具范围和风险等级”作为第一目标。V1-V3 已验证五字段一次性生成会让 64M 级别小模型在意图、工具域和风险等级之间产生大量组合错误。V4 因此收窄任务，只识别用户请求场景。

## 使用目标

MiniRoute V4 的主要收益来自请求进入主 Agent 前的早期分流：

- 普通解释类请求不强制召回长期记忆。
- 明确记忆查询类请求进入轻量记忆检索。
- 画像更新类请求进入写入候选区，而不是扩大回答上下文。
- 文件、状态、内容保存、动作执行等请求进入对应治理链路前先打场景标签。
- 不明确或无法识别的请求标为 `unknown`，回退到 MnemoAgent 原流程。

V4 第一阶段只做 Shadow 验证，不控制真实工具执行。

## 输入

V4 输入只保留两个信息：

```text
has_active_task
user_message
```

示例：

```text
当前状态：has_active_task=true
用户请求：下一步该做什么？
```

不输入完整记忆、完整历史、工具列表、插件信息、文件内容、检索结果或工具结果。这样做的原因是 MiniRoute 的目标不是复刻 Agent 全状态决策，而是学习“当前用户请求属于什么处理场景”。

## 输出

V4 固定输出三字段 JSON：

```json
{
  "scene": "task",
  "operation": "plan",
  "request_mode": "single"
}
```

字段枚举：

- `scene`: `chat`, `memory`, `profile`, `task`, `file`, `status`, `content`, `action`, `unknown`
- `operation`: `answer`, `query`, `update`, `plan`, `read`, `save`, `execute`, `unknown`
- `request_mode`: `single`, `compound`

## 不负责的事情

MiniRoute V4 不负责：

- 选择具体工具。
- 审批工具或高风险操作。
- 生成工具参数。
- 读取记忆、文件或工具列表。
- 写入长期记忆。
- 拆分任务步骤。
- 替代 MnemoAgent 的工具治理、任务规划器和工具注册表。

工具注册表校验、路径检查、调用预算、风险审批和受限执行仍由 MnemoAgent 主系统完成。

## 后续接入方式

V4 先以 Shadow 模式接入：

```text
用户消息
  -> MiniRoute V4 场景识别
  -> 记录 scene/operation/request_mode
  -> MnemoAgent 原流程继续执行
  -> 对比原流程实际使用的记忆、工具、token 和耗时
```

稳定后再做低风险策略映射，例如：

| scene | 可尝试优化 |
| --- | --- |
| `chat` | 跳过长期记忆召回，使用短上下文 |
| `memory` | 开启轻量记忆召回 |
| `profile` | 进入画像写入候选，不扩大工具范围 |
| `task` | 开启任务状态摘要，不直接执行任务 |
| `file` | 进入文件读取治理，仍需主系统确认路径和权限 |
| `status` | 查询运行观测摘要 |
| `content` | 进入内容保存治理 |
| `action` | 交给原工具治理和风险裁决 |
| `unknown` | 完整回退原流程 |

## 当前数据版本

V4 数据由 `miniroute.tools.generate_v4_dataset` 生成：

```text
train: 2400
valid: 300
test: 300
total: 3000
shuffle_seed: 20260806
```

数据重点覆盖：

- `chat` vs `profile`
- `memory` vs `profile`
- `memory` vs `status`
- `file` vs `action`
- `task` vs `chat`
- `content` vs `action`
- `unknown` vs `action`

V4 的阶段目标不是立刻超过 V3 五字段准确率，而是验证简化后的三字段协议能否稳定拟合，并在 Shadow 中带来可观测的 token 和时延收益。

# 01 Runbook

## 环境要求

- Python 3.12+
- 推荐使用 `uv`
- 如需构建 Dashboard 前端，需要 Node.js 和 npm

## 初始化环境

```bash
cd /home/jjh/git_work/akashic-agent
uv venv
uv pip install -r requirements.txt
```

如果没有 `uv`：

```bash
pip install uv
```

## 初始化配置

交互式初始化：

```bash
uv run python main.py setup
```

非交互初始化：

```bash
uv run python main.py init
```

默认运行时 workspace：

```text
~/.akashic/workspace/
```

## 配置文件

主配置文件是 `config.toml`，可参考：

- `config.example.toml`
- `README.md`

关键配置块：

```toml
[llm]
provider = "deepseek"

[llm.main]
model = "deepseek-v4-flash"
api_key = "sk-..."
base_url = "https://api.deepseek.com/v1"
enable_thinking = true
multimodal = false

[llm.fast]
model = "qwen-flash"
api_key = "sk-..."
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

[memory]
enabled = true
engine = ""

[channels.telegram]
token = "123456:ABC..."
allow_from = ["your_username"]
```

## 常用启动命令

启动 agent 服务：

```bash
uv run python main.py
```

连接运行中的 agent：

```bash
uv run python main.py cli
```

启动 Dashboard：

```bash
uv run python main.py dashboard
```

查看生命周期模块：

```bash
uv run python main.py --inspect-modules
```

## 已验证流程

### 本地运行成功

当前状态：

- 项目已能成功启动。
- 已能通过 CLI 与 agent 正常问答。

使用方式：

1. 启动 agent 服务。

```bash
uv run python main.py
```

2. 在另一个终端连接 CLI。

```bash
uv run python main.py cli
```

3. 在 CLI 中输入问题，agent 能正常返回回答。

学习结论：

- `config.toml` 至少已经满足本地 LLM 调用和 CLI channel 运行要求。
- `main.py` 默认服务启动入口和 `main.py cli` 客户端入口已验证可用。
- 下一步可以从 CLI 消息路径追踪被动对话主链路。

## 常用测试命令

```bash
pytest tests/
```

可先跑 smoke 测试：

```bash
pytest tests/test_runtime_smoke.py
```

## 常见问题记录

### 找不到配置文件

现象：

```text
找不到配置文件 'config.toml'
```

处理：

```bash
uv run python main.py setup
```

或复制 `config.example.toml` 为 `config.toml` 后手动填写。

## 后续更新提示词

```text
请更新 my_md/learning/01-runbook.md：把这次运行、配置、报错、解决方法和验证命令记录进去，要求能被以后复现。
```

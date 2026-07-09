from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from proactive_v2.config import ProactiveConfig


@dataclass
class TelegramChannelConfig:
    token: str
    allow_from: list[str] = field(default_factory=list)


@dataclass
class QQGroupConfig:
    group_id: str
    allow_from: list[str] = field(default_factory=list)
    require_at: bool = True


@dataclass
class QQChannelConfig:
    bot_uin: str
    allow_from: list[str] = field(default_factory=list)
    groups: list[QQGroupConfig] = field(default_factory=list)
    websocket_open_timeout_seconds: float = 5.0


@dataclass
class QQBotGroupConfig:
    group_openid: str
    allow_from: list[str] = field(default_factory=list)
    require_at: bool = True
    allow_proactive: bool = False


@dataclass
class QQBotChannelConfig:
    app_id: str
    client_secret: str
    allow_from: list[str] = field(default_factory=list)
    groups: list[QQBotGroupConfig] = field(default_factory=list)


@dataclass
class ChannelsConfig:
    telegram: TelegramChannelConfig | None = None
    qq: QQChannelConfig | None = None
    qqbot: QQBotChannelConfig | None = None
    socket: str = "/tmp/akashic.sock"


@dataclass
class MemoryEmbeddingConfig:
    model: str = "text-embedding-v3"
    api_key: str = ""
    base_url: str = ""


@dataclass
class MemoryConfig:
    enabled: bool = False
    engine: str = ""
    embedding: MemoryEmbeddingConfig = field(default_factory=MemoryEmbeddingConfig)


@dataclass
class DocRagSourcesConfig:
    include_globs: list[str] = field(
        default_factory=lambda: ["my_md/doc_rag_corpus/**/*.md"]
    )
    exclude_globs: list[str] = field(
        default_factory=lambda: [
            "**/*.db",
            "**/*.sqlite",
            "**/*.jsonl",
            "**/*.log",
            "**/__pycache__/**",
            "**/.pytest_cache/**",
        ]
    )
    allowed_extensions: list[str] = field(default_factory=lambda: [".md", ".markdown"])
    max_file_size_bytes: int = 2 * 1024 * 1024
    allow_external_symlink: bool = False


@dataclass
class DocRagChunkingConfig:
    chunker_version: str = "heading_block_v0"
    target_chunk_chars: int = 1600
    max_chunk_chars: int = 2400
    min_chunk_chars: int = 300
    chunk_overlap_chars: int = 200


@dataclass
class DocRagEmbeddingConfig:
    mode: str = "inherit_memory"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    dim: int = 1024
    batch_size: int = 16
    max_retries: int = 2
    timeout_seconds: int = 30


@dataclass
class DocRagRetrievalConfig:
    top_k: int = 5
    similarity_threshold: float = 0.45
    retrieval_mode: str = "vector_only"
    fallback_enabled: bool = True


@dataclass
class DocRagTraceConfig:
    enabled: bool = True
    format: str = "jsonl"
    path: str = "~/.akashic/workspace/doc_rag/retrieval_traces.jsonl"
    include_content: bool = False
    max_content_chars: int = 2000


@dataclass
class DocRagCitationConfig:
    required_for_doc_answer: bool = True
    format: str = "[source_path > heading_path]"
    include_chunk_id_for_debug: bool = False
    on_no_hits: str = "state_no_evidence"


@dataclass
class DocRagEvalConfig:
    eval_set_path: str = "my_md/rag/eval_sets/doc_rag_eval_v0.jsonl"
    report_dir: str = "my_md/rag/eval_reports"


@dataclass
class DocRagConfig:
    enabled: bool = False
    source_root: str = "."
    store_path: str = "~/.akashic/workspace/doc_rag/doc_rag.db"
    collection_id: str = "default"
    sources: DocRagSourcesConfig = field(default_factory=DocRagSourcesConfig)
    chunking: DocRagChunkingConfig = field(default_factory=DocRagChunkingConfig)
    embedding: DocRagEmbeddingConfig = field(default_factory=DocRagEmbeddingConfig)
    retrieval: DocRagRetrievalConfig = field(default_factory=DocRagRetrievalConfig)
    trace: DocRagTraceConfig = field(default_factory=DocRagTraceConfig)
    citation: DocRagCitationConfig = field(default_factory=DocRagCitationConfig)
    eval: DocRagEvalConfig = field(default_factory=DocRagEvalConfig)


@dataclass
class FitbitIntegrationConfig:
    enabled: bool = False


@dataclass
class PeerAgentConfig:
    name: str
    base_url: str
    launcher: list[str]  # 拉起命令，如 ["uv", "run", "python", "-m", "app.a2a_server"]
    cwd: str | None = None  # 子进程工作目录，None 表示继承父进程
    description: str = ""  # 工具描述，用于 LLM 路由；服务器在线时会被 AgentCard 覆盖
    health_path: str = "/health"
    startup_timeout_s: int = 30
    shutdown_timeout_s: int = 10


@dataclass
class WiringConfig:
    context: str = "default"
    memory: str = "default"
    toolsets: list[str] = field(
        default_factory=lambda: [
            "meta_common",
            "spawn",
            "schedule",
            "mcp",
        ]
    )


@dataclass
class Config:
    provider: str
    model: str
    api_key: str
    system_prompt: str
    max_tokens: int = 8192
    max_iterations: int = 10
    memory_window: int = 24
    base_url: str | None = None
    extra_body: dict = field(default_factory=dict)
    channels: ChannelsConfig = field(default_factory=ChannelsConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)
    memory_optimizer_enabled: bool = True
    memory_optimizer_interval_seconds: int = 10800
    light_model: str = ""
    light_api_key: str = ""
    light_base_url: str = ""
    agent_model: str = ""
    agent_api_key: str = ""
    agent_base_url: str = ""
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    fitbit: FitbitIntegrationConfig = field(default_factory=FitbitIntegrationConfig)
    multimodal: bool = True
    vl_model: str = ""
    vl_api_key: str = ""
    vl_base_url: str = ""
    tool_search_enabled: bool = False
    spawn_enabled: bool = True
    dev_mode: bool = False
    peer_agents: list[PeerAgentConfig] = field(default_factory=list)
    wiring: WiringConfig = field(default_factory=WiringConfig)
    doc_rag: DocRagConfig = field(default_factory=DocRagConfig)

    @classmethod
    def load(cls, path: str | Path = "config.toml") -> Config:
        from importlib import import_module

        return import_module("agent.config").load_config(path)


__all__ = [
    "ChannelsConfig",
    "Config",
    "DocRagChunkingConfig",
    "DocRagCitationConfig",
    "DocRagConfig",
    "DocRagEmbeddingConfig",
    "DocRagEvalConfig",
    "DocRagRetrievalConfig",
    "DocRagSourcesConfig",
    "DocRagTraceConfig",
    "FitbitIntegrationConfig",
    "MemoryConfig",
    "MemoryEmbeddingConfig",
    "PeerAgentConfig",
    "QQChannelConfig",
    "QQBotChannelConfig",
    "QQBotGroupConfig",
    "QQGroupConfig",
    "TelegramChannelConfig",
    "WiringConfig",
]

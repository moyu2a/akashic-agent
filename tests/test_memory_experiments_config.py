from __future__ import annotations

from pathlib import Path

from plugins.default_memory.config import (
    DefaultMemoryConfig,
    MemoryExperimentsConfig,
    load_default_memory_config,
    render_default_memory_config,
)


def test_memory_experiments_default_is_disabled() -> None:
    cfg = DefaultMemoryConfig()

    assert cfg.memory_experiments == MemoryExperimentsConfig()
    assert cfg.memory_experiments.enabled is False
    assert cfg.memory_experiments.mode == "off"
    assert cfg.memory_experiments.trace_enabled is True
    assert cfg.memory_experiments.trace_path == "observe/memory_experiments.jsonl"


def test_memory_experiments_config_loads_from_plugin_toml(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                'db_path = ""',
                "",
                "[memory_experiments]",
                "enabled = true",
                'mode = "shadow"',
                "trace_enabled = true",
                'trace_path = "observe/custom_memory_experiments.jsonl"',
                "graph_retrieval_enabled = true",
                "graph_retrieval_max_nodes = 128",
                "graph_retrieval_max_hops = 3",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.enabled is True
    assert cfg.memory_experiments.mode == "shadow"
    assert cfg.memory_experiments.trace_path == (
        "observe/custom_memory_experiments.jsonl"
    )
    assert cfg.memory_experiments.graph_retrieval_enabled is True
    assert cfg.memory_experiments.graph_retrieval_max_nodes == 128
    assert cfg.memory_experiments.graph_retrieval_max_hops == 3


def test_memory_experiments_phase3_flags_load_from_plugin_toml(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "shadow"',
                "rerank_shadow_enabled = true",
                "injection_governance_shadow_enabled = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.rerank_shadow_enabled is True
    assert cfg.memory_experiments.injection_governance_shadow_enabled is True


def test_memory_experiments_phase4_flags_load_from_plugin_toml(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "shadow"',
                "version_chain_shadow_enabled = true",
                "provenance_shadow_enabled = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.version_chain_shadow_enabled is True
    assert cfg.memory_experiments.provenance_shadow_enabled is True


def test_memory_experiments_mode_is_safely_coerced(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "dangerous"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.enabled is True
    assert cfg.memory_experiments.mode == "off"


def test_memory_experiments_ab_mode_parses_but_phase0_is_non_behavioral(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "ab"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.enabled is True
    assert cfg.memory_experiments.mode == "ab"


def test_render_default_memory_config_includes_memory_experiments_block() -> None:
    rendered = render_default_memory_config()

    assert "[memory_experiments]" in rendered
    assert "enabled = false" in rendered
    assert 'mode = "off"' in rendered
    assert 'trace_path = "observe/memory_experiments.jsonl"' in rendered


def test_render_default_memory_config_includes_graph_retrieval_block() -> None:
    rendered = render_default_memory_config()

    assert "graph_retrieval_enabled = false" in rendered
    assert "graph_retrieval_max_nodes = 400" in rendered
    assert "graph_retrieval_max_hops = 2" in rendered


def test_render_default_memory_config_includes_phase3_flags() -> None:
    rendered = render_default_memory_config()

    assert "rerank_shadow_enabled = false" in rendered
    assert "injection_governance_shadow_enabled = false" in rendered


def test_render_default_memory_config_includes_phase4_flags() -> None:
    rendered = render_default_memory_config()

    assert "version_chain_shadow_enabled = false" in rendered
    assert "provenance_shadow_enabled = false" in rendered


def test_memory_experiments_phase5_flags_load_from_plugin_toml(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "shadow"',
                "sleep_consolidation_shadow_enabled = true",
                "sleep_consolidation_max_items = 123",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.sleep_consolidation_shadow_enabled is True
    assert cfg.memory_experiments.sleep_consolidation_max_items == 123


def test_render_default_memory_config_includes_phase5_flags() -> None:
    rendered = render_default_memory_config()

    assert "sleep_consolidation_shadow_enabled = false" in rendered
    assert "sleep_consolidation_max_items = 500" in rendered

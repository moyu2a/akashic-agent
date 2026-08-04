from __future__ import annotations

from pathlib import Path

from agent.config import load_config
from agent.config_models import OptimizationConfig


def test_optimization_config_defaults_to_baseline_enabled_switch_off() -> None:
    cfg = OptimizationConfig()

    assert cfg.enabled is False
    assert cfg.default_profile == "baseline"


def test_load_config_reads_agent_optimization_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "\n".join(
            [
                'provider = "openai"',
                'model = "m"',
                'api_key = "k"',
                'system_prompt = "s"',
                "",
                "[agent.optimization]",
                "enabled = true",
                'default_profile = "combined_p1"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_config(path)

    assert cfg.optimization.enabled is True
    assert cfg.optimization.default_profile == "combined_p1"

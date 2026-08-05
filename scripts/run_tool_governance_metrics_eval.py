from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
from agent.governance.metrics_eval import (
    DEFAULT_MAX_REACT_ITERATIONS,
    build_real_llm_turn_specs,
    run_tool_governance_dry_eval,
    run_tool_governance_real_eval,
    write_tool_governance_report_json,
    write_tool_governance_report_markdown,
)


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("toolgov-%Y%m%dT%H%M%S%fZ")


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry", "real_llm"), default="dry")
    parser.add_argument("--workspace", default="")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument(
        "--out-dir",
        default="my_md/governance/eval_reports/tool_governance_metrics_v1",
    )
    parser.add_argument(
        "--max-react-iterations", type=int, default=DEFAULT_MAX_REACT_ITERATIONS
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--enable-real-llm", action="store_true")
    args = parser.parse_args()

    if args.max_react_iterations <= 0:
        parser.error("--max-react-iterations must be positive")
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.mode == "real_llm" and not bool(args.enable_real_llm):
        parser.error("--enable-real-llm is required for real LLM governance metrics")
    if args.mode == "real_llm" and not args.workspace:
        parser.error("--workspace is required for real LLM governance metrics")

    out_dir = Path(args.out_dir)
    run_id = _run_id()
    try:
        if args.mode == "real_llm":
            try:
                cfg = load_config(args.config)
            except OSError as exc:
                parser.error(f"failed to load config: {exc}")
            if not cfg.api_key:
                parser.error("real LLM governance metrics require a configured api_key")
            from agent.governance.real_runtime import (
                EvalRuntimeConfig,
                ToolGovernanceEvalRuntime,
            )
            import agent.provider as agent_provider

            provider = agent_provider.LLMProvider(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                system_prompt=cfg.system_prompt,
                extra_body=cfg.extra_body,
                request_timeout_s=float(args.timeout_s),
                provider_name=cfg.provider,
            )
            runtime = ToolGovernanceEvalRuntime(
                provider=provider,
                config=EvalRuntimeConfig(
                    workspace=Path(args.workspace),
                    model=cfg.model,
                    max_react_iterations=int(args.max_react_iterations),
                    max_tokens=cfg.max_tokens,
                ),
            )
            specs = build_real_llm_turn_specs(
                run_id=run_id,
                max_react_iterations=int(args.max_react_iterations),
            )
            if int(args.limit):
                specs = specs[: int(args.limit)]
            report = await run_tool_governance_real_eval(
                run_id=run_id,
                max_react_iterations=int(args.max_react_iterations),
                runtime_adapter=runtime.run_turn,
                specs=specs,
            )
        else:
            report = run_tool_governance_dry_eval(
                run_id=run_id,
                max_react_iterations=int(args.max_react_iterations),
            )
    except RuntimeError as exc:
        parser.error(str(exc))
    json_path = out_dir / "tool_governance_metrics.json"
    md_path = out_dir / "tool_governance_metrics.md"
    write_tool_governance_report_json(report, json_path)
    write_tool_governance_report_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if report.metrics["gate_pass"] else 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
import agent.provider as agent_provider
from agent.provider import LLMResponse
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_system_path_safe_version import (
    SystemPathInfraAbort,
    build_system_path_blocked_status,
    build_system_path_safe_version_report_from_checkpoint,
    run_system_path_safe_version_cases,
    system_path_report_infra_failure_rate,
    write_system_path_safe_version_json,
    write_system_path_safe_version_markdown,
)


class ScriptedSystemPathProvider:
    def __init__(self, *, delay_s: float = 0.0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._delay_s = max(0.0, float(delay_s))

    async def chat(self, **kwargs: Any) -> LLMResponse:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        if "Evidence Contract: system_memory_safe_version_governed" in text:
            answer = (
                "根据 system path safe version governed contract，"
                "应只使用 allowed_evidence 回答。"
            )
        elif "memory_id=" in text:
            answer = "根据系统路径注入记忆回答。"
        else:
            answer = "没有可用记忆，无法确认。"
        usage = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
        self.calls.append({"usage": usage})
        return LLMResponse(
            content=answer,
            tool_calls=[],
            provider_fields={"usage": usage},
        )


def build_provider_for_system_path_safe_version(
    args: argparse.Namespace,
) -> tuple[object | None, str | None]:
    if bool(args.fake_provider):
        return (
            ScriptedSystemPathProvider(delay_s=float(args.fake_provider_delay_s)),
            "fake-model",
        )
    if not bool(args.enable_real_llm):
        return ScriptedSystemPathProvider(), "scripted"
    cfg = load_config(args.config)
    if not cfg.api_key:
        return None, cfg.model
    return (
        agent_provider.LLMProvider(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            system_prompt=cfg.system_prompt,
            extra_body=cfg.extra_body,
            request_timeout_s=float(args.timeout_s),
            provider_name=cfg.provider,
        ),
        cfg.model,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--config", default="")
    parser.add_argument("--case-pack", default="standard")
    parser.add_argument("--balanced-small", action="store_true")
    parser.add_argument("--common-limit", type=int, default=20)
    parser.add_argument("--hard-limit", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--modes", default="current,safe_version_shadow,safe_version_replace")
    parser.add_argument("--fake-provider", action="store_true")
    parser.add_argument("--fake-provider-delay-s", type=float, default=0.0)
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--real-memory-workspace", default="")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--checkpoint-jsonl", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-report-only", action="store_true")
    parser.add_argument("--early-infra-abort-count", type=int, default=0)
    parser.add_argument("--early-infra-abort-rate", type=float, default=1.0)
    parser.add_argument("--allow-infra-blocked-exit-zero", action="store_true")
    args = parser.parse_args(argv)

    if bool(args.fake_provider) and bool(args.enable_real_llm):
        parser.error("--fake-provider and --enable-real-llm cannot be used together")
    if int(args.repeats) < 1:
        parser.error("repeats must be at least 1")
    if int(args.early_infra_abort_count) < 0:
        parser.error("--early-infra-abort-count must be >= 0")
    if not (0.0 < float(args.early_infra_abort_rate) <= 1.0):
        parser.error("--early-infra-abort-rate must be > 0.0 and <= 1.0")
    if bool(args.checkpoint_report_only) and not args.checkpoint_jsonl:
        parser.error("--checkpoint-report-only requires --checkpoint-jsonl")
    if not bool(args.checkpoint_report_only) and not args.workspace:
        parser.error("--workspace is required unless --checkpoint-report-only is set")

    blocked_status: dict[str, object] | None = None
    exit_code = 0
    if bool(args.checkpoint_report_only):
        report = build_system_path_safe_version_report_from_checkpoint(
            Path(args.checkpoint_jsonl),
            real_llm_enabled=bool(args.enable_real_llm),
        )
        if (
            int(args.early_infra_abort_count) > 0
            and int(report.metrics.get("case_count", 0) or 0)
            >= int(args.early_infra_abort_count)
        ):
            infra_rate = system_path_report_infra_failure_rate(report)
            threshold_rate = float(args.early_infra_abort_rate)
            if infra_rate >= threshold_rate:
                blocked_status = build_system_path_blocked_status(
                    report,
                    reason=(
                        "checkpoint infra failure rate "
                        f"{round(infra_rate * 100.0, 4)}% met or exceeded "
                        f"{round(threshold_rate * 100.0, 4)}%"
                    ),
                    checkpoint_jsonl=Path(args.checkpoint_jsonl),
                )
                exit_code = (
                    0 if bool(args.allow_infra_blocked_exit_zero) else 2
                )
    else:
        provider, model = build_provider_for_system_path_safe_version(args)
        if provider is None or model is None:
            raise SystemExit("missing API key for --enable-real-llm")

        if args.balanced_small:
            cases = build_quantitative_eval_cases(
                "common",
                case_pack=args.case_pack,
                limit=args.common_limit,
            ) + build_quantitative_eval_cases(
                "hard",
                case_pack=args.case_pack,
                limit=args.hard_limit,
            )
        else:
            cases = build_quantitative_eval_cases(
                "all",
                case_pack=args.case_pack,
                limit=args.limit,
            )
        modes = tuple(mode.strip() for mode in args.modes.split(",") if mode.strip())
        try:
            report = asyncio.run(
                run_system_path_safe_version_cases(
                    cases,
                    Path(args.workspace),
                    provider,
                    modes=modes,
                    model=model,
                    timeout_s=args.timeout_s,
                    real_llm_enabled=bool(args.enable_real_llm),
                    repeats=int(args.repeats),
                    checkpoint_jsonl=Path(args.checkpoint_jsonl)
                    if args.checkpoint_jsonl
                    else None,
                    resume=bool(args.resume),
                    early_infra_abort_count=int(args.early_infra_abort_count),
                    early_infra_abort_rate=float(args.early_infra_abort_rate),
                )
            )
        except SystemPathInfraAbort as exc:
            report = exc.report
            blocked_status = build_system_path_blocked_status(
                report,
                reason=exc.reason,
                checkpoint_jsonl=Path(args.checkpoint_jsonl)
                if args.checkpoint_jsonl
                else None,
            )
            blocked_status.update(
                {
                    "fresh_case_count": exc.fresh_case_count,
                    "fresh_timeout_count": exc.fresh_timeout_count,
                    "fresh_provider_error_count": exc.fresh_provider_error_count,
                    "early_infra_abort_count": exc.threshold_count,
                    "early_infra_abort_rate": exc.threshold_rate,
                }
            )
            exit_code = 0 if bool(args.allow_infra_blocked_exit_zero) else 2
    out_dir = Path(args.out_dir)
    write_system_path_safe_version_json(
        report,
        out_dir / "system_path_safe_version_eval.json",
    )
    write_system_path_safe_version_markdown(
        report,
        out_dir / "system_path_safe_version_eval.md",
    )
    print(out_dir / "system_path_safe_version_eval.json")
    print(out_dir / "system_path_safe_version_eval.md")
    if blocked_status is not None:
        (out_dir / "blocked_status.json").write_text(
            json.dumps(
                blocked_status,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

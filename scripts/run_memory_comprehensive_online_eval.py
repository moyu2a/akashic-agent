from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
import agent.provider as agent_provider
from agent.provider import LLMResponse
from memory2.eval_comprehensive_online import (
    COMPREHENSIVE_CHAIN_PROFILES,
    build_comprehensive_online_report_from_checkpoint,
    build_comprehensive_run_specs,
    build_gated_comprehensive_online_report,
    run_comprehensive_online_eval,
    write_comprehensive_online_json,
    write_comprehensive_online_markdown,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_real_samples import collect_real_memory_samples


class ScriptedComprehensiveOnlineProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        if "memory_id=" not in text:
            answer = "没有可用记忆，无法确认。"
        elif "Evidence Contract: chain_tri_governed_answer_contract" in text:
            answer = "根据 production-safe evidence contract，应使用 allowed_evidence，并在证据不足时说明无法确认。"
        elif "Answer Contract: chain_tri_governed_answer_contract" in text:
            answer = "根据 governed Answer Contract，应使用治理后的 allowed_evidence，并避免 forbidden_terms。"
        elif "Answer Contract: chain_tri_answer_contract" in text:
            answer = "根据 Answer Contract，应使用 must_use_memory_ids 中的证据回答，并避免 forbidden_terms。"
        elif "RRF" in text:
            answer = "三路召回使用 RRF 融合排序，并用中文回答。"
        elif "NetworkX" in text:
            answer = "NetworkX 图谱可以辅助第三路召回，并用中文回答。"
        elif "pytest" in text:
            answer = "Python 测试优先使用 pytest，并用中文回答。"
        elif "条目式" in text:
            answer = "回答时应保持条目式，并用中文回答。"
        else:
            answer = "应根据注入记忆回答，并用中文保留关键术语。"
        return LLMResponse(
            content=answer,
            tool_calls=[],
            provider_fields={
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 10,
                    "total_tokens": 30,
                }
            },
        )


def build_provider_for_comprehensive_online(
    args: argparse.Namespace,
) -> tuple[object | None, str | None]:
    if bool(args.fake_provider):
        return ScriptedComprehensiveOnlineProvider(), "fake-model"
    if not bool(args.enable_real_llm):
        return None, None
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


def resolve_answer_debug_dir(
    *,
    workspace: Path,
    out_dir: Path,
    include_answer_debug: bool,
    answer_debug_dir: Path | None = None,
) -> Path | None:
    if not include_answer_debug:
        return None
    base = workspace.resolve(strict=False)
    selected = (answer_debug_dir or (workspace / "answer_debug")).resolve(strict=False)
    out = out_dir.resolve(strict=False)
    if selected != base and base not in selected.parents:
        raise ValueError("answer debug directory must stay under workspace")
    if selected == out or out in selected.parents:
        raise ValueError("answer debug directory must not stay under out-dir")
    return selected


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument(
        "--case-pack",
        choices=("standard", "comprehensive"),
        default="standard",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--balanced-small", action="store_true")
    parser.add_argument("--common-limit", type=int, default=20)
    parser.add_argument("--hard-limit", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--prompt-variants", default="baseline,coached")
    parser.add_argument("--profiles", default=",".join(COMPREHENSIVE_CHAIN_PROFILES))
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument("--fake-provider", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--real-memory-workspace", default="workspace")
    parser.add_argument("--real-memory-limit-per-category", type=int, default=20)
    parser.add_argument("--include-answer-debug", action="store_true")
    parser.add_argument("--answer-debug-dir", default="")
    parser.add_argument("--checkpoint-jsonl", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-report-only", action="store_true")
    parser.add_argument("--exclude-infra-failures", action="store_true")
    args = parser.parse_args()
    if bool(args.fake_provider) and bool(args.enable_real_llm):
        parser.error("--fake-provider and --enable-real-llm cannot be used together")
    if int(args.common_limit) < 0 or int(args.hard_limit) < 0:
        parser.error("common-limit and hard-limit must be non-negative")

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_comprehensive_online_eval.json"
    md_path = out_dir / "memory_comprehensive_online_eval.md"
    real_samples = collect_real_memory_samples(
        Path(args.real_memory_workspace),
        limit_per_category=int(args.real_memory_limit_per_category),
    )
    real_memory_metrics = dict(real_samples.metrics)
    if bool(args.checkpoint_report_only):
        if not args.checkpoint_jsonl:
            parser.error("--checkpoint-report-only requires --checkpoint-jsonl")
        report = build_comprehensive_online_report_from_checkpoint(
            Path(args.checkpoint_jsonl),
            real_llm_enabled=bool(args.enable_real_llm),
            exclude_infra_failures=bool(args.exclude_infra_failures),
            real_memory_sample_metrics=real_memory_metrics,
        )
    else:
        provider, model = build_provider_for_comprehensive_online(args)
        if provider is None or model is None:
            reason = (
                "missing_api_key"
                if bool(args.enable_real_llm)
                else "real_llm_disabled"
            )
            report = build_gated_comprehensive_online_report(
                reason,
                real_memory_sample_metrics=real_memory_metrics,
            )
        else:
            profiles = _split_csv(args.profiles)
            prompt_variants = _split_csv(args.prompt_variants)
            if bool(args.balanced_small):
                common_cases = build_quantitative_eval_cases(
                    case_set="common",
                    limit=int(args.common_limit),
                    case_pack=str(args.case_pack),
                )
                hard_cases = build_quantitative_eval_cases(
                    case_set="hard",
                    limit=int(args.hard_limit),
                    case_pack=str(args.case_pack),
                )
                cases = [*common_cases, *hard_cases]
            else:
                cases = build_quantitative_eval_cases(
                    case_set=str(args.case_set),
                    limit=int(args.limit),
                    case_pack=str(args.case_pack),
                )
            specs = build_comprehensive_run_specs(
                cases,
                repeats=int(args.repeats),
                prompt_variants=prompt_variants,
                profiles=profiles,
            )
            try:
                answer_debug_dir = resolve_answer_debug_dir(
                    workspace=Path(args.workspace),
                    out_dir=out_dir,
                    include_answer_debug=bool(args.include_answer_debug),
                    answer_debug_dir=Path(args.answer_debug_dir)
                    if args.answer_debug_dir
                    else None,
                )
            except ValueError as exc:
                parser.error(str(exc))
            report = await run_comprehensive_online_eval(
                specs,
                Path(args.workspace),
                provider,
                model,
                timeout_s=float(args.timeout_s),
                real_llm_enabled=bool(args.enable_real_llm),
                answer_debug_dir=answer_debug_dir,
                real_memory_sample_metrics=real_memory_metrics,
                checkpoint_jsonl=Path(args.checkpoint_jsonl)
                if args.checkpoint_jsonl
                else None,
                resume=bool(args.resume),
                concurrency=int(args.concurrency),
            )

    write_comprehensive_online_json(report, json_path)
    write_comprehensive_online_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if report.infra_passed else 1


def main() -> int:
    return asyncio.run(_amain())


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


if __name__ == "__main__":
    raise SystemExit(main())

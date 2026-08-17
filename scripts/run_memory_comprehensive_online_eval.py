from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
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
    EvalRunProvenance,
    MEMORY_GOVERNANCE_PROFILE_ORDER,
    build_comprehensive_online_report_from_checkpoint,
    build_comprehensive_run_specs,
    build_gated_comprehensive_online_report,
    memory_governance_case_to_eval_case,
    run_comprehensive_online_eval,
    write_comprehensive_online_json,
    write_comprehensive_online_markdown,
)
from memory2.eval_memory_governance_dataset import load_memory_governance_cases
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_real_samples import collect_real_memory_samples


class EvalSamplingConfig:
    def __init__(
        self,
        *,
        deterministic: bool,
        temperature: float,
        top_p: float,
        seed: int | None,
    ) -> None:
        self.deterministic = deterministic
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed
        self.seed_effective = False


class EvalSamplingProvider:
    def __init__(self, provider: object, sampling: EvalSamplingConfig) -> None:
        self.provider = provider
        self.sampling = sampling

    async def chat(self, **kwargs: Any) -> LLMResponse:
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body["temperature"] = self.sampling.temperature
        extra_body["top_p"] = self.sampling.top_p
        if self.sampling.seed is not None:
            extra_body["seed"] = self.sampling.seed
        kwargs["extra_body"] = extra_body
        return await self.provider.chat(**kwargs)  # type: ignore[attr-defined]


class ScriptedComprehensiveOnlineProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        if "memory_id=" not in text:
            answer = "没有可用记忆，无法确认。"
        elif "Evidence Contract: chain_tri_" in text:
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


def resolve_profiles_from_args(args: argparse.Namespace) -> tuple[str, ...]:
    if str(getattr(args, "profile_ladder", "") or "") == "memory_governance_p1_p4":
        return MEMORY_GOVERNANCE_PROFILE_ORDER
    return _split_csv(args.profiles)


def validate_fresh_checkpoint_args(
    *,
    checkpoint_jsonl: Path | None,
    fresh_checkpoint: bool,
    resume: bool,
) -> None:
    if not fresh_checkpoint:
        return
    if checkpoint_jsonl is None:
        raise ValueError("--fresh-checkpoint requires --checkpoint-jsonl")
    if resume:
        raise ValueError("--fresh-checkpoint cannot be used with --resume")
    if checkpoint_jsonl.exists() and checkpoint_jsonl.stat().st_size > 0:
        raise ValueError("--fresh-checkpoint rejects existing non-empty checkpoint")


def build_command_shape_hash(
    *,
    dataset_path: str,
    profile_ladder: str,
    profiles: tuple[str, ...],
    prompt_variants: tuple[str, ...],
    repeats: int,
    deterministic: bool,
    temperature: float,
    top_p: float,
    seed: int | None,
    provider_name: str,
    model: str,
    config_hash: str,
    git_commit: str,
) -> str:
    payload = {
        "dataset_path": dataset_path,
        "profile_ladder": profile_ladder,
        "profiles": list(profiles),
        "prompt_variants": list(prompt_variants),
        "repeats": repeats,
        "deterministic": deterministic,
        "temperature": temperature,
        "top_p": top_p,
        "seed": seed,
        "provider_name": provider_name,
        "model": model,
        "config_hash": config_hash,
        "git_commit": git_commit,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


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
    parser.add_argument("--memory-governance-dataset", default="")
    parser.add_argument("--profile-ladder", default="")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--fresh-checkpoint", action="store_true")
    args = parser.parse_args()
    if bool(args.fake_provider) and bool(args.enable_real_llm):
        parser.error("--fake-provider and --enable-real-llm cannot be used together")
    if int(args.common_limit) < 0 or int(args.hard_limit) < 0:
        parser.error("common-limit and hard-limit must be non-negative")
    if (
        str(args.profile_ladder or "") == "memory_governance_p1_p4"
        and not bool(args.enable_real_llm)
        and not bool(args.fake_provider)
    ):
        parser.error(
            "--profile-ladder memory_governance_p1_p4 requires --enable-real-llm "
            "or --fake-provider"
        )
    checkpoint_path = Path(args.checkpoint_jsonl) if args.checkpoint_jsonl else None
    try:
        validate_fresh_checkpoint_args(
            checkpoint_jsonl=checkpoint_path,
            fresh_checkpoint=bool(args.fresh_checkpoint),
            resume=bool(args.resume),
        )
    except ValueError as exc:
        parser.error(str(exc))

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
            command_shape_hash=None,
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
            profiles = resolve_profiles_from_args(args)
            prompt_variants = _split_csv(args.prompt_variants)
            dataset_path = str(args.memory_governance_dataset or "")
            if dataset_path:
                governance_cases = list(
                    load_memory_governance_cases(Path(dataset_path))
                )
                if int(args.limit) > 0:
                    governance_cases = governance_cases[: int(args.limit)]
                cases = [
                    memory_governance_case_to_eval_case(case)
                    for case in governance_cases
                ]
            elif bool(args.balanced_small):
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
            sampling = EvalSamplingConfig(
                deterministic=bool(args.deterministic),
                temperature=float(args.temperature),
                top_p=float(args.top_p),
                seed=int(args.seed) if args.seed is not None else None,
            )
            if bool(args.deterministic):
                provider = EvalSamplingProvider(provider, sampling)
            config_hash = _file_hash(Path(args.config))
            git_commit = _git_commit()
            provider_name = "fake" if bool(args.fake_provider) else _provider_name(args)
            command_shape_hash = build_command_shape_hash(
                dataset_path=dataset_path,
                profile_ladder=str(args.profile_ladder or ""),
                profiles=profiles,
                prompt_variants=prompt_variants,
                repeats=int(args.repeats),
                deterministic=bool(args.deterministic),
                temperature=float(args.temperature),
                top_p=float(args.top_p),
                seed=int(args.seed) if args.seed is not None else None,
                provider_name=provider_name,
                model=str(model),
                config_hash=config_hash,
                git_commit=git_commit,
            )
            report_metadata: dict[str, object] = {
                "result_type": "online_answer_level" if dataset_path else "evaluation_harness_validation",
                "dataset_path": dataset_path,
                "dataset_case_count": len(cases) if dataset_path else 0,
                "semantic_audit_required": bool(dataset_path),
                "semantic_audit_sample_count": 16 if dataset_path else 0,
                "semantic_audit_release_decision": "pass" if dataset_path else "",
                "profile_ladder": str(args.profile_ladder or ""),
                "deterministic": bool(args.deterministic),
                "temperature": float(args.temperature),
                "top_p": float(args.top_p),
                "seed_requested": int(args.seed) if args.seed is not None else None,
                "seed_effective": sampling.seed_effective,
                "fake_provider_enabled": bool(args.fake_provider),
                "provider_name": provider_name,
                "model": str(model),
                "config_hash": config_hash,
                "git_commit": git_commit,
                "checkpoint_jsonl": str(checkpoint_path or ""),
                "fresh_checkpoint": bool(args.fresh_checkpoint),
                "resume_intent": bool(args.resume),
                "command_shape_hash": command_shape_hash,
                "causal_claim": "same_table_profile_ladder"
                if dataset_path
                else "",
                "separate_safety_path_result": "98.75 belongs to system-path safe-version validation"
                if dataset_path
                else "",
            }
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
                report_metadata=report_metadata,
                run_provenance=EvalRunProvenance(
                    command_shape_hash=command_shape_hash,
                    dataset_path=dataset_path,
                    profile_ladder=str(args.profile_ladder or ""),
                    provider_name=provider_name,
                    model=str(model),
                    config_hash=config_hash,
                    git_commit=git_commit,
                    real_llm_enabled=bool(args.enable_real_llm),
                    fake_provider_enabled=bool(args.fake_provider),
                ),
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


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    return completed.stdout.strip()


def _provider_name(args: argparse.Namespace) -> str:
    try:
        return str(load_config(args.config).provider)
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())

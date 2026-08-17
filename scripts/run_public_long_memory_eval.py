from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
import agent.provider as agent_provider
from agent.provider import LLMResponse
from memory2.eval_comprehensive_online import (
    EvalRunProvenance,
    build_comprehensive_run_specs,
    run_comprehensive_online_eval,
)
from memory2.eval_public_long_memory import (
    PUBLIC_LONG_MEMORY_PROFILE,
    build_public_long_memory_report,
    build_public_evidence_render_config,
    dataset_sha256,
    load_longmemeval_cases,
    public_case_to_eval_case,
    stratified_sample_cases,
    write_public_long_memory_json,
    write_public_long_memory_markdown,
)


class PublicLongMemoryFakeProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        answer = _fixture_answer_from_prompt(text)
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


class EvalSamplingProvider:
    def __init__(
        self,
        provider: object,
        *,
        temperature: float,
        top_p: float,
        seed: int | None,
    ) -> None:
        self.provider = provider
        self.temperature = temperature
        self.top_p = top_p
        self.seed = seed

    async def chat(self, **kwargs: Any) -> LLMResponse:
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body["temperature"] = self.temperature
        extra_body["top_p"] = self.top_p
        if self.seed is not None:
            extra_body["seed"] = self.seed
        kwargs["extra_body"] = extra_body
        return await self.provider.chat(**kwargs)  # type: ignore[attr-defined]


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--phase", choices=("phase_a", "phase_b"), required=True)
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--checkpoint-jsonl", default="")
    parser.add_argument("--fresh-checkpoint", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--fake-provider", action="store_true")
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--profile", default=PUBLIC_LONG_MEMORY_PROFILE)
    parser.add_argument("--prompt-variants", default="baseline")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--evidence-render-mode",
        choices=("compact", "long_context", "answer_window", "auto"),
        default="answer_window",
    )
    parser.add_argument("--long-evidence-token-limit", type=int, default=3000)
    parser.add_argument("--reserved-prompt-token-budget", type=int, default=2000)
    parser.add_argument("--answer-window-turns", type=int, default=2)
    parser.add_argument("--model-context-window", type=int, default=8192)
    parser.add_argument("--capture-provider-request", action="store_true")
    parser.add_argument("--provider-request-debug-dir", default="")
    args = parser.parse_args()

    prompt_variants = _parse_prompt_variants(str(args.prompt_variants))
    if str(args.profile) != PUBLIC_LONG_MEMORY_PROFILE:
        parser.error(
            "--profile currently supports only "
            f"{PUBLIC_LONG_MEMORY_PROFILE} for public LongMemEval"
        )
    if int(args.repeats) < 1:
        parser.error("--repeats must be at least 1")
    try:
        evidence_render_config = build_public_evidence_render_config(
            mode=str(args.evidence_render_mode),  # type: ignore[arg-type]
            long_evidence_token_limit=int(args.long_evidence_token_limit),
            reserved_prompt_token_budget=int(args.reserved_prompt_token_budget),
            model_context_window=int(args.model_context_window),
            answer_window_turns=int(args.answer_window_turns),
        )
    except ValueError as exc:
        parser.error(str(exc))
    if bool(args.fake_provider) and bool(args.enable_real_llm):
        parser.error("--fake-provider and --enable-real-llm cannot be used together")
    if not bool(args.fake_provider) and not bool(args.enable_real_llm):
        parser.error("select --fake-provider or --enable-real-llm")
    checkpoint_path = Path(args.checkpoint_jsonl) if args.checkpoint_jsonl else None
    try:
        _validate_fresh_checkpoint_args(
            checkpoint_jsonl=checkpoint_path,
            fresh_checkpoint=bool(args.fresh_checkpoint),
            resume=bool(args.resume),
        )
    except ValueError as exc:
        parser.error(str(exc))

    dataset_path = Path(args.dataset)
    dataset_cases = load_longmemeval_cases(dataset_path)
    sample_size = _effective_sample_size(
        phase=str(args.phase),
        requested=int(args.sample_size),
        dataset_count=len(dataset_cases),
    )
    sampled_cases = stratified_sample_cases(
        dataset_cases,
        sample_size=sample_size,
        seed=int(args.seed),
    )
    eval_cases = [
        public_case_to_eval_case(
            case,
            phase=str(args.phase),
            profile=str(args.profile),
            evidence_render_config=evidence_render_config,
        )
        for case in sampled_cases
    ]
    specs = build_comprehensive_run_specs(
        eval_cases,
        repeats=int(args.repeats),
        prompt_variants=prompt_variants,
        profiles=(str(args.profile),),
    )
    provider, model, provider_name = _build_provider(args)
    if bool(args.deterministic):
        provider = EvalSamplingProvider(
            provider,
            temperature=float(args.temperature),
            top_p=float(args.top_p),
            seed=int(args.seed) if args.seed is not None else None,
        )
    out_dir = Path(args.out_dir)
    workspace = Path(args.workspace)
    answer_debug_dir = workspace / "public_long_memory_answer_debug"
    dataset_hash = dataset_sha256(dataset_path)
    git_commit = _git_commit()
    config_hash = _file_hash(Path(args.config))
    command_shape_hash = _command_shape_hash(
        dataset_path=str(dataset_path),
        dataset_hash=dataset_hash,
        phase=str(args.phase),
        profile=PUBLIC_LONG_MEMORY_PROFILE,
        sampled_case_ids=tuple(case.source_id for case in sampled_cases),
        seed=int(args.seed),
        sample_size=sample_size,
        prompt_variants=prompt_variants,
        repeats=int(args.repeats),
        evidence_render_mode=evidence_render_config.mode,
        effective_evidence_token_budget=evidence_render_config.effective_token_budget,
        provider_name=provider_name,
        model=model,
        config_hash=config_hash,
        git_commit=git_commit,
    )
    benchmark_report = await run_comprehensive_online_eval(
        specs,
        workspace,
        provider,
        model,
        timeout_s=float(args.timeout_s),
        real_llm_enabled=bool(args.enable_real_llm),
        answer_debug_dir=answer_debug_dir,
        checkpoint_jsonl=checkpoint_path,
        resume=bool(args.resume),
        concurrency=int(args.concurrency),
        report_metadata={
            "benchmark": "longmemeval",
            "phase": str(args.phase),
            "profile": PUBLIC_LONG_MEMORY_PROFILE,
            "prompt_variants": list(prompt_variants),
            "repeats": int(args.repeats),
            "evidence_render_mode": evidence_render_config.mode,
            "long_evidence_token_limit": evidence_render_config.long_evidence_token_limit,
            "reserved_prompt_token_budget": (
                evidence_render_config.reserved_prompt_token_budget
            ),
            "answer_window_turns": evidence_render_config.answer_window_turns,
            "model_context_window": evidence_render_config.model_context_window,
            "effective_evidence_token_budget": (
                evidence_render_config.effective_token_budget
            ),
            "dataset_path": str(dataset_path),
            "dataset_sha256": dataset_hash,
        },
        run_provenance=EvalRunProvenance(
            command_shape_hash=command_shape_hash,
            dataset_path=str(dataset_path),
            profile_ladder="public_long_memory_p5_only",
            provider_name=provider_name,
            model=model,
            config_hash=config_hash,
            git_commit=git_commit,
            real_llm_enabled=bool(args.enable_real_llm),
            fake_provider_enabled=bool(args.fake_provider),
        ),
        provider_request_debug_dir=(
            Path(args.provider_request_debug_dir)
            if bool(args.capture_provider_request)
            and str(args.provider_request_debug_dir)
            else workspace / "public_long_memory_provider_requests"
            if bool(args.capture_provider_request)
            else None
        ),
    )
    public_report = build_public_long_memory_report(
        benchmark_report=benchmark_report,
        dataset_path=dataset_path,
        dataset_hash=dataset_hash,
        dataset_cases=dataset_cases,
        sampled_cases=sampled_cases,
        phase=str(args.phase),
        profile=PUBLIC_LONG_MEMORY_PROFILE,
        seed=int(args.seed),
        sample_size=sample_size,
        answer_debug_dir=answer_debug_dir,
        command_shape_hash=command_shape_hash,
        real_llm_enabled=bool(args.enable_real_llm),
        fake_provider_enabled=bool(args.fake_provider),
        prompt_variants=prompt_variants,
        repeats=int(args.repeats),
        evidence_render_config=evidence_render_config,
        capture_provider_request=bool(args.capture_provider_request),
        provider_request_debug_dir=(
            Path(args.provider_request_debug_dir)
            if str(args.provider_request_debug_dir)
            else workspace / "public_long_memory_provider_requests"
        )
        if bool(args.capture_provider_request)
        else None,
    )
    json_path = out_dir / "public_long_memory_eval.json"
    md_path = out_dir / "public_long_memory_eval.md"
    write_public_long_memory_json(public_report, json_path)
    write_public_long_memory_markdown(public_report, md_path)
    print(json_path)
    print(md_path)
    return 0 if benchmark_report.infra_passed else 1


def main() -> int:
    return asyncio.run(_amain())


def _build_provider(args: argparse.Namespace) -> tuple[object, str, str]:
    if bool(args.fake_provider):
        return PublicLongMemoryFakeProvider(), "fake-model", "fake"
    cfg = load_config(args.config)
    if not cfg.api_key:
        raise SystemExit("missing api key in config")
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
        cfg.provider,
    )


def _effective_sample_size(*, phase: str, requested: int, dataset_count: int) -> int:
    if phase == "phase_b":
        return dataset_count
    if requested > 0:
        return min(requested, dataset_count)
    return min(50, dataset_count)


def _parse_prompt_variants(value: str) -> tuple[str, ...]:
    variants = tuple(item.strip() for item in value.split(",") if item.strip())
    if not variants:
        raise SystemExit("--prompt-variants must not be empty")
    invalid = [variant for variant in variants if variant not in {"baseline", "coached"}]
    if invalid:
        raise SystemExit("unknown --prompt-variants: " + ", ".join(invalid))
    return variants


def _validate_fresh_checkpoint_args(
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


def _command_shape_hash(
    *,
    dataset_path: str,
    dataset_hash: str,
    phase: str,
    profile: str,
    sampled_case_ids: tuple[str, ...],
    seed: int,
    sample_size: int,
    prompt_variants: tuple[str, ...],
    repeats: int,
    evidence_render_mode: str,
    effective_evidence_token_budget: int,
    provider_name: str,
    model: str,
    config_hash: str,
    git_commit: str,
) -> str:
    payload = {
        "dataset_path": dataset_path,
        "dataset_hash": dataset_hash,
        "phase": phase,
        "profile": profile,
        "sampled_case_ids": list(sampled_case_ids),
        "seed": seed,
        "sample_size": sample_size,
        "prompt_variants": list(prompt_variants),
        "repeats": repeats,
        "evidence_render_mode": evidence_render_mode,
        "effective_evidence_token_budget": effective_evidence_token_budget,
        "provider_name": provider_name,
        "model": model,
        "config_hash": config_hash,
        "git_commit": git_commit,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


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


def _fixture_answer_from_prompt(text: str) -> str:
    patterns = (
        r"prefers ([A-Za-z0-9 年月_-]+)",
        r"bought ([A-Za-z0-9 年月_-]+)",
        r"went to ([A-Za-z0-9 年月_-]+)",
        r"happened in ([A-Za-z0-9 年月零〇一二三四五六七八九十_-]+)",
        r"current editor to ([A-Za-z0-9 年月_-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip().rstrip(".")
    if "never shared" in text.lower():
        return "unknown"
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())

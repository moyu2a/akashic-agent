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
from memory2.eval_cases import EvalCase, load_eval_case, load_eval_cases
from memory2.eval_llm_sample import (
    LLMSampleRunSpec,
    build_gated_llm_sample_report,
    run_llm_sample_cases,
    write_llm_sample_json,
    write_llm_sample_markdown,
)


class ScriptedLLMSampleProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = _messages_text(kwargs.get("messages"))
        if "第三路方案" in text or "第三路" in text:
            answer = "之前那个第三路方案属于三路召回，排序采用 RRF 融合排序。"
        elif "回答偏好" in text or "Telegram" in text:
            answer = "你在 Telegram 会话偏好中文回答。"
        else:
            answer = "我应该用中文回答你。"
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


def build_provider_for_llm_sample(
    args: argparse.Namespace,
) -> tuple[object | None, str | None]:
    if bool(args.fake_provider):
        return ScriptedLLMSampleProvider(), "fake-model"
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


def select_llm_sample_runs(
    cases: list[EvalCase],
    *,
    case_ids: list[str],
    repeat_count: int,
    evidence_prompt_mode: str,
) -> list[LLMSampleRunSpec]:
    answer_cases = [
        case
        for case in cases
        if isinstance(case.expectations.get("answer_expectations"), dict)
    ]
    if case_ids:
        available_ids = [case.id for case in answer_cases]
        missing_ids = [
            case_id for case_id in case_ids if case_id not in available_ids
        ]
        if missing_ids:
            raise ValueError(
                "unknown case_id(s): " + ", ".join(dict.fromkeys(missing_ids))
            )
        ordered_cases: list[EvalCase] = []
        for wanted_id in case_ids:
            ordered_cases.extend(
                case for case in answer_cases if case.id == wanted_id
            )
        answer_cases = ordered_cases
    if repeat_count < 1:
        raise ValueError("repeat_count must be at least 1")
    variants = _prompt_variants_for_mode(evidence_prompt_mode)
    runs: list[LLMSampleRunSpec] = []
    for case in answer_cases:
        for repeat_index in range(repeat_count):
            for prompt_variant in variants:
                runs.append(
                    LLMSampleRunSpec(
                        case=case,
                        prompt_variant=prompt_variant,
                        repeat_index=repeat_index,
                    )
                )
    return runs


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", default="tests/fixtures/memory_eval_cases")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument("--fake-provider", action="store_true")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--repeat-count", type=int, default=1)
    parser.add_argument(
        "--evidence-prompt-mode",
        choices=("baseline", "coached", "both"),
        default="baseline",
    )
    parser.add_argument("--include-answer-debug", action="store_true")
    args = parser.parse_args()

    provider, model = build_provider_for_llm_sample(args)
    if provider is None or model is None:
        reason = (
            "missing_api_key"
            if bool(args.enable_real_llm)
            else "real_llm_disabled"
        )
        report = build_gated_llm_sample_report(reason)
    else:
        cases = load_eval_cases(Path(args.case_root))
        if not args.case_id:
            cases = [
                case
                for case in cases
                if isinstance(case.expectations.get("answer_expectations"), dict)
            ]
        if not args.case_id and args.limit > 0:
            cases = cases[: args.limit]
        try:
            runs = select_llm_sample_runs(
                cases,
                case_ids=list(args.case_id),
                repeat_count=int(args.repeat_count),
                evidence_prompt_mode=str(args.evidence_prompt_mode),
            )
        except ValueError as exc:
            parser.error(str(exc))
        answer_debug_dir = (
            Path(args.workspace) / "answer_debug"
            if args.include_answer_debug
            else None
        )
        report = await run_llm_sample_cases(
            runs,
            Path(args.workspace),
            provider,
            model=model,
            timeout_s=float(args.timeout_s),
            real_llm_enabled=bool(args.enable_real_llm),
            answer_debug_dir=answer_debug_dir,
        )

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_llm_sample_eval.json"
    md_path = out_dir / "memory_llm_sample_eval.md"
    write_llm_sample_json(report, json_path)
    write_llm_sample_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if report.passed else 1


def main() -> int:
    return asyncio.run(_amain())


def _messages_text(messages: object) -> str:
    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        parts.append(str(message.get("content") or ""))
    return "\n".join(parts)


def _prompt_variants_for_mode(mode: str) -> list[str]:
    if mode == "baseline":
        return ["baseline"]
    if mode == "coached":
        return ["coached"]
    if mode == "both":
        return ["baseline", "coached"]
    raise ValueError("evidence_prompt_mode must be baseline, coached, or both")


if __name__ == "__main__":
    raise SystemExit(main())

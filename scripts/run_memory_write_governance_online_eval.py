from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
import agent.provider as agent_provider
from memory2.eval_write_governance_online import (
    ScriptedWriteGovernanceOnlineProvider,
    WriteGovernanceOnlineReport,
    run_write_governance_online_eval,
    select_write_governance_online_candidates,
    write_write_governance_evidence_jsonl,
    write_write_governance_online_json,
    write_write_governance_online_markdown,
)


def build_provider_for_write_governance_online(
    args: argparse.Namespace,
) -> tuple[object | None, str | None]:
    if bool(args.fake_provider):
        return ScriptedWriteGovernanceOnlineProvider(), "fake-write-governance-model"
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


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument("--fake-provider", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--checkpoint-jsonl", default="")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if bool(args.fake_provider) and bool(args.enable_real_llm):
        parser.error("--fake-provider and --enable-real-llm cannot be used together")

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_write_governance_online_eval.json"
    md_path = out_dir / "memory_write_governance_online_eval.md"
    evidence_path = out_dir / "memory_write_governance_online_evidence.jsonl"

    provider, model = build_provider_for_write_governance_online(args)
    if provider is None or model is None:
        reason = "missing_api_key" if bool(args.enable_real_llm) else "real_llm_disabled"
        report = _gated_report(reason, real_llm_enabled=bool(args.enable_real_llm))
        write_write_governance_online_json(report, json_path)
        write_write_governance_online_markdown(report, md_path)
        write_write_governance_evidence_jsonl(report.evidence_records, evidence_path)
        print(json_path)
        print(md_path)
        print(evidence_path)
        return 1

    candidates = select_write_governance_online_candidates(
        case_set=str(args.case_set),
        limit=int(args.limit),
    )
    report = await run_write_governance_online_eval(
        candidates,
        Path(args.workspace),
        provider,
        model,
        timeout_s=float(args.timeout_s),
        real_llm_enabled=bool(args.enable_real_llm),
        checkpoint_jsonl=Path(args.checkpoint_jsonl)
        if args.checkpoint_jsonl
        else None,
        resume=bool(args.resume),
        concurrency=int(args.concurrency),
    )
    write_write_governance_online_json(report, json_path)
    write_write_governance_online_markdown(report, md_path)
    write_write_governance_evidence_jsonl(report.evidence_records, evidence_path)
    print(json_path)
    print(md_path)
    print(evidence_path)
    return 0 if report.infra_passed else 1


def _gated_report(
    reason: str,
    *,
    real_llm_enabled: bool,
) -> WriteGovernanceOnlineReport:
    return WriteGovernanceOnlineReport(
        run_id="write-governance-online-gated",
        generated_at="2026-07-21T00:00:00+00:00",
        results=(),
        evidence_records=(),
        metrics={
            "evaluation_level": "write_governance_online_shadow",
            "candidate_count": 0,
            "real_llm_enabled": bool(real_llm_enabled),
            "infra_passed": False,
            "gate_reason": reason,
            "provider_error_count": 0,
            "timeout_count": 0,
            "completed_call_count": 0,
            "skipped_from_checkpoint_count": 0,
            "concurrency": 0,
            "total_token_count": 0,
            "avg_latency_ms": 0.0,
            "evidence_record_count": 0,
        },
    )


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())

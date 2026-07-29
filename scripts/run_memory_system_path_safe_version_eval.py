from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.provider import LLMResponse
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_system_path_safe_version import (
    run_system_path_safe_version_cases,
    write_system_path_safe_version_json,
    write_system_path_safe_version_markdown,
)


class ScriptedSystemPathProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--config", default="")
    parser.add_argument("--case-pack", default="standard")
    parser.add_argument("--balanced-small", action="store_true")
    parser.add_argument("--common-limit", type=int, default=20)
    parser.add_argument("--hard-limit", type=int, default=20)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--modes", default="current,safe_version_shadow,safe_version_replace")
    parser.add_argument("--fake-provider", action="store_true")
    parser.add_argument("--enable-real-llm", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--real-memory-workspace", default="")
    args = parser.parse_args(argv)

    if not args.fake_provider and not args.enable_real_llm:
        args.fake_provider = True
    if args.enable_real_llm and not args.fake_provider:
        raise SystemExit("real LLM provider is not implemented for this eval runner yet")

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
    provider = ScriptedSystemPathProvider()
    report = asyncio.run(
        run_system_path_safe_version_cases(
            cases,
            Path(args.workspace),
            provider,
            modes=modes,
            model="scripted",
            timeout_s=args.timeout_s,
        )
    )
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

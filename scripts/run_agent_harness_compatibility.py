from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.agent_harness.legacy import load_source_registry
from eval.agent_harness.legacy import IntegrationStatus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 1B runner baseline")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("my_md/test_docs/eval_suite/phase-1b-compatibility-baseline.json"),
    )
    args = parser.parse_args(argv)
    records = load_source_registry(args.baseline)
    print(f"entries={len(records)}")
    print(
        "main_gate_allowed=" + str(sum(record.main_gate_allowed for record in records))
    )
    print("adapter_ready=" + str(sum(record.adapter_ready for record in records)))
    print(
        "main_gate_ready_count="
        + str(
            sum(
                record.adapter_ready
                and record.integration_status is IntegrationStatus.MAIN_GATE_READY
                and record.main_gate_allowed
                for record in records
            )
        )
    )
    print(
        "integration_statuses="
        + ",".join(sorted({record.integration_status.value for record in records}))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

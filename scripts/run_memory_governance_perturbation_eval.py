from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_memory_governance_dataset import (
    load_memory_governance_cases,
    memory_governance_case_to_json,
    validate_memory_governance_cases,
)
from memory2.eval_memory_perturbation import (
    build_full_schema_perturbed_cases,
    build_question_perturbations,
)


def main() -> int:
    dataset = Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
    out = Path(
        "my_md/memory_optimization/datasets/memory_governance_eval_80_perturbed.jsonl"
    )
    full_out = Path(
        "my_md/memory_optimization/datasets/"
        "memory_governance_eval_80_perturbed_full.jsonl"
    )
    cases = load_memory_governance_cases(dataset)
    rows = build_question_perturbations(cases)
    full_cases = build_full_schema_perturbed_cases(cases, rows)
    errors = validate_memory_governance_cases(full_cases)
    if errors:
        raise ValueError("full perturbed dataset validation failed: " + "; ".join(errors))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + "\n",
        encoding="utf-8",
    )
    full_out.write_text(
        "\n".join(
            json.dumps(
                memory_governance_case_to_json(case),
                ensure_ascii=False,
                sort_keys=True,
            )
            for case in full_cases
        )
        + "\n",
        encoding="utf-8",
    )
    print(out)
    print(full_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

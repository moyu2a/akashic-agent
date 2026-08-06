from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .protocol import EpisodeResult

_STATUS_MAP = {
    "pass": "PASS",
    "partial": "PARTIAL",
    "fail": "FAIL",
    "n/a": "SKIP",
}


@dataclass(frozen=True)
class DifferentialReport:
    compared_case_count: int
    missing_case_ids: tuple[str, ...]
    unexpected_case_ids: tuple[str, ...]
    status_mismatches: tuple[tuple[str, str, str], ...]

    @property
    def passed(self) -> bool:
        return not (
            self.missing_case_ids or self.unexpected_case_ids or self.status_mismatches
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "compared_case_count": self.compared_case_count,
            "missing_case_ids": list(self.missing_case_ids),
            "unexpected_case_ids": list(self.unexpected_case_ids),
            "status_mismatches": [list(item) for item in self.status_mismatches],
        }


def compare_case_reports(
    legacy_rows: Iterable[Mapping[str, object]],
    unified_results: Iterable[EpisodeResult],
) -> DifferentialReport:
    legacy_by_case = {
        str(row.get("case_id")): str(row.get("status", "")).strip().lower()
        for row in legacy_rows
        if row.get("case_id")
    }
    unified_by_case = {
        str(
            result.metrics.get("case_id") or _case_id_from_episode(result.episode_id)
        ): result
        for result in unified_results
    }
    missing = tuple(sorted(set(legacy_by_case) - set(unified_by_case)))
    unexpected = tuple(sorted(set(unified_by_case) - set(legacy_by_case)))
    mismatches: list[tuple[str, str, str]] = []
    for case_id in sorted(set(legacy_by_case) & set(unified_by_case)):
        expected = _STATUS_MAP.get(legacy_by_case[case_id], "ERROR")
        actual = unified_by_case[case_id].status
        if expected != actual:
            mismatches.append((case_id, legacy_by_case[case_id], actual))
    return DifferentialReport(
        compared_case_count=len(set(legacy_by_case) & set(unified_by_case)),
        missing_case_ids=missing,
        unexpected_case_ids=unexpected,
        status_mismatches=tuple(mismatches),
    )


def _case_id_from_episode(episode_id: str) -> str:
    return episode_id.rsplit("-r", 1)[0]

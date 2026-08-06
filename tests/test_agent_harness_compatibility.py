from __future__ import annotations

from eval.agent_harness.compatibility import (
    CompatibilityStatus,
    build_compatibility_report,
)


def test_compatibility_report_requires_explicit_adapter_status() -> None:
    report = build_compatibility_report(
        [
            {
                "component": "legacy_runner.py",
                "commit": "abc123",
                "status": "ADAPTER_REQUIRED",
                "reason": "runtime and report schema differ",
            }
        ]
    )

    assert report["entry_count"] == 1
    assert report["entries"][0]["status"] == CompatibilityStatus.ADAPTER_REQUIRED.value
    assert report["entries"][0]["reusable"] is False


def test_compatibility_report_rejects_unknown_status() -> None:
    try:
        build_compatibility_report(
            [
                {
                    "component": "runner.py",
                    "commit": "abc123",
                    "status": "UNKNOWN",
                    "reason": "not audited",
                }
            ]
        )
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("unknown compatibility status must be rejected")

"""Annotation pipeline stage status tracker.

Reads durable SlurmRunRecords from the runs directory and maps each of the
15 annotation pipeline stages to its current completion state.  No records
are modified.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flytetest.registry import get_pipeline_stages
from flytetest.spec_executor import (
    DEFAULT_SLURM_RUN_RECORD_FILENAME,
    SlurmRunRecord,
    load_slurm_run_record,
)

# Ordered list of (workflow_name, human-readable label) for the full 15-stage
# annotation pipeline.  Stage index in the returned StageStatus is 1-based.
# Derived from the registry so new pipeline stages self-register there.
ANNOTATION_PIPELINE_STAGES: list[tuple[str, str]] = get_pipeline_stages("annotation")

_FAILED_STATES = frozenset({"FAILED", "TIMEOUT", "OUT_OF_MEMORY", "CANCELLED"})
_RUNNING_STATES = frozenset({"RUNNING", "PENDING", "COMPLETING"})


@dataclass
class StageStatus:
    """Status of one annotation pipeline stage derived from durable run records."""

    stage_index: int
    workflow_name: str
    label: str
    status: str
    job_id: str | None
    run_record_path: str | None
    submitted_at: str | None
    final_state: str | None


def _effective_state(record: SlurmRunRecord) -> str:
    return (record.final_scheduler_state or record.scheduler_state or "").upper()


def _status_from_state(effective: str) -> str:
    if effective == "COMPLETED":
        return "COMPLETED"
    if effective in _FAILED_STATES:
        return "FAILED"
    if effective in _RUNNING_STATES:
        return "RUNNING"
    if effective:
        return "UNKNOWN"
    return "PENDING"


def _load_all_records(runs_dir: Path) -> list[SlurmRunRecord]:
    """Load all valid SlurmRunRecords from the runs directory."""
    records: list[SlurmRunRecord] = []
    if not runs_dir.is_dir():
        return records
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue
        record_path = entry / DEFAULT_SLURM_RUN_RECORD_FILENAME
        if not record_path.is_file():
            continue
        try:
            records.append(load_slurm_run_record(entry))
        except Exception:
            pass
    return records


def get_annotation_pipeline_status(runs_dir: Path) -> list[StageStatus]:
    """Return per-stage status for the 15-stage annotation pipeline.

    Reads durable SlurmRunRecords from *runs_dir* without modifying them.
    For each stage the most recent record (by submitted_at) is used.
    """
    all_records = _load_all_records(runs_dir)

    # Group by workflow name
    by_workflow: dict[str, list[SlurmRunRecord]] = {}
    for record in all_records:
        by_workflow.setdefault(record.workflow_name, []).append(record)

    result: list[StageStatus] = []
    for idx, (workflow_name, label) in enumerate(ANNOTATION_PIPELINE_STAGES, start=1):
        candidates = by_workflow.get(workflow_name, [])
        if not candidates:
            result.append(StageStatus(
                stage_index=idx,
                workflow_name=workflow_name,
                label=label,
                status="PENDING",
                job_id=None,
                run_record_path=None,
                submitted_at=None,
                final_state=None,
            ))
            continue

        # Pick most recent by submitted_at; fall back to run_id for stability
        best = max(
            candidates,
            key=lambda r: (
                "" if r.submitted_at == "not_recorded" else r.submitted_at,
                r.run_id,
            ),
        )
        effective = _effective_state(best)
        result.append(StageStatus(
            stage_index=idx,
            workflow_name=workflow_name,
            label=label,
            status=_status_from_state(effective),
            job_id=best.job_id or None,
            run_record_path=str(best.run_record_path),
            submitted_at=best.submitted_at if best.submitted_at != "not_recorded" else None,
            final_state=best.final_scheduler_state,
        ))

    return result


def get_pipeline_summary(stages: list[StageStatus]) -> dict[str, object]:
    """Summarise pipeline progress across all stage statuses."""
    total = len(stages)
    completed = sum(1 for s in stages if s.status == "COMPLETED")
    failed = sum(1 for s in stages if s.status == "FAILED")
    running = sum(1 for s in stages if s.status == "RUNNING")
    pending = sum(1 for s in stages if s.status == "PENDING")
    percent_complete = round(completed / total * 100) if total else 0
    next_pending = next((s.label for s in stages if s.status == "PENDING"), None)
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "running": running,
        "pending": pending,
        "percent_complete": percent_complete,
        "next_pending_stage": next_pending,
        "has_failures": failed > 0,
    }

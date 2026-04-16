# Milestone 21d: Pipeline Status Tracker

Date: 2026-04-15
Status: Ready to implement

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 21d

---

## Goal

Replace manual stage-by-stage progress checking in `docs/mcp_full_pipeline_prompt_tests.md`
with a `get_pipeline_status` MCP tool that reads durable `SlurmRunRecord` JSON
files from `.runtime/runs/` and returns a per-stage checklist for the 15-stage
annotation pipeline. No records are modified.

---

## Files

| File | Action |
|---|---|
| `src/flytetest/pipeline_tracker.py` | New — `ANNOTATION_PIPELINE_STAGES`, `StageStatus`, `get_annotation_pipeline_status`, `get_pipeline_summary` |
| `src/flytetest/mcp_contract.py` | Edit — add `GET_PIPELINE_STATUS_TOOL_NAME` + add to `MCP_TOOL_NAMES` |
| `src/flytetest/server.py` | Edit — add `_get_pipeline_status_impl`, `get_pipeline_status` public wrapper, register tool |
| `tests/test_pipeline_tracker.py` | New — 8 synthetic tests |
| `docs/mcp_full_pipeline_prompt_tests.md` | Edit — add Stage 0 status-check section |

---

## pipeline_tracker.py Design

### Stage list

All 15 constants sourced from `src/flytetest/config.py`.

```python
ANNOTATION_PIPELINE_STAGES: list[tuple[str, str]] = [
    (TRANSCRIPT_EVIDENCE_WORKFLOW_NAME, "Transcript evidence (Trinity/STAR/StringTie)"),
    (PASA_WORKFLOW_NAME,                "PASA transcript alignment"),
    (TRANSDECODER_WORKFLOW_NAME,        "TransDecoder coding region prediction"),
    (PROTEIN_EVIDENCE_WORKFLOW_NAME,    "Protein evidence alignment (Exonerate)"),
    (ANNOTATION_WORKFLOW_NAME,          "BRAKER3 ab initio annotation"),
    (CONSENSUS_PREP_WORKFLOW_NAME,      "EVM consensus prep (pre-EVM contract)"),
    (CONSENSUS_EVM_WORKFLOW_NAME,       "EVidenceModeler consensus annotation"),
    (PASA_UPDATE_WORKFLOW_NAME,         "PASA post-EVM annotation refinement"),
    (REPEAT_FILTER_WORKFLOW_NAME,       "RepeatMasker repeat filtering"),
    (FUNCTIONAL_QC_WORKFLOW_NAME,       "BUSCO quality assessment"),
    (EGGNOG_WORKFLOW_NAME,              "EggNOG functional annotation"),
    (AGAT_WORKFLOW_NAME,                "AGAT statistics"),
    (AGAT_CONVERSION_WORKFLOW_NAME,     "AGAT GFF3 conversion"),
    (AGAT_CLEANUP_WORKFLOW_NAME,        "AGAT GFF3 cleanup"),
    (TABLE2ASN_WORKFLOW_NAME,           "table2asn submission prep"),
]
```

### StageStatus dataclass

```python
@dataclass
class StageStatus:
    stage_index: int          # 1-based
    workflow_name: str
    label: str
    status: str               # COMPLETED | FAILED | RUNNING | PENDING | UNKNOWN
    job_id: str | None
    run_record_path: str | None
    submitted_at: str | None
    final_state: str | None
```

### get_annotation_pipeline_status(runs_dir: Path) -> list[StageStatus]

For each stage:
1. Scan `runs_dir` for all `*.json` files via `load_slurm_run_record`; skip
   unparseable files.
2. Among records matching `workflow_name`, pick the one with the most recent
   `submitted_at`.
3. Resolve status from `(record.final_scheduler_state or record.scheduler_state or "").upper()`:
   - `COMPLETED` → `"COMPLETED"`
   - `FAILED` / `TIMEOUT` / `OUT_OF_MEMORY` / `CANCELLED` → `"FAILED"`
   - `RUNNING` / `PENDING` / `COMPLETING` → `"RUNNING"`
   - non-empty but none of the above → `"UNKNOWN"`
   - no record found → `"PENDING"`

Keep `pipeline_tracker.py` self-contained — do not import from `server.py`.

### get_pipeline_summary(stages) -> dict

Returns:
```json
{
  "total": 15,
  "completed": 7,
  "failed": 1,
  "running": 1,
  "pending": 6,
  "percent_complete": 47,
  "next_pending_stage": "RepeatMasker repeat filtering",
  "has_failures": true
}
```

`percent_complete = round(completed / total * 100)`.
`next_pending_stage` = label of the first stage with `status == "PENDING"`, or `None`.

---

## mcp_contract.py

Add after `WAIT_FOR_SLURM_JOB_TOOL_NAME = "wait_for_slurm_job"`:
```python
GET_PIPELINE_STATUS_TOOL_NAME = "get_pipeline_status"
```

Append `GET_PIPELINE_STATUS_TOOL_NAME` to `MCP_TOOL_NAMES`.

---

## server.py

### Imports

```python
from flytetest.mcp_contract import (..., GET_PIPELINE_STATUS_TOOL_NAME)
from flytetest.pipeline_tracker import get_annotation_pipeline_status, get_pipeline_summary
```

### Impl (add near _list_slurm_run_history_impl)

```python
def _get_pipeline_status_impl(*, runs_dir: Path | None = None) -> dict[str, object]:
    history_root = runs_dir or DEFAULT_RUN_DIR
    stages = get_annotation_pipeline_status(history_root)
    summary = get_pipeline_summary(stages)
    return {
        "supported": True,
        "run_root": str(history_root),
        "summary": summary,
        "stages": [
            {
                "index": s.stage_index,
                "workflow_name": s.workflow_name,
                "label": s.label,
                "status": s.status,
                "job_id": s.job_id,
                "run_record_path": s.run_record_path,
                "submitted_at": s.submitted_at,
            }
            for s in stages
        ],
    }
```

### Public wrapper + registration

```python
def get_pipeline_status() -> dict[str, object]:
    """Return checklist status for all 15 annotation pipeline stages."""
    return _get_pipeline_status_impl()
```

Register in `create_mcp_server`:
```python
mcp.tool()(get_pipeline_status)
```

---

## Tests (tests/test_pipeline_tracker.py)

Use `save_slurm_run_record` + `replace(record, ...)` from `spec_executor.py`,
same pattern as `test_server.py` ~line 641. All tests use `tempfile.TemporaryDirectory`.

1. `test_all_pending_when_no_records` — empty dir → 15 stages, all PENDING
2. `test_completed_stage_detected` — record with `final_scheduler_state="COMPLETED"` → stage COMPLETED
3. `test_failed_stage_maps_correctly` — `final_scheduler_state="FAILED"` → FAILED
4. `test_timeout_maps_to_failed` — `final_scheduler_state="TIMEOUT"` → FAILED
5. `test_running_stage_detected` — `scheduler_state="RUNNING"`, no final → RUNNING
6. `test_most_recent_record_wins` — two records for same workflow, older FAILED newer COMPLETED → COMPLETED
7. `test_summary_counts_correct` — 3 COMPLETED, 1 FAILED, 1 RUNNING → counts + percent_complete
8. `test_next_pending_stage_label` — summary returns correct label for first PENDING stage

---

## mcp_full_pipeline_prompt_tests.md

Add **Stage 0: Check Pipeline Status** before Stage 1:

```markdown
## Stage 0: Check Pipeline Status

Use `get_pipeline_status` before submitting any stage to see what has already
completed. Call it again after each stage to confirm progress.

**MCP call:** `get_pipeline_status` (no arguments)

**Pass criteria:**
- Returns a `stages` list with 15 entries
- `summary.completed` reflects the number of COMPLETED stages
- `summary.next_pending_stage` names the next stage to submit
- `summary.has_failures` is `false` before proceeding to the next stage
```

Append to each existing stage's Pass Criteria:
> Re-run `get_pipeline_status` after this stage completes to confirm progress.

---

## Acceptance Criteria

- All new and existing tests pass; full suite stays green.
- `get_pipeline_status` in `list_entries()` tool list.
- Calling against empty runs dir returns 15 stages all PENDING.
- `CHANGELOG.md` updated with dated entry.
- `docs/realtime_refactor_checklist.md` M21d items marked `[x]`.

## Compatibility Risks

- `runs_dir` scan reads every `*.json` file in the directory, not just
  subdirectory records. Keep consistent with how `_list_slurm_run_history_impl`
  reads from subdirectory `DEFAULT_SLURM_RUN_RECORD_FILENAME` paths to avoid
  loading unrelated JSON files. Use the same subdirectory-walking approach.
- `pipeline_tracker.py` must not import from `server.py` to avoid circular
  imports.

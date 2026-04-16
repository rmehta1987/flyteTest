# Milestone 21: Ad Hoc Task Execution Surface

Date: 2026-04-10  
Revised: 2026-04-14  
Status: Ready to implement

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 21

Bundled items:
- TODO 16 — `list_available_bindings` MCP tool (binding discovery)
- TODO 12 — `get_run_summary` MCP tool (run dashboard)

---

## Current State

- `run_task()` in `server.py:916` is hardcoded to two tasks:
  `exonerate_align_chunk` and `busco_assess_proteins`.
- `SHOWCASE_TARGETS` in `mcp_contract.py:83` has 2 task entries and 7
  workflow entries. `SUPPORTED_TASK_NAMES` (derived from showcase) is never
  used by `run_task()` — the hardcoded set bypasses it.
- The registry has 15 `synthesis_eligible=True` workflow-level entries, but
  these require planner types (`ReferenceGenome`, `TranscriptEvidenceSet`,
  etc.) as inputs, not raw file paths — they are not suitable as ad hoc tasks.
- No binding discovery tool exists.
- No run dashboard exists. `list_slurm_run_history` is Slurm-only and
  chronological — not a state-grouped summary.

## Task Eligibility Policy

**Gate: explicit `ShowcaseTarget(category="task")` opt-in in `mcp_contract.py`.**

Do NOT auto-expose `synthesis_eligible` tasks — that flag controls workflow
composition, not the user-facing execution surface. A task is eligible for
ad hoc execution only if:
1. Its inputs are fully expressible as scalar values + `Path`-backed file shapes
   (`File`, `Dir`, `str`, `int`, `float`) — no prior workflow result bundle required.
2. Its output is a `Dir` or `File` that produces a `run_manifest.json`.
3. It has a clear biological or stage boundary that a user would meaningfully
   invoke in isolation.

### New tasks to add to `SHOWCASE_TARGETS`

| Task | Module | Inputs | Why eligible |
|---|---|---|---|
| `fastqc` | `flytetest.tasks.qc` | `left: File`, `right: File`, `fastqc_sif: str=""` | Simple FASTQ files, no prior run deps |
| `gffread_proteins` | `flytetest.tasks.filtering` | `gff3: File`, `genome: File`, + optional str scalars | GFF3 + genome FASTA only |

**Ineligible** (require prior workflow `Dir` outputs):
- `agat_cleanup_gff3` — needs `agat_conversion_results: Dir`
- `agat_convert_sp_gxf2gxf` — needs `eggnog_results: Dir`
- `agat_statistics` — needs `eggnog_results: Dir`
- All other tasks that consume a prior-run result directory

---

## Part 1 — Ad Hoc Task Surface (M21 core)

### Implementation steps

**`src/flytetest/mcp_contract.py`:**
1. Add two new `ShowcaseTarget(category="task")` entries for `fastqc` and
   `gffread_proteins`.
2. Update the `run_task` tool description to list all 4 supported task names.

**`src/flytetest/server.py` — `run_task()`:**
3. Replace `if task_name not in {SUPPORTED_TASK_NAME, BUSCO_FIXTURE_TASK_NAME}:`
   with `if task_name not in set(SUPPORTED_TASK_NAMES):`.
   (`SUPPORTED_TASK_NAMES` is already derived from `SHOWCASE_TARGETS` in
   `mcp_contract.py`.)
4. Add `parameters` blocks for `fastqc` and `gffread_proteins` following the
   existing BUSCO fixture pattern — `(name, required)` tuples. If 4+ tasks
   need per-task parameter blocks, refactor to a dispatch dict rather than a
   chain of `if task_name ==` branches.

### Test cases (4 new in `tests/test_server.py`)

| ID | Test name | What it checks |
|---|---|---|
| T1 | `test_run_task_declines_unknown_task_name` | unsupported name → `supported=False` |
| T2 | `test_run_task_declines_missing_required_inputs` | known task, required input absent → `supported=False` |
| T3 | `test_run_task_declines_unknown_input_keys` | known task, extra key → `supported=False` |
| T4 | `test_run_task_routes_all_supported_tasks_with_synthetic_handler` | for each name in `SUPPORTED_TASK_NAMES`, `run_task` reaches the handler |

---

## Part 2 — Binding Discovery (TODO 16)

### New MCP tool: `list_available_bindings`

**Signature:**
```python
def list_available_bindings(
    task_name: str,
    search_root: str | None = None,
) -> dict[str, object]:
```

**Behaviour:**
1. If `task_name not in SUPPORTED_TASK_NAMES` → `supported=False`.
2. Look up the task's parameter list from `mcp_contract.py` (each task in
   `SHOWCASE_TARGETS` with category="task" gets an explicit parameter list).
3. Scan `search_root` (default: `Path.cwd()`) recursively up to depth 3 for
   files/dirs matching per-parameter heuristics:

   | Pattern suffix | File extensions scanned |
   |---|---|
   | `*_fasta`, `*_fa`, `proteins_fasta`, `genome` (File) | `*.fasta`, `*.fa`, `*.fna`, `*.faa` |
   | `*_gff3`, `gff3` (File) | `*.gff3`, `*.gff` |
   | `*_bam` | `*.bam` |
   | `*_sif` | `*.sif` |
   | `left`, `right` (FASTq) | `*.fastq.gz`, `*.fq.gz`, `*.fastq`, `*.fq` |
   | `*_dir`, `*_results` (Dir) | subdirectories containing `run_manifest.json` |
   | scalar (`str` with default, `int`, `float`) | no scan — return hint string |

4. Return:
   ```json
   {
     "supported": true,
     "task_name": "busco_assess_proteins",
     "bindings": {
       "proteins_fasta": ["data/busco/test_data/eukaryota/genome.fna"],
       "lineage_dataset": "(scalar — provide a string value)",
       "busco_cpu": "(scalar — provide an integer, default: 8)",
       "busco_sif": [],
       "busco_mode": "(scalar — provide a string, default: prot)"
     },
     "limitations": ["Search depth capped at 3; pass search_root for a narrower scope."]
   }
   ```

**Constraints:**
- Cap recursive scan at depth 3 to avoid long waits on large filesystems.
- V1 is best-effort: document that coverage depends on parameter naming conventions.
- Implemented entirely in `server.py` + a new `_task_parameter_scan_patterns()`
  helper; no changes to `registry.py`.

### Test cases (3 new in `tests/test_server.py`)

| ID | Test name | What it checks |
|---|---|---|
| T5 | `test_list_available_bindings_declines_unknown_task` | unsupported task → `supported=False` |
| T6 | `test_list_available_bindings_finds_files_matching_fasta_pattern` | FASTA files in search_root are discovered |
| T7 | `test_list_available_bindings_returns_scalar_hints_for_non_path_params` | scalar params return hint string, not a file list |

---

## Part 3 — Run Dashboard (TODO 12)

### New MCP tool: `get_run_summary`

**Signature:**
```python
def get_run_summary(limit: int = 20) -> dict[str, object]:
```

**Behaviour:**
1. Scan `DEFAULT_RUN_DIR` (`.runtime/runs/`) for subdirectories containing
   `slurm_run_record.json` or `local_run_record.json`.
2. Sort by mtime descending; inspect at most `limit * 5` entries to bound
   scan cost on large installs.
3. For each record:
   - Slurm: read `effective_scheduler_state` (or `final_scheduler_state`).
   - Local: `completed_at is not None` → `COMPLETED`, else `IN_PROGRESS`.
4. Group by state; return the most recent `limit` entries in `recent`.
5. If `DEFAULT_RUN_DIR` does not exist → `supported=True`, empty results
   (not an error — fresh install).

**Return shape:**
```json
{
  "supported": true,
  "total_scanned": 12,
  "by_state": {"COMPLETED": 8, "FAILED": 2, "RUNNING": 1, "PENDING": 1},
  "recent": [
    {
      "kind": "slurm",
      "job_id": "1234567",
      "workflow_name": "annotation_qc_busco",
      "state": "COMPLETED",
      "created_at": "2026-04-14T10:00:00Z",
      "run_record_path": "..."
    }
  ],
  "limitations": []
}
```

**Offline-friendly:** reads persisted records only — no `squeue` calls.

**Implementation:** new `_get_run_summary_impl()` + `get_run_summary()` in
`server.py`, following the existing `_list_slurm_run_history_impl` pattern
(`server.py:204`). Reuses `load_slurm_run_record()` and `load_local_run_record()`.

### Test cases (3 new in `tests/test_server.py`)

| ID | Test name | What it checks |
|---|---|---|
| T8 | `test_get_run_summary_returns_empty_for_missing_run_dir` | no run dir → supported=True, empty |
| T9 | `test_get_run_summary_groups_slurm_records_by_state` | COMPLETED + FAILED records counted correctly |
| T10 | `test_get_run_summary_includes_local_run_records` | local records appear in recent list |

---

## Low-Hanging Fruit Bundled into M21

These Phase-1 quick-win TODOs are small enough to land in the same pass:

**TODO 15 — Actionable errors in `prepare_run_recipe`:**  
When planning returns no matching target, include the closest registered
workflow/task name in the limitation message. Implement in `server.py` or
`planning.py` via a `difflib.get_close_matches()` call against
`SUPPORTED_TARGET_NAMES`. No new tool needed.

**TODO 17 — Result inspection tool `inspect_run_result`:**  
New MCP tool: `inspect_run_result(run_record_path: str) → dict`.
Loads a `local_run_record.json` or `slurm_run_record.json`, returns a
human-readable summary: workflow name, node results, output paths, durable
index refs. Useful after a cluster job finishes without having to read raw JSON.

---

## Files Changed

| File | Change |
|---|---|
| `src/flytetest/mcp_contract.py` | Add `fastqc`, `gffread_proteins` `ShowcaseTarget` entries; update `run_task` description; add `list_available_bindings`, `get_run_summary`, `inspect_run_result` tool descriptions |
| `src/flytetest/server.py` | `run_task()` uses `SUPPORTED_TASK_NAMES`; add `list_available_bindings`, `get_run_summary`, `inspect_run_result` tools; actionable errors in `prepare_run_recipe` |
| `tests/test_server.py` | 10 new tests (T1–T10) + tests for TODO 15 and TODO 17 |
| `docs/realtime_refactor_checklist.md` | Add TODO 12 + TODO 16 items to M21 section; mark complete when done |
| `docs/mcp_showcase.md` | Document 3 new tools |
| `docs/capability_maturity.md` | Update ad hoc task, binding discovery, run dashboard rows |
| `CHANGELOG.md` | M21 entries |

---

## Validation

```bash
.venv/bin/python -m unittest tests.test_server -v   # 10+ new tests pass
.venv/bin/python -m unittest                        # full suite green (371 tests)
git diff --check
```

---

## Blockers and Constraints

1. **`gffread_proteins` signature audit**: Confirm exact parameter names and
   optionality from `src/flytetest/tasks/filtering.py:250` before writing the
   parameter block in `run_task()`.
2. **`fastqc` task environment**: `fastqc` in `tasks/qc.py` uses a Flyte task
   environment. Confirm whether direct Python call (outside Flyte) works the
   same way as `exonerate_align_chunk` and `busco_assess_proteins`.
3. **Scan depth for `list_available_bindings`**: Cap at depth 3; document that
   deep directory structures need an explicit `search_root`.
4. **`get_run_summary` mtime scan**: Cap at `limit * 5` dirs to bound cost.
5. **Do NOT auto-expose synthesis_eligible registry entries** — they require
   workflow planner types, not direct file paths.

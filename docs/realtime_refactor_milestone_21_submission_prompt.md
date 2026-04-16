Use this prompt when handing the Milestone 21 Ad Hoc Task Execution Surface slice
off to another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-10-milestone-21-ad-hoc-task-execution-surface.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

Context:

- This is Milestone 21. Milestones 20a and 20b must be merged before starting
  this work. Confirm the `## Milestone 20a` and `## Milestone 20b` sections in
  `docs/realtime_refactor_checklist.md` are both marked complete before proceeding.
- M20a/M20b own `SlurmRunRecord`, `LocalRunRecord`, `DurableAssetRef`, and the
  retry/monitor/resolver tools. Do not modify those.
- M21 owns `run_task()`, `list_available_bindings()`, `get_run_summary()`,
  `inspect_run_result()`, and the SHOWCASE_TARGETS opt-in gate.
- The design is already decided — read the plan doc in full before writing any
  code. Do not re-litigate the architecture.

Key decisions already made (do not re-litigate):

- Task eligibility is governed by explicit `ShowcaseTarget(category="task")`
  entries in `SHOWCASE_TARGETS` (`mcp_contract.py`). Do NOT auto-expose tasks
  based on `synthesis_eligible=True` — that flag controls workflow composition,
  not the user-facing execution surface.
- `SUPPORTED_TASK_NAMES` is already derived from `SHOWCASE_TARGETS` in
  `mcp_contract.py`. `run_task()` must use it instead of a hardcoded set.
- New eligible tasks: `fastqc` (module `flytetest.tasks.qc`) and
  `gffread_proteins` (module `flytetest.tasks.filtering`). Confirm exact
  parameter signatures in those modules before writing parameter blocks.
- `list_available_bindings` uses heuristic file extension matching per
  parameter name suffix (see the scan pattern table in the plan doc). Cap
  recursive scan at depth 3. V1 is best-effort.
- `get_run_summary` is offline — reads persisted run records only, no
  `squeue` calls. Groups by state, caps scan at `limit * 5` directories.
- `inspect_run_result` loads one run record and returns structured summary —
  no scheduler calls, no side effects.
- TODO 15 (actionable errors): use `difflib.get_close_matches()` against
  `SUPPORTED_TARGET_NAMES` in `prepare_run_recipe` / `plan_typed_request`.

Blocker to resolve before writing code:

- Audit `src/flytetest/tasks/filtering.py` around line 250 for exact parameter
  names and optionality of `gffread_proteins`. Record findings before writing
  the parameter block.
- Audit `src/flytetest/tasks/qc.py` for `fastqc` parameter names. Confirm
  whether it can be called outside a Flyte context the same way
  `busco_assess_proteins` is called in `run_task()`.

Task:

Phase 1 — Extend SHOWCASE_TARGETS and run_task() (no inter-phase deps):

1. In `src/flytetest/mcp_contract.py`:
   - Add two new `ShowcaseTarget(category="task")` entries: `fastqc` and
     `gffread_proteins`. Each needs `name`, `module_name`, `source_path`.
   - Update the `run_task` tool description to list all 4 supported task names.

2. In `src/flytetest/server.py` `run_task()`:
   - Replace the hardcoded `{SUPPORTED_TASK_NAME, BUSCO_FIXTURE_TASK_NAME}`
     guard with `if task_name not in set(SUPPORTED_TASK_NAMES):`.
   - Add `parameters` blocks for `fastqc` and `gffread_proteins` following the
     existing `busco_assess_proteins` pattern — list of `(name, required)` tuples.
   - If there are now 4+ tasks, refactor to a dispatch dict `TASK_PARAMETERS`
     keyed by task name rather than a chain of `if task_name ==` branches.

3. Add 4 tests to `tests/test_server.py`:
   - `test_run_task_declines_unknown_task_name` — unsupported name → `supported=False`
   - `test_run_task_declines_missing_required_inputs` — known task, required
     input absent → `supported=False`
   - `test_run_task_declines_unknown_input_keys` — known task, extra key →
     `supported=False`
   - `test_run_task_routes_all_supported_tasks_with_synthetic_handler` — for
     each name in `SUPPORTED_TASK_NAMES`, confirm `run_task` reaches the handler
     (inject a no-op handler, do not exercise actual task logic)

Phase 2 — list_available_bindings (depends on Phase 1):

4. In `src/flytetest/server.py`, add `_task_parameter_scan_patterns()` helper
   and `_list_available_bindings_impl()`. See the scan pattern table in the plan
   doc for the mapping from parameter name suffix → file extensions.
   Cap recursive scan at depth 3. Return the shape defined in the plan doc.

5. Expose `list_available_bindings(task_name, search_root=None)` as an MCP tool.
   Add tool description to `src/flytetest/mcp_contract.py`.

6. Add 3 tests to `tests/test_server.py`:
   - `test_list_available_bindings_declines_unknown_task` — unsupported task →
     `supported=False`
   - `test_list_available_bindings_finds_files_matching_fasta_pattern` — FASTA
     files planted under a temp search_root are returned for the matching param
   - `test_list_available_bindings_returns_scalar_hints_for_non_path_params` —
     scalar params return hint string, not a file list

Phase 3 — get_run_summary (no inter-phase deps):

7. In `src/flytetest/server.py`, add `_get_run_summary_impl(limit)` following
   the pattern of `_list_slurm_run_history_impl` (`server.py:204`):
   - Scan `DEFAULT_RUN_DIR` for subdirs containing `slurm_run_record.json` or
     `local_run_record.json`.
   - Sort by mtime descending. Inspect at most `limit * 5` entries.
   - For Slurm records: read `effective_scheduler_state` or
     `final_scheduler_state`. For local: `completed_at is not None` →
     COMPLETED, else IN_PROGRESS.
   - Group by state. Return the shape defined in the plan doc.
   - If `DEFAULT_RUN_DIR` does not exist → `supported=True`, empty results.

8. Expose `get_run_summary(limit=20)` as an MCP tool. Add tool description
   to `src/flytetest/mcp_contract.py`.

9. Add 3 tests to `tests/test_server.py`:
   - `test_get_run_summary_returns_empty_for_missing_run_dir` — no run dir →
     `supported=True`, `total_scanned=0`, empty `recent`
   - `test_get_run_summary_groups_slurm_records_by_state` — write synthetic
     slurm_run_record.json files under a temp dir, confirm state grouping
   - `test_get_run_summary_includes_local_run_records` — write a synthetic
     local_run_record.json, confirm it appears in `recent`

Phase 4 — Low-hanging fruit (no inter-phase deps):

10. TODO 15 — Actionable errors in `prepare_run_recipe` / `plan_typed_request`:
    When no matching target is found, add `difflib.get_close_matches(user_target,
    SUPPORTED_TARGET_NAMES, n=3, cutoff=0.6)` and include the closest name(s)
    in the limitation message. No new tool needed.

11. TODO 17 — `inspect_run_result(run_record_path: str) -> dict`:
    New MCP tool. Load the run record file (detect Slurm vs local by filename).
    Return structured summary: `workflow_name`, `run_id`, `state`, `node_results`
    (list with output paths), `durable_asset_index_path` if sidecar exists.
    No scheduler calls. Add tool description to `mcp_contract.py`.

Phase 5 — Docs:

12. Update `docs/realtime_refactor_checklist.md` — mark M21 items complete,
    including TODO 12 and TODO 16 sub-items.
13. Update `CHANGELOG.md` — add M21 entries under `## Unreleased`.
14. Update `docs/capability_maturity.md`:
    - "Ad hoc task execution" row: Close → Current
    - Add rows for binding discovery and run dashboard (both: Current)
15. Update `docs/mcp_showcase.md` — document `list_available_bindings`,
    `get_run_summary`, `inspect_run_result`.
16. Update `README.md` if any walkthrough references the old 2-task limit.

Important constraints:

- Do not expose tasks based on `synthesis_eligible` — only `SHOWCASE_TARGETS`
  opt-in entries are eligible.
- Do not add any scheduler calls (`squeue`, `sacct`, `scontrol`) inside
  `get_run_summary` or `inspect_run_result` — offline reads only.
- Do not break the existing `run_task` behavior for `exonerate_align_chunk`
  and `busco_assess_proteins`.
- Do not modify `LocalRunRecord`, `SlurmRunRecord`, `DurableAssetRef`, or
  any M20a/M20b artifact formats.
- Keep README, DESIGN, checklist docs, capability docs, MCP contract, and
  tests aligned.

Validation (run before declaring M21 complete):

1. `.venv/bin/python -m unittest tests.test_server -v`
   — T1–T10 and all pre-existing server tests pass (10+ new tests)
2. `.venv/bin/python -m unittest` — full suite passes (371+ tests)
3. `git diff --check` — no trailing whitespace

Report back with:

- checklist items completed
- files changed
- validation run output summary
- current checklist status
- remaining blockers or assumptions
```

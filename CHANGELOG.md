# Changelog

This file records milestone-level changes in FLyteTest so repo scope, MCP
surface changes, prompt-driven handoff work, and in-progress work notes are
easier to track over time.

Guidelines:

- add new entries at the top under `Unreleased` until a milestone is finalized
- describe what actually changed, not planned work
- keep scope boundaries honest, especially for deferred post-PASA stages
- link to prompt or checklist docs when they were part of the milestone handoff
- use strikethrough for milestone items that were later removed, renamed, or superseded during refactoring, and add a short note explaining what replaced them
- treat this file as the shared working memory for meaningful units of work;
  update it after each completed slice instead of waiting for a final wrap-up
- use dated checklist items or dated bullets for completed work so the timeline
  is obvious to later agents
- record what was tried, what worked, what failed, what remains blocked, and
  any dead ends that should not be retried without a new reason
- add newly discovered follow-up tasks while implementation is still in
  progress so they are not lost between sessions

Entry template:

```markdown
## Unreleased

### Milestone name or date

- [ ] short factual change
- [x] completed factual change (2026-04-11)
- [ ] blocked follow-up or discovered task
- [ ] failed approach to avoid retrying without a new reason
- ~~removed or superseded item~~
  - replaced by: short explanation
  - reason: refactor, scope correction, renamed contract, or other concise note
```

## Unreleased

### MCP Doc Cross-linking

- [x] 2026-04-13 linked the `Validated Slurm Walkthrough` in
  `docs/mcp_showcase.md` to `docs/mcp_cluster_prompt_tests.md` so the general
  MCP guide points to the detailed live-cluster prompt test script instead of
  repeating the acceptance scenarios inline

### Slurm Test Coverage Follow-Up

- [x] 2026-04-13 fixed pre-existing timing flake in `test_loop_survives_reconcile_error`
  (`tests/test_slurm_async_monitor.py`) — replaced real thread dispatch with
  `patch.object(anyio.to_thread, "run_sync", new=fake_run_sync)` so the test
  only waits on `anyio.sleep` between cycles; widened the window from 0.5s to
  1.0s as a safety margin
- [x] 2026-04-13 added `test_monitor_slurm_job_reports_completed_terminal_state`,
  `_failed_`, and `_timeout_` — verify `final_scheduler_state` is non-null for
  each terminal state; the COMPLETED/FAILED path also checks `stdout_path` and
  `stderr_path` are present so clients know where to retrieve diagnostic output
- [x] 2026-04-13 added `test_monitor_slurm_job_uses_sacct_when_squeue_is_empty`
  — simulates empty squeue + sacct hit to prove the normal job-completion
  transition (job aged off squeue) is handled; asserts `source == "sacct"`
- [x] 2026-04-13 added `test_retry_slurm_job_declines_timeout_failure` and
  `_declines_cancelled_record` — verify both terminal states decline without
  calling sbatch; TIMEOUT requires new `prepare_run_recipe` with updated walltime
- [x] 2026-04-13 added `test_retry_slurm_job_child_record_links_to_parent`
  — after a successful NODE_FAIL retry, loads the child run record and asserts
  `retry_parent_run_record_path` points to the original record
- [x] 2026-04-13 added `cancel_slurm_job` idempotency and scancel-failure tests
  — `test_cancel_slurm_job_is_idempotent` verifies scancel is called exactly
  once across two cancel requests; `test_cancel_slurm_job_persists_cancellation_when_scancel_fails`
  verifies `cancellation_requested_at` is written to the run record even when
  scancel returns non-zero
- [x] 2026-04-13 updated `SlurmWorkflowSpecExecutor.cancel()` in
  `spec_executor.py` to support both behaviors: added early-return idempotency
  guard when `cancellation_requested_at` is already set; moved
  `save_slurm_run_record` before the `returncode != 0` check so the durable
  cancellation intent is always persisted regardless of scheduler response
- [x] 2026-04-13 added `test_cancel_then_monitor_shows_cancelled_state`
  — full cancel → CANCELLED monitor cycle; verifies `final_scheduler_state`
  is set after a reconcile that reports CANCELLED from the scheduler
- [x] 2026-04-13 added `test_run_slurm_recipe_saves_script_with_correct_directives`
  — reads the saved sbatch script and asserts `#SBATCH` directives match the
  frozen `resource_request` (`--cpus-per-task`, `--mem`, `--partition`,
  `--account`, `--time`)
- [x] 2026-04-13 added `test_run_slurm_recipe_script_path_points_to_existing_file`
  — verifies the `script_path` field in the durable run record points to a
  file that actually exists on disk after submission
- [x] 2026-04-13 added `slurm_resource_hints` to `_entry_payload()` in
  `server.py`; added `test_list_entries_exposes_slurm_resource_hints_for_slurm_capable_workflows`
  — verifies `cpu`, `memory`, and `walltime` are present and `queue`/`account`
  are absent for the BUSCO workflow entry
- [x] 2026-04-13 added `resume_from_local_record` parameter to
  `_run_slurm_recipe_impl()` in `server.py` and threaded it through to
  `.submit()`; added `test_run_slurm_recipe_carries_forward_local_resume_node_state`
  — builds a prior `LocalRunRecord`, submits with it, and asserts
  `local_resume_node_state` is populated in the `SlurmRunRecord`
- [x] 2026-04-13 added `test_monitor_slurm_job_rejects_unknown_schema_version`
  — overwrites a run record with an unrecognised `schema_version`, calls
  monitor, and asserts a human-readable schema/version message appears in
  `limitations` rather than a cryptic `KeyError`
- [x] 2026-04-13 added `test_run_slurm_recipe_twice_produces_independent_run_records`
  — submits the same artifact twice and asserts the two run records have
  different `run_id` values and different on-disk paths
- [x] 2026-04-13 full suite: 335 tests pass, 1 live-Slurm smoke skipped

### MCP Prompt-Level Integration Tests

- [x] 2026-04-13 created `tests/test_mcp_prompt_flows.py` — 5 multi-turn Slurm
  lifecycle flows exercised through the MCP tool surface (`create_mcp_server()`
  → `server.tools["tool_name"](keyword_args)`), mirroring the exact JSON-RPC
  call path a Claude client takes; Slurm subprocess layer replaced by
  in-process fakes so tests run offline without real cluster access
- [x] 2026-04-13 `test_mcp_prepare_submit_and_poll_until_completed` — full
  prepare → submit → monitor(RUNNING) → monitor(COMPLETED) flow; validates the
  `final_scheduler_state` polling gate: first call returns `None` (client must
  keep polling), second returns `"COMPLETED"` (client stops)
- [x] 2026-04-13 `test_mcp_failed_job_is_retried_to_completed` — prepare →
  submit → monitor(NODE_FAIL) → retry_slurm_job → monitor(COMPLETED) flow;
  verifies `retry_run_record_path` is a different path from the parent and
  the child lifecycle reaches COMPLETED independently
- [x] 2026-04-13 `test_mcp_duplicate_cancel_does_not_issue_second_scancel` —
  prepare → submit → cancel × 2; verifies second cancel returns `supported=True`
  without issuing a second `scancel` to the scheduler
- [x] 2026-04-13 `test_mcp_prepare_with_resource_request_dict_uses_slurm_profile`
  — verifies that passing `resource_request` as a dict with
  `execution_profile="slurm"` freezes the slurm profile into the recipe
  binding plan so `run_slurm_recipe` can proceed without re-planning
- [x] 2026-04-13 `test_mcp_list_slurm_run_history_returns_submitted_job` —
  verifies that after prepare + submit, the job appears in
  `list_slurm_run_history` with the correct `workflow_name` and `job_id`; this
  is the client path for resuming monitoring after a restart
- [x] 2026-04-13 full suite: 340 tests pass, 1 live-Slurm smoke skipped

### Registry Slurm Resource Hints

- [x] 2026-04-13 added `_WORKFLOW_SLURM_RESOURCE_HINTS` dict to
  `src/flytetest/registry.py` with advisory `cpu`, `memory`, and `walltime`
  starting-point values for all 16 Slurm-capable workflows; `queue` and
  `account` are deliberately absent — they are site-specific and must always
  come from the user
- [x] 2026-04-13 updated `_with_resource_defaults()` to attach hints under
  `execution_defaults["slurm_resource_hints"]` alongside the existing
  `execution_defaults["resources"]` (local) table; updated the function
  docstring to describe both tables and their precedence rules
- [x] 2026-04-13 added rule to `AGENTS.md` Section 7: when the user does not
  specify Slurm resources, read `slurm_resource_hints` from the target
  workflow's registry entry and surface them to the user before freezing;
  queue and account must always come from the user
- [x] 2026-04-13 updated `docs/capability_maturity.md` Resource-aware
  execution planning row to name both `execution_defaults["resources"]`
  (local cpu/memory/execution_class) and `execution_defaults["slurm_resource_hints"]`
  (Slurm cpu/memory/walltime) and their advisory role
- [x] 2026-04-13 updated `docs/mcp_showcase.md` `resource_request` description
  to direct clients toward `list_entries` →
  `compatibility.execution_defaults.slurm_resource_hints` as the starting-point
  source before freezing a recipe

### MCP Showcase Slurm Lifecycle Documentation

- [x] 2026-04-13 restructured "Validated Slurm Walkthrough" in
  `docs/mcp_showcase.md` into six named phases: Prepare, Submit, Monitor, On
  Completion, On Failure, Cancel; each phase is self-contained so users can
  navigate to the step they need
- [x] 2026-04-13 added scheduler state reference table covering `PENDING`,
  `RUNNING`, `COMPLETED`, `FAILED`, `TIMEOUT`, `OUT_OF_MEMORY`, `CANCELLED`
  with meaning and next-action guidance; `TIMEOUT` and `OUT_OF_MEMORY` are
  documented as terminal states that require a new `prepare_run_recipe` call
  with updated `resource_request` rather than `retry_slurm_job`
- [x] 2026-04-13 added "Slurm Prerequisites" section before the walkthrough
  explaining the 2FA constraint, authenticated HPC login session requirement,
  and required commands on `PATH`; cross-referenced from Common Failure Modes
  (moved from buried in failure modes to a dedicated callout)
- [x] 2026-04-13 added `resource_request` JSON schema example in the Recipe
  Flow section with all five fields (`cpu`, `memory`, `queue`, `account`,
  `walltime`); noted that these fields can also be embedded in the prompt text
  for MCP clients that drop optional tool arguments
- [x] 2026-04-13 added Phase 4 (On Completion) happy-path example showing a
  `COMPLETED` terminal state; `final_scheduler_state` being non-null is
  documented as the polling gate for MCP clients
- [x] 2026-04-13 added Phase 5 (On Failure) decision tree: `retry_slurm_job`
  for retryable failures (`NODE_FAIL`, transient errors) versus new
  `prepare_run_recipe` with updated `resource_request` for resource-exhaustion
  terminal states
- [x] 2026-04-13 added `.runtime/runs/<run_id>/` sbatch script callout in the
  `run_slurm_recipe` description so users know the script can be inspected
  before or after submission to verify directives
- [x] 2026-04-13 updated `retry_slurm_job` tools one-liner to state it
  resubmits the original frozen recipe unchanged; resource changes require a
  new `prepare_run_recipe` call
- [x] 2026-04-13 updated `AGENTS.md` Sections 3 and 7 to replace stale Flyte
  Slurm plugin language with the authenticated-session `sbatch` model; added
  explicit note that 2FA prevents SSH key pairing
- [x] 2026-04-13 updated `DESIGN.md` Section 4.5 to replace non-existent
  `SlurmExecutionProfile` / `sbatch_conf_for_recipe` API pseudo-code with the
  actual four-phase recipe workflow (`prepare_run_recipe` → `run_slurm_recipe`
  → `monitor_slurm_job` → `retry_slurm_job`)
- [x] 2026-04-13 added "## Slurm Execution" section to
  `docs/tutorial_context.md` covering the 2FA constraint, frozen resource
  settings, `TIMEOUT`/`OUT_OF_MEMORY` terminal classification, and BUSCO
  fixture as the canonical smoke-test reference

### Documentation Style Guide and Context Cleanup

- [x] 2026-04-13 rewrote `## Inline Comments` section of `.codex/comments.md`
  with four concrete code examples (annotation comment blocks, biological
  context, guard/constraint explanations); replaced abstract guidance with
  patterns that can be applied directly to source files
- [x] 2026-04-13 updated `.codex/comments.md` Function Docstrings section to
  name `slurm_poll_loop` in `src/flytetest/slurm_monitor.py` as the canonical
  depth standard for all project docstrings
- [x] 2026-04-13 updated `.codex/documentation.md` to add the `slurm_poll_loop`
  depth-target paragraph at the top of Code Documentation Expectations, and
  added a `named sub-sections` bullet (Error handling:, Output contract:,
  Retry logic:) to the Args/Returns guidance
- [x] 2026-04-13 added rule to both `.codex/comments.md` and
  `.codex/documentation.md`: Args and Returns explanations must go beyond the
  type hint to give the biological or engineering reason for each parameter,
  not just restate the type
- [x] 2026-04-13 created `.claudeignore` to exclude
  `Genomic Studies Platform Summary.md` from Claude Code context without
  removing it from the repository
- [x] 2026-04-13 archived 24 milestone submission prompt and plan files from
  `docs/realtime_refactor_plans/` into `docs/realtime_refactor_plans/archive/`;
  covered M12–M18 submission prompts, MCP spec cutover, recipe binding plans,
  and bulk milestone prompts; active M19 phase prompts remain in place
- [x] 2026-04-13 moved misplaced `src/flytetest/improve_dataclass_serializatoin.md`
  (typo in name, wrong directory) into a clean gated plan at
  `docs/realtime_refactor_plans/2026-04-13-dataclass-serialization-consolidation.md`;
  added matching checklist section to `docs/realtime_refactor_checklist.md`;
  gate: after M19 Phases C and D complete; key constraint: no `slots=True`
  (breaks Flyte's `dataclasses.asdict()`)

### Milestone 18 RCC Slurm Smoke

- [x] 2026-04-13 fixed M18 BUSCO image path freezing for cluster runs:
  `m18_prepare_slurm_recipe.py` now resolves a repo-relative `BUSCO_SIF` to an
  absolute path before saving the Slurm recipe, preventing Apptainer from
  resolving `data/images/...` relative to the BUSCO task scratch directory
- [x] 2026-04-13 validated the M18 RCC Slurm smoke from an authenticated
  cluster session: recipe submission, monitoring, synthetic retry-seed
  creation, retry-child submission, and retry-child monitoring all worked; the
  retry child is considered complete when its run record reconciles to
  `COMPLETED` with scheduler exit code `0:0` and `attempt_number` 2
- [x] 2026-04-13 updated `scripts/rcc/README.md` and `README.md` to document
  the M18 BUSCO image path behavior, retry-child success criteria, and current
  Slurm retry support status
- [x] 2026-04-13 added MCP recipe planning support for the M18 BUSCO eukaryota
  fixture: `prepare_run_recipe` can now freeze `busco_assess_proteins` as a
  registered-task Slurm recipe with the fixture FASTA, `auto-lineage`, genome
  mode, `busco_cpu`, and optional `busco_sif` runtime bindings; updated the
  MCP docs with a client prompt for Codex/OpenCode-style testing
- [x] 2026-04-13 extended `list_entries` / `flytetest://supported-targets`
  payloads with `supported_execution_profiles` and `default_execution_profile`
  so clients can ask which runnable targets are Slurm-capable before calling
  `prepare_run_recipe`

### Milestone 19 HPC Cluster Validation Helpers

- [x] 2026-04-13 threaded `resume_from_local_record` into compute-node Slurm
  execution: `_run_local_recipe_impl()` now accepts an optional prior local
  run-record path, and generated Slurm scripts call that helper with the
  frozen local-resume record when one was provided at submission time, so the
  local-to-Slurm resume path now affects actual job execution instead of only
  durable submission metadata
- [x] 2026-04-13 added RCC-first Milestone 19 cluster-validation helpers under
  `scripts/rcc/` for two scenarios: approval-gated composed recipe submission
  (`run_m19_approval_gate_smoke.sh`) and local-to-Slurm resume reuse
  (`run_m19_resume_slurm_smoke.sh`); added generic monitor/cancel Python
  helpers plus scenario-specific monitor/cancel wrappers and documented the new
  pointer files in `scripts/rcc/README.md`
- [x] 2026-04-13 kept the approval-gate smoke honest in the docs and helper
  output: it proves rejection before approval and accepted Slurm submission
  after approval, but does not claim end-to-end success for the current
  generated repeat-filter plus BUSCO workflow on the local handler surface
- [x] 2026-04-13 validated the Milestone 19 approval-gate smoke on RCC:
  unapproved composed-recipe submission was blocked with "No approval record
  found for this composed recipe.", the approved resubmission was accepted by
  Slurm, and downstream composed execution later reconciled to `FAILED` with
  exit code `1:0` as expected under the smoke's documented runtime
  limitations
- [x] 2026-04-13 validated the Milestone 19 local-to-Slurm resume smoke on
  RCC: the resume helper submitted a BUSCO recipe with a matching prior local
  run record, and the monitored Slurm run reconciled to `COMPLETED` with
  scheduler exit code `0:0`, confirming that compute-node execution honored
  `resume_from_local_record` instead of only persisting the resume metadata in
  the durable submission record
- [x] 2026-04-13 validated the first real workflow Milestone 19 Slurm probe on
  RCC with the protein-evidence lifecycle wrappers: the submit helper froze a
  durable recipe artifact and Slurm run record, and the monitor helper later
  reconciled the job to `COMPLETED` with scheduler exit code `0:0`, closing
  the RCC-side real-workflow validation gate for Milestone 19
- [x] 2026-04-13 added passive RCC poll-loop watcher helpers
  `watch_slurm_run_record.py` and `watch_slurm_run_record.sh`; they reload the
  durable JSON record directly at a fixed interval and print only the
  background-reconciliation evidence fields, so RCC sessions can prove that
  the MCP server's `slurm_poll_loop()` updated the record without using
  `monitor_slurm_job`
- [x] 2026-04-13 moved the generic latest-run pointer behavior into the shared
  `run_slurm_recipe` server path: every successful Slurm submission now
  refreshes `.runtime/runs/latest_slurm_run_record.txt` and
  `.runtime/runs/latest_slurm_artifact.txt`, so back-to-back direct MCP
  submissions no longer depend on workflow-specific RCC wrapper pointers

### MCP Slurm Run History

- [x] 2026-04-13 added `list_slurm_run_history` to the MCP surface; it reads
  durable `.runtime/runs/` records only, returns recent accepted Slurm
  submissions newest first, includes the generic latest pointer targets, and
  does not require live scheduler access
- [x] 2026-04-13 added focused server tests for the new history tool: one
  covers recent-run ordering plus latest-pointer reporting, and one covers the
  empty-run-root case
- [x] 2026-04-13 extended `list_slurm_run_history` with exact
  `workflow_name`, `active_only`, and `terminal_only` filters plus
  `matched_count` reporting; conflicting active-versus-terminal requests now
  fail fast with an explicit limitation message

### Documentation Sweep Planning

- [x] 2026-04-12 moved the documentation sweep notes into
  `docs/realtime_refactor_plans/2026-04-12-documentation-sweep-plan.md`;
  renamed the misspelled scratch file into a durable plan and split the sweep
  into review-sized batches with per-batch validation rules
- [x] 2026-04-13 refreshed Batch 0 inventory in the documentation sweep plan:
  re-ran the helper-boilerplate searches, rechecked `spec_executor.py` for
  LocalNodeExecutionRequest-style copy-paste docstrings, verified no remaining
  module-docstring indentation issues in `src/` or `tests/`, and kept the pass
  documentation-only
- [x] 2026-04-13 completed documentation sweep Batches 1 and 2 in
  `src/flytetest/spec_executor.py`: replaced the copied
  LocalNodeExecutionRequest-style class/dataclass docstrings, removed generic
  helper Args/Returns boilerplate, and validated with `python3 -m compileall`,
  `.venv/bin/python -m pytest tests/test_spec_executor.py`, targeted `rg`
  checks, and `git diff --check -- src/flytetest/spec_executor.py`; the bare
  `python` command is not available in this shell
- [x] 2026-04-13 completed documentation sweep Batch 3 across shared
  infrastructure modules: cleaned planner, manifest, MCP contract, config,
  GFF3, asset, spec, artifact, and server helper docstrings without changing
  production behavior; worker validations covered `python3 -m compileall`,
  targeted `tests/test_specs.py`, `tests/test_planning.py`,
  `tests/test_server.py`, small manifest/config/GFF3/server test selections,
  targeted boilerplate `rg` checks, and path-scoped `git diff --check`
- [x] 2026-04-13 completed documentation sweep Batches 4, 5, and 6 across the
  biological task/workflow families: PASA, consensus, repeat filtering,
  protein evidence, transcript evidence, TransDecoder, AGAT, EggNOG,
  annotation, functional annotation, and RNA-seq QC/quant docstrings now
  describe the existing stage boundaries instead of helper boilerplate; worker
  validations passed per-family `python3 -m compileall`, targeted PASA,
  consensus/filtering, protein-evidence, transcript/TransDecoder, and
  downstream annotation tests, targeted `rg` checks, and path-scoped
  `git diff --check`
- [x] 2026-04-13 completed documentation sweep Batch 7 test cleanup: removed
  boilerplate test helper docstrings and trimmed nested test-double docstrings
  across server, spec executor, biological stage, planning/spec, and Flyte stub
  tests while leaving assertions and fixture behavior unchanged; worker
  validations passed compileall, the touched test-file pytest targets,
  targeted `rg` checks, and path-scoped `git diff --check`
- [x] 2026-04-13 completed documentation sweep Batch 8 shell comment audit in
  `scripts/rcc/`: added missing file-level purpose comments to RCC smoke,
  fixture, image, Slurm, and wrapper scripts without changing commands, flags,
  variables, or control flow; validation passed `bash -n` for changed shell
  entrypoints, `git diff --check -- scripts/rcc`, and a comment-only diff
  inspection
- [x] 2026-04-13 completed documentation sweep Batch 9 final validation:
  repo-wide boilerplate `rg` checks are clean, `spec_executor.py` has only the
  allowed `LocalNodeExecutionRequest` occurrence of the copied phrase, the
  module-docstring indentation scan found no first-docstring indentation
  issues, `python3 -m compileall src tests` passed, `git diff --check` passed,
  and the consolidated touched-file pytest target passed with 179 tests; the
  full suite still has one persistent failure in untouched
  `tests/test_slurm_async_monitor.py::TestSlurmPollLoop::test_loop_survives_reconcile_error`
  where the async retry loop only records one call inside the test timeout

### Milestone 19 Phase D: Deterministic Cache-Key Normalization

- [x] 2026-04-12 added `HANDLER_SCHEMA_VERSION = "1"` constant in
  `spec_executor.py`; included in every cache key so bumping the version
  invalidates all prior records when handler output shapes change
- [x] 2026-04-12 added `cache_identity_key()` pure function that computes a
  stable SHA-256 hex digest (16-char prefix) from frozen `WorkflowSpec`,
  `BindingPlan`, resolved planner inputs, and handler schema version; path
  normalization strips repo-root prefix and converts to POSIX separators
- [x] 2026-04-12 added `cache_identity_key: str | None` optional field to
  both `LocalRunRecord` and `SlurmRunRecord`; persisted in the durable JSON
  record and survives save/load round-trips
- [x] 2026-04-12 extended `_validate_resume_identity()` with an optional
  `current_cache_key` parameter; the cache key comparison is the authoritative
  content-level gate for resume acceptance (workflow name and artifact path
  remain as fast pre-filters)
- [x] 2026-04-12 wired `cache_identity_key` computation into
  `LocalWorkflowSpecExecutor.execute()` and
  `SlurmWorkflowSpecExecutor._submit_saved_artifact()`; the key is computed
  from frozen dicts and persisted in every new run record
- [x] 2026-04-12 added 12 Phase D tests in `CacheIdentityKeyTests`:
  determinism, node change, runtime binding change, resource spec change,
  runtime image change, repo-root normalization, handler version invalidation,
  cache key match/mismatch resume, LocalRunRecord/SlurmRunRecord round-trip,
  and executor integration
- [x] 2026-04-12 marked the Phase A cache-key checklist item as complete;
  resolved the cache-key normalization and cache invalidation open blockers

### Milestone 19 Core Phase B: Local Resume Semantics

- [x] 2026-04-12 added `resume_from: Path | None` parameter to
  `LocalWorkflowSpecExecutor.execute()`; when provided, the prior
  `LocalRunRecord` is loaded, identity-validated (workflow name + artifact
  path), and used to skip nodes whose `node_completion_state` entry is `True`
- [x] 2026-04-12 added `node_skip_reasons: dict[str, str]` field to
  `LocalRunRecord`; each skipped node gets a human-readable reason referencing
  the prior run ID and completion status
- [x] 2026-04-12 added `_validate_resume_identity()` helper that rejects
  resume when workflow name or artifact path differs between prior record and
  current artifact; returns a structured mismatch description
- [x] 2026-04-12 added 6 Phase B tests to `LocalResumeTests` in
  `tests/test_spec_executor.py`: full-skip resume, skip-reason recording,
  workflow-name mismatch rejection, artifact-path mismatch rejection,
  partial-completion re-execution, and `node_skip_reasons` round-trip

### Milestone 19 Core Phase C: Slurm Parity And Safe Composed Execution

Design decision — resume alignment between `LocalRunRecord` and `SlurmRunRecord`:

The two record types remain separate dataclasses.  Alignment is achieved by:
(a) `SlurmWorkflowSpecExecutor.submit()` accepts an optional
`resume_from_local_record: Path | None`; when provided and identity-matched,
completed nodes from the local record are recorded as pre-done in the new
`SlurmRunRecord` via a `local_resume_node_state` dict.
(b) The Slurm submission script can use the pre-done node list to skip
already-completed stages.
(c) Both paths use the same `_validate_resume_identity()` helper for identity
checking.
(d) Approval state lives in a companion `RecipeApprovalRecord(SpecSerializable)`
alongside the saved artifact, not inside the artifact itself, so approval is
explicit, durable, and independently inspectable.

- [x] 2026-04-12 added `local_resume_node_state: dict[str, bool]` and
  `local_resume_run_id: str | None` fields to `SlurmRunRecord`; these carry
  forward completed node state from a prior local run without merging the two
  record types
- [x] 2026-04-12 added `resume_from_local_record: Path | None` parameter to
  `SlurmWorkflowSpecExecutor.submit()` and `_submit_saved_artifact()`; when
  identity-matched, prior local completion state is recorded in the new
  `SlurmRunRecord` and noted in assumptions
- [x] 2026-04-12 introduced `RecipeApprovalRecord(SpecSerializable)` in
  `spec_artifacts.py` with `RECIPE_APPROVAL_SCHEMA_VERSION = "recipe-approval-v1"`;
  includes `save_recipe_approval()`, `load_recipe_approval()`, and
  `check_recipe_approval()` helpers using atomic temp-file writes
- [x] 2026-04-12 added `approve_composed_recipe` MCP tool in `server.py` that
  writes a durable approval record alongside the artifact; added
  `APPROVE_COMPOSED_RECIPE_TOOL_NAME` to `MCP_TOOL_NAMES` in `mcp_contract.py`
- [x] 2026-04-12 `run_local_recipe` and `run_slurm_recipe` now check
  `check_recipe_approval()` before executing `generated_workflow` artifacts;
  unapproved composed recipes are blocked with a clear limitation message
- [x] 2026-04-12 added 3 Slurm resume tests in `SlurmResumeFromLocalRecordTests`
  (pre-completed state, identity mismatch rejection, round-trip) and 10
  approval tests in `tests/test_recipe_approval.py` (record round-trip, schema
  validation, missing/approved/rejected/expired checks, MCP tool, run_local gate)
- [x] 2026-04-12 full suite: 297 tests pass (284 pre-Phase C + 13 new), 1
  live-Slurm smoke skipped

### Milestone 19 Part B: Async Slurm Monitoring

- [x] 2026-04-12 created `src/flytetest/slurm_monitor.py` as the standalone
  async monitoring module — contains `SlurmPollingConfig`, batched Slurm
  parsing helpers, file-locking helpers, `reconcile_active_slurm_jobs()`, and
  the `slurm_poll_loop()` async entry point
- [x] 2026-04-12 implemented `batch_query_slurm_job_states()` that issues a
  single `squeue --format="%i %T"` call and a single `sacct
  --format=JobID,State,ExitCode` call per poll cycle for all active job IDs,
  replacing the per-job query loop that M16 relied on
- [x] 2026-04-12 added `_parse_batch_squeue_output()` and
  `_parse_batch_sacct_output()` to handle multi-job scheduler output; sacct
  parser prefers bare-JobID rows over step rows (e.g. `123.batch`)
- [x] 2026-04-12 introduced `fcntl.flock`-based exclusive locks on a companion
  `.lock` file alongside each `slurm_run_record.json`; both the async updater
  and synchronous MCP handlers can coexist safely via `save_slurm_run_record_locked()`
  and `load_slurm_run_record_locked()`
- [x] 2026-04-12 implemented `discover_active_slurm_run_dirs()` to scan
  `.runtime/runs/` for non-terminal, non-cancelled Slurm run records before
  each poll cycle, avoiding unnecessary scheduler queries for completed jobs
- [x] 2026-04-12 attached `slurm_poll_loop` to the MCP server event loop in
  `_run_stdio_server_async()` via `anyio.create_task_group()`; the poll task
  is cancelled cleanly when the server's stdio transport closes
- [x] 2026-04-12 configured `SlurmPollingConfig` with defaults: 30-second
  poll interval, 300-second backoff cap, factor-of-2 exponential backoff,
  30-second per-command timeout; a single `sacct` timeout causes backoff only,
  not a server crash
- [x] 2026-04-12 added `tests/test_slurm_async_monitor.py` covering batch
  squeue/sacct parsing, mocked batch queries (including squeue timeout and
  failure), run-directory discovery across mixed states, full reconcile
  end-to-end, locked round-trips, lock-file creation, and async loop lifecycle
- [x] 2026-04-12 updated `docs/capability_maturity.md` to mark async Slurm
  monitoring as `Current`; module is observational only — does not alter
  submission, retry, or cancellation semantics
- [x] 2026-04-12 marked all Milestone 19 Part B checklist items complete in
  `docs/realtime_refactor_checklist.md`

### Planning assessment refresh

- [x] 2026-04-13 added `synchronous-twirling-panda-assessment.md` with a
  current-state agree / disagree critique of `synchronous-twirling-panda.md`,
  reflecting that the Slurm design update is complete and Milestone 19 Phase A
  has landed while Phase B/C resume and cache-key work remain open

### Milestone 19 Core Phase A: Durable Local Run Records

- [x] 2026-04-12 introduced `LocalRunRecord(SpecSerializable)` in
  `src/flytetest/spec_executor.py` — the first durable local run-record shape
  for saved-spec execution; stage completion state is no longer in-memory only
- [x] 2026-04-12 added schema version constant `LOCAL_RUN_RECORD_SCHEMA_VERSION
  = "local-run-record-v1"` and `DEFAULT_LOCAL_RUN_RECORD_FILENAME =
  "local_run_record.json"`; schema version is validated on deserialize and
  rejected when mismatched so stale records cannot silently produce wrong data
- [x] 2026-04-12 persists per-node completion state (`node_completion_state`
  dict keyed by node name), output references (`node_results`, `final_outputs`),
  timestamps (`created_at`, `completed_at`), resolved planner inputs, and
  assumptions; all fields round-trip exactly via `SpecSerializable`
- [x] 2026-04-12 added `save_local_run_record()` + `load_local_run_record()`
  helpers in `spec_executor.py`, following the same atomic temp-file pattern
  as the Slurm helpers from M16/18
- [x] 2026-04-12 extended `LocalWorkflowSpecExecutor.__init__` with optional
  `run_root: Path | None = None`; writes a durable record after every
  successful run when set; no record written when `None` (backward compat)
- [x] 2026-04-12 made `LocalNodeExecutionResult` extend `SpecSerializable`
  (changed `manifest_paths` annotation to `dict[str, Path]` for full round-trip
  fidelity); no behavioral change to existing callers
- [x] 2026-04-12 added 4 Phase A tests to `tests/test_spec_executor.py`:
  round-trip, schema-version validation, executor-persistence integration, and
  backward-compat with no `run_root`
- [x] 2026-04-12 full suite: 241 tests pass (237 pre-existing + 4 new), 0
  failures, 1 live-Slurm smoke skipped
- [ ] Phase B (resume semantics) — completed under Phase C session
- [ ] Phase C (cache keys + Slurm parity) — completed: Slurm resume alignment,
  approval gate, and composed-recipe execution gating landed

### Design alignment for scheduler-backed execution

- [x] 2026-04-12 updated `DESIGN.md` to replace the Flyte Slurm plugin model
  with the supported authenticated-session `sbatch` topology
- [x] 2026-04-12 aligned the Slurm execution, MCP tool, and test guidance in
  `DESIGN.md` with the already-implemented scheduler-bound execution path
- [x] 2026-04-12 normalized the Milestone 16 authenticated-Slurm handoff note
  so older Flyte Slurm plugin language is clearly historical

### Validation sweep after Milestone 15 review

- [x] 2026-04-11 fixed the `prepare_evm_transcript_inputs` signature typo so
  the pre-EVM consensus workflow and tests consistently use `pasa_results`
- [x] 2026-04-11 verified full local unittest discovery after the Milestone 15
  review fixes: 237 tests passing, 1 live Slurm smoke skipped because `sbatch`
  is required

### Milestone 15 Phase 2: Planning Integration & Approval Gating

- [x] 2026-04-11 extended `_planning_goal_for_typed_request()` to try
  registry-constrained composition fallback when hardcoded patterns don't match
- [x] 2026-04-11 integrated composition algorithm into planning layer via
  `_try_composition_fallback()` function that queries synthesis-eligible stages
  and attempts path discovery for common output types
- [x] 2026-04-11 added `requires_user_approval` flag to `plan_typed_request()`
  response so composed workflows are explicitly marked as needing approval
- [x] 2026-04-11 implemented approval gating in `_prepare_run_recipe_impl()`
  to prevent artifact save when composition requires approval
- [x] 2026-04-11 fixed `_workflow_spec_for_typed_goal()` to support
  arbitrary multi-stage workflow specs (not just hardcoded 2-entry repeat+BUSCO)
- [x] 2026-04-11 created `tests/test_planning_composition.py` with focused
  integration tests for composition fallback and approval gating
- [x] 2026-04-11 updated README.md with Workflow Composition section
  explaining discovery, approval requirements, and bounding parameters
- [x] 2026-04-11 updated docs/capability_maturity.md marking Registry-driven
  composition as "Current" instead of "Close", added M15 Phase 2 to Near-Term
  Priorities
- [x] 2026-04-11 fixed a regression where unrelated prompts and known day-one
  missing-input declines could fall through to registry-composition candidates
- [x] 2026-04-11 verified the focused composition/planning coverage after adding
  regression tests for fallback intent gating
- [x] 2026-04-11 backward compatible: hardcoded patterns checked before
  composition fallback, existing requests behave identically

### Milestone 16 Slurm lifecycle observability

- [x] 2026-04-11 added durable Slurm run-record loading and reconciliation
  through `squeue`, `scontrol show job`, and `sacct`
- [x] 2026-04-11 added explicit `monitor_slurm_job` and `cancel_slurm_job`
  MCP operations for submitted jobs
- [x] 2026-04-11 added terminal-state recording for stdout, stderr, exit code,
  and cancellation details in the durable run record
- [x] 2026-04-11 added focused tests for reconciliation, cancellation, and
  stale-record handling
- [x] 2026-04-11 changed the Slurm execution boundary so it now tracks job
  lifecycle state explicitly instead of treating submission as the end of the
  scheduler contract

### Protein-evidence Slurm smoke

- [x] 2026-04-11 added RCC wrapper scripts for submitting, monitoring, and
  cancelling the protein-evidence Slurm recipe from frozen run records
- [x] 2026-04-11 added a validated protein-evidence Slurm path that freezes
  the recipe, submits it, and persists the latest run-record and artifact
  pointers under `.runtime/runs/`
- [x] 2026-04-11 added supporting smoke and debug helpers for the
  protein-evidence HPC workflow
- [x] 2026-04-11 changed the protein-evidence stage so it now has an explicit
  HPC validation path in addition to the local fixture and workflow tests

### Tool reference normalization

- [x] 2026-04-11 normalized `docs/tool_refs/` so every tool reference now
  includes `Input Data`, `Output Data`, and `Code Reference` sections
- [x] 2026-04-11 added code back-links from the tool refs to the relevant task
  and workflow modules, including the deferred `table2asn` boundary
- [x] 2026-04-11 updated `docs/tool_refs/README.md` and
  `docs/tool_refs/stage_index.md` so the stage index and tool-reference
  guidance reflect the implemented workflow surface more honestly
- [x] 2026-04-11 refreshed stale stage notes in the BRaker3, PASA, EVM,
  TransDecoder, Trinity, BUSCO, EggNOG, AGAT, Exonerate, Salmon, FastQC, and
  repeat-filtering references to match the current code paths

### Authenticated Slurm access boundary

- [x] 2026-04-11 changed `run_slurm_recipe`, `monitor_slurm_job`, and
  `cancel_slurm_job` so they now report explicit unsupported-environment
  limitations when FLyteTest is running outside an already-authenticated
  scheduler-capable environment
- [x] 2026-04-11 changed Slurm lifecycle diagnostics so they distinguish
  missing CLI commands and scheduler reachability issues from ordinary
  lifecycle state
- [x] 2026-04-11 updated README, MCP showcase docs, capability notes, and the
  Milestone 16 Part 2 handoff docs so they describe the supported Slurm
  topology as a local MCP/server process running inside an authenticated HPC
  session
- [x] 2026-04-11 updated README and MCP showcase docs with Codex CLI and
  OpenCode client setup examples plus the validated prompt sequence for
  prepare, submit, monitor, and cancel on the protein-evidence Slurm path

### TaskEnvironment catalog refactor

- [x] 2026-04-11 centralized shared Flyte `TaskEnvironment` defaults in
  `src/flytetest/config.py`
- [x] 2026-04-11 introduced a declarative task-environment catalog plus
  compatibility aliases for current task families
- [x] 2026-04-11 added explicit per-family runtime overrides for BRAKER3
  annotation and BUSCO QC so the catalog reflects real workload differences
- [x] 2026-04-11 added focused tests for the shared defaults and alias
  stability
- [x] 2026-04-11 reduced repetition in the task-environment setup so future
  task families can inherit shared runtime policy from one place

### Local recipe execution robustness

- [x] 2026-04-11 changed collection-shaped workflow inputs such as
  `protein_fastas: list[File]` so they now bypass the local `flyte run
  --local` wrapper in MCP/server execution and use direct Python workflow
  invocation instead
- [x] 2026-04-11 avoided the current Flyte 2.1.2 CLI serialization gap where
  collection inputs are parsed as JSON but nested `File` / `Dir` values are
  not rehydrated for workflow execution

### AGAT post-processing milestone

- [x] 2026-04-11 implemented the AGAT statistics slice as `agat_statistics`
  plus the `annotation_postprocess_agat` workflow wrapper
- [x] 2026-04-11 implemented the AGAT conversion slice as
  `agat_convert_sp_gxf2gxf` plus the `annotation_postprocess_agat_conversion`
  workflow wrapper
- [x] 2026-04-11 implemented the AGAT cleanup slice as `agat_cleanup_gff3`
  plus the `annotation_postprocess_agat_cleanup` workflow wrapper
- [x] 2026-04-11 added synthetic AGAT coverage in `tests/test_agat.py`
- [x] 2026-04-11 updated the AGAT tool reference, stage index, capability
  snapshot, registry, compatibility exports, and prompt handoff docs to
  reflect the new post-EggNOG boundary
- [x] 2026-04-11 advanced the implemented biological scope from EggNOG
  functional annotation into the AGAT post-processing slices on the
  EggNOG-annotated and AGAT-converted GFF3 bundles
- [ ] deferred: `table2asn` remains a downstream stage outside these slices

### EggNOG functional annotation milestone

- [x] 2026-04-11 implemented the `annotation_functional_eggnog` workflow for
  the post-BUSCO functional-annotation milestone
- [x] 2026-04-11 added the EggNOG task family: `eggnog_map` and
  `collect_eggnog_results`
- [x] 2026-04-11 added synthetic EggNOG coverage in `tests/test_eggnog.py`
- [x] 2026-04-11 updated the EggNOG tool reference, stage index, capability
  matrix, tutorial context, and milestone checklist to track the new boundary
- [x] 2026-04-11 advanced the implemented biological scope from BUSCO-based
  annotation QC into EggNOG functional annotation while keeping AGAT and
  `table2asn` deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README
  milestone tables, planning adapters, and prompt handoff docs to expose the
  new boundary explicitly
- [ ] deferred: AGAT and `table2asn` remain downstream stages outside this
  milestone

### BUSCO annotation QC milestone

- [x] 2026-04-11 implemented the `annotation_qc_busco` workflow for post-
  repeat-filtering annotation QC
- [x] 2026-04-11 added the BUSCO task family: `busco_assess_proteins` and
  `collect_busco_results`
- [x] 2026-04-11 added synthetic BUSCO coverage in `tests/test_functional.py`
- [x] 2026-04-11 added a BUSCO milestone handoff prompt in
  `docs/busco_submission_prompt.md`
- [x] 2026-04-11 advanced the implemented biological scope from repeat-
  filtered GFF3/protein collection through BUSCO-based annotation QC while
  keeping EggNOG, AGAT, and submission-prep deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README
  milestone tables, stage index, and BUSCO tool reference to expose the new
  QC boundary explicitly
- [x] 2026-04-11 validated the BUSCO workflow with a real repo-local Apptainer
  runtime and explicit `_odb12` lineage datasets, and updated BUSCO docs to
  reflect the tested `flyte run` CLI surface and runtime paths
- [ ] deferred: EggNOG, AGAT, and `table2asn` remain downstream stages outside
  this milestone

### Repeat filtering and cleanup milestone

- [x] 2026-04-11 implemented the post-PASA `annotation_repeat_filtering`
  workflow for RepeatMasker conversion, gffread protein extraction,
  funannotate overlap filtering, repeat blasting, deterministic removal
  transforms, and final repeat-free GFF3/protein FASTA collection
- [x] 2026-04-11 added the repeat-filtering task family:
  `repeatmasker_out_to_bed`, `gffread_proteins`, `funannotate_remove_bad_models`,
  `remove_overlap_repeat_models`, `funannotate_repeat_blast`,
  `remove_repeat_blast_hits`, and `collect_repeat_filter_results`
- [x] 2026-04-11 added synthetic repeat-filtering tests plus local
  RepeatMasker fixture-path coverage in `tests/test_repeat_filtering.py`
- [x] 2026-04-11 advanced the implemented biological scope from PASA post-EVM
  refinement through repeat filtering and cleanup while keeping the later
  functional and submission stages deferred
- [x] 2026-04-11 updated the registry, compatibility exports, README milestone
  tables, tutorial context, and tool references to expose the repeat-
  filtering boundary explicitly
- [x] 2026-04-11 implemented `trinity_denovo_assemble`, updated
  `transcript_evidence_generation` to collect both Trinity branches, and
  removed PASA's external de novo Trinity FASTA requirement in favor of the
  transcript-evidence bundle
- [ ] deferred: BUSCO, EggNOG, AGAT, and `table2asn` remain downstream stages
  outside this milestone

### Documentation and planning

- [x] 2026-04-11 clarified the active milestone, stop rule, and stage-by-stage
  notes alignment in `README.md`
- [x] 2026-04-11 added tutorial-backed prompt-planning context in
  `docs/tutorial_context.md`
- [x] 2026-04-11 added stage-oriented tool-reference landing pages and prompt
  starters under `docs/tool_refs/`
- [x] 2026-04-11 added refactor milestone tracking and handoff materials in
  `docs/refactor_completion_checklist.md` and
  `docs/refactor_submission_prompt.md`

### Codebase structure and workflow coverage

- [x] 2026-04-11 split the repo into a package layout under `src/flytetest/`
  with separate task, workflow, type, registry, planning, and server modules
- [x] 2026-04-11 implemented deterministic workflow coverage through PASA
  post-EVM refinement while keeping repeat filtering, BUSCO, EggNOG, AGAT,
  and `table2asn` deferred
- [x] 2026-04-11 preserved the notes-faithful pre-EVM filename contract for
  `transcripts.gff3`, `predictions.gff3`, and `proteins.gff3`

### MCP showcase

- [x] 2026-04-11 added a narrow FastMCP stdio server in
  `src/flytetest/server.py`
- [x] 2026-04-11 limited the runnable MCP showcase to workflow
  `ab_initio_annotation_braker3` and task `exonerate_align_chunk`
- [x] 2026-04-11 added prompt planning in `src/flytetest/planning.py` for
  explicit local-path extraction and hard downstream-stage declines
- [x] 2026-04-11 added small read-only MCP resources for scope discovery:
  `flytetest://scope`, `flytetest://supported-targets`, and
  `flytetest://example-prompts`
- [x] 2026-04-11 added a compact additive `result_summary` block to
  `prompt_and_run` responses for success, decline, and failure cases

### Validation and fixtures

- [x] 2026-04-11 added synthetic MCP server coverage in `tests/test_server.py`
- [x] 2026-04-11 staged lightweight tutorial-derived local fixture files under
  `data/` for bounded smoke testing

## Prompt Tracking

Current prompt/handoff docs already in the repo:

- `docs/refactor_submission_prompt.md`
- `docs/tutorial_context.md`
- `docs/tool_refs/stage_index.md`

Future improvement idea:

- [ ] add a small prompt archive directory for accepted milestone prompts
  once the current MCP contract stabilizes
- [ ] add an environment preflight layer that checks for the active
  interpreter, `mcp`, `flyte`, and other required tools instead of assuming
  they are already available

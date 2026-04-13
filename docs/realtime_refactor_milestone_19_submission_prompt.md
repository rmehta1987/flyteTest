Use this prompt when handing the Milestone 19 Core Phase B (local resume
semantics) off to another Codex session or when starting the next
implementation pass.

Phase A (durable local run records) is complete as of 2026-04-12.
This prompt targets Phase B only.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the
rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-19-caching-resumability.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-12-milestone-19-phase-a-audit.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

If you were assigned a specialist role, also read the matching guide under
`.codex/agent/`.

Context — what Phase A landed (2026-04-12, 241 tests passing):

- `LocalRunRecord(SpecSerializable)` dataclass exists in
  `src/flytetest/spec_executor.py`. It captures schema version, run ID,
  workflow name, artifact path, run record path, timestamps, execution
  profile, resolved planner inputs, binding plan target, per-node completion
  state (`node_completion_state: dict[str, bool]`), node results, final
  outputs, and assumptions.
- `save_local_run_record()` and `load_local_run_record()` helpers use the same
  atomic temp-file pattern as the Slurm M16/18 helpers.
- `LocalWorkflowSpecExecutor.__init__` accepts an optional
  `run_root: Path | None = None`; when set, a durable record is written after
  every fully-successful run. When `None` (the default), behaviour is
  unchanged for existing callers.
- Schema version `"local-run-record-v1"` is validated on load; a mismatched
  version raises `ValueError`.
- `LocalNodeExecutionResult` now extends `SpecSerializable`.
- 4 Phase A tests in `tests/test_spec_executor.py` cover round-trip, schema
  validation, executor integration, and backward compatibility.

What Phase B must add:

- Resume-from-record for local saved-spec execution.
- The executor should accept an optional prior run-record path. When supplied,
  it must load the record, validate that the frozen recipe identity and
  resolved inputs match the current call, skip nodes whose
  `node_completion_state` entry is `True`, and rerun only the remaining nodes.
- Record the reason each node was reused or rerun in the updated run record.
- The prior record is the only authority for which nodes to skip; do not infer
  skip decisions from filesystem state alone.
- Write an updated record after the resumed run completes.

Task:

1. Read the Phase A audit document at
   `docs/realtime_refactor_plans/2026-04-12-milestone-19-phase-a-audit.md`
   to understand the current record shape and the chosen design decisions.
2. Inspect the current `LocalWorkflowSpecExecutor.execute()` implementation
   and the `LocalRunRecord` dataclass in `spec_executor.py`.
3. Decide the minimal identity check required to validate that a prior record
   is safe to reuse (workflow name + artifact path are the strict minimum;
   document any assumptions).
4. Add an optional `resume_from: Path | None = None` parameter to `execute()`
   (or equivalent) that, when supplied, loads the prior record, validates
   identity, and skips completed nodes.
5. Extend `LocalRunRecord` with a `node_skip_reasons: dict[str, str]` field
   (or equivalent) only if it does not break the existing round-trip tests.
   If it would break them, update the tests first and verify they still pass
   before continuing.
6. Add focused tests for: clean resume from a completed record, partial-run
   resume (some nodes done, some not), identity-mismatch rejection, and a
   fully-interrupted run that restarts from an empty completion state.
7. Update the checklist items under Milestone 19 Core Phase B.
8. Update CHANGELOG.md with a dated entry for Phase B.
9. Stop when blocked, when a compatibility guardrail would be at risk, or when
   the next step would require a larger risky batch that should be split.

Important constraints:

- Resume only from the frozen recipe and the recorded bindings in the prior
  `LocalRunRecord`; do not re-resolve planner inputs from scratch on resume.
- Keep skip decisions explicit and recorded in the updated run record.
- Do not implement cache-key derivation or Slurm parity in this phase
  (those belong to Phase C).
- Do not attempt approval-gating for composed recipes in this phase.
- Keep README, DESIGN, checklist docs, and tests aligned with every behavioral
  change.

Report back with:

- checklist item(s) completed
- files changed
- validation run (test count before and after)
- current checklist status for Milestone 19
- remaining blockers or assumptions
```

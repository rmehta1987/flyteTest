Use this prompt when handing the Milestone 19 Core Phase C (Slurm parity,
approval-gating, and safe composed execution) off to another session or when
starting the next implementation pass.

Phase A (durable local run records) is complete as of 2026-04-12.
Phase B (local resume semantics) must be complete before Phase C begins.
Milestone 19 Part B (async Slurm monitoring) is complete as of 2026-04-12.

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

Context — what has already landed before Phase C starts:

Phase A (2026-04-12, 241 tests passing):
- `LocalRunRecord(SpecSerializable)` dataclass in `src/flytetest/spec_executor.py`
  captures schema version, run ID, workflow name, artifact path, run record
  path, timestamps, execution profile, resolved planner inputs, binding plan
  target, per-node completion state (`node_completion_state: dict[str, bool]`),
  node results, final outputs, and assumptions.
- `save_local_run_record()` and `load_local_run_record()` helpers use atomic
  temp-file writes.
- `LocalWorkflowSpecExecutor` accepts an optional `run_root: Path | None`.
- Schema version `"local-run-record-v1"` validated on load.

Phase B (must land before Phase C — confirm it is complete by checking the
checklist before continuing):
- `LocalWorkflowSpecExecutor.execute()` accepts an optional
  `resume_from: Path | None` parameter.
- Prior record is loaded, identity-validated (workflow name + artifact path at
  minimum), and used to skip nodes whose `node_completion_state` entry is
  `True`.
- Skip reasons are recorded in the updated run record (`node_skip_reasons` or
  equivalent).
- Tests confirm: clean resume from full completion, partial resume, identity-
  mismatch rejection, and interrupted-run restart.

Part B async monitoring (2026-04-12, 279 tests passing):
- `src/flytetest/slurm_monitor.py` provides a background asyncio/anyio poll
  loop that batches Slurm status queries and updates durable run records
  without blocking the MCP server.
- File locking via `fcntl.flock` companion `.lock` files guards concurrent
  writes between the async updater and synchronous MCP handlers.
- `save_slurm_run_record_locked()` / `load_slurm_run_record_locked()` are
  available alongside the existing unlocked helpers.
- The poll loop is started in `_run_stdio_server_async()` via an anyio task
  group and cancelled cleanly on server shutdown.

What Phase C must add:

1. Align the local run-record resume model with the Slurm run-record layer so
   both execution paths honour the same explicit replay and resume rules.

2. Extend resumability to Slurm-backed execution: when a Slurm job is
   resubmitted from a prior run record, the retry logic should recognise which
   workflow nodes were already completed (via a prior durable local run record
   if it exists) before submitting only the incomplete stages.

3. Add an explicit approval-acceptance path for composed recipes before
   enabling execution-capable composed DAGs:
   - Approval state must be recorded durably in the saved recipe artifact or
     in a companion approval record alongside it.
   - The MCP server must not execute a composed recipe whose approval record is
     absent or expired.
   - Approval should be a separate MCP action that a human client can invoke
     explicitly; it must not be auto-granted by the planner.

4. Add tests covering:
   - Resume behavior across both local and Slurm execution paths.
   - Guardrails that prevent stale or mismatched reuse when the frozen spec or
     resolved inputs differ between the prior record and the current call.
   - Composed-recipe approval-acceptance flow (grant, execute, reject, expired).
   - A composed recipe that cannot execute without explicit approval.

Task:

1. Read the checklist under `## Milestone 19` and confirm that Phase B is
   complete before writing any Phase C code. If Phase B is not complete, stop
   and report the blocker.
2. Audit `src/flytetest/spec_executor.py` for the `SlurmWorkflowSpecExecutor`
   class and the `SlurmRunRecord` shape; understand how the existing Slurm
   submission, reconciliation, retry, and cancellation paths work before
   touching them.
3. Read `src/flytetest/spec_artifacts.py` and `src/flytetest/specs.py` to
   understand the saved-artifact and `BindingPlan` shapes before deciding where
   approval state should live.
4. Read `src/flytetest/composition.py` to understand the composition approval-
   gate that Milestone 15 added; Phase C should build on that boundary rather
   than bypass it.
5. Design the smallest alignment between `LocalRunRecord` and `SlurmRunRecord`
   that lets both paths honour resume semantics without merging the two
   dataclasses. Document the design decision in CHANGELOG.md before
   implementing.
6. Add a `resume_from_local_record` parameter or equivalent to the Slurm
   submission path. When a prior `LocalRunRecord` is provided and its identity
   matches the current artifact, treat completed nodes as pre-done and record
   that handoff explicitly in the new `SlurmRunRecord`.
7. Add approval state to the saved recipe artifact or a companion record.
   Use the existing `SpecSerializable` round-trip pattern. Do not invent a new
   serialization layer.
8. Add an `approve_composed_recipe` MCP tool (or equivalent) in `server.py`
   that writes the approval record. Update `MCP_TOOL_NAMES` and
   `mcp_contract.py`. The execution tools must check for valid approval before
   running a composed recipe.
9. Update the checklist items under `Milestone 19 Core Phase C`.
10. Update `README.md`, `docs/capability_maturity.md`, and `CHANGELOG.md` to
    reflect the landed behavior.
11. Stop when blocked, when a compatibility guardrail would be at risk, or when
    the next step would trigger a larger risky batch that should be split.

Important constraints:

- Do not merge `LocalRunRecord` and `SlurmRunRecord` into one type; keep the
  two durable record shapes separate and aligned rather than unified.
- Do not re-resolve planner inputs from scratch on Slurm resume; the frozen
  record and artifact are the only authority.
- Approval state must be explicit, durable, and inspectable; auto-granting from
  the planner is not acceptable.
- Keep Milestones 13, 16, 18, and Part B Slurm semantics intact; do not weaken
  the durable run-record boundary, submission contract, or the async monitoring
  loop.
- Keep the MCP tool contract stable; adding a new tool is fine but do not
  rename or remove existing tool names before a deliberate migration lands.
- Update docs, manifests, and tests that describe any changed behavior.

Report back with:

- checklist item(s) completed
- files changed
- validation run (test count before and after; all pre-existing tests must
  still pass)
- current checklist status for Milestone 19
- remaining blockers or assumptions
```

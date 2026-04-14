Use this prompt when handing the Milestone 20b Storage-Native Durable Asset
Return slice off to another Codex session or when starting the next
implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-20b-storage-native-durable-asset-return.md
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

Context:

- This is Milestone 20b. Milestone 20a (HPC Failure Recovery) must be merged
  before starting this work. Confirm the `## Milestone 20a` section in
  `docs/realtime_refactor_checklist.md` is marked complete before proceeding.
- M20b and M20a touch different sections of `spec_executor.py`:
  - M20a owns `SlurmWorkflowSpecExecutor.retry()`, `render_slurm_script()`,
    `SlurmRunRecord`, and the server retry/monitor tools.
  - M20b owns `LocalWorkflowSpecExecutor.execute()`, manifest writing,
    `run_manifest.json`, `resolver.py`, `spec_artifacts.py`, and
    `types/assets.py`.
  - If a merge conflict arises in `spec_executor.py`, the conflict surface is
    `_submit_saved_artifact()` return type and manifest writing — resolve
    carefully and do not silently revert M20a changes.
- The repo already produces deterministic local result bundles and manifests
  with stable filesystem paths.
- There is no content-addressed object store or metadata-indexed asset layer
  yet. Historical manifests point at filesystem paths; any durable reference
  model must be additive.
- Keep the first version filesystem-backed and manifest-driven. Do not
  introduce a database-first architecture.

Task:

1. Read `docs/realtime_refactor_plans/2026-04-08-milestone-20b-storage-native-durable-asset-return.md`
   in full.
2. Audit the current implementation state in `src/flytetest/resolver.py`,
   `src/flytetest/spec_executor.py`, `src/flytetest/spec_artifacts.py`,
   `src/flytetest/types/assets.py`, and the manifest-loading tests to identify
   the smallest durable asset surface.
3. Define a durable asset reference model for outputs. The model should be a
   stable dataclass or typed dict that can live alongside current path-based
   fields in manifests without removing them.
4. Update manifest writing so durable references are captured without removing
   legacy path-based compatibility. Use an additive field, not a replacement.
5. Make outputs reloadable after the local run directory is gone. Prefer a
   resolution strategy that checks the durable reference first and falls back
   to the path field with an explicit warning rather than silently inventing a
   path.
6. Add tests for asset lookup, replay, and downstream reuse. Tests must be
   offline-friendly (no real tool runs, no Slurm).
7. Update docs and the checklist so the new state is honest and reviewable:
   - `docs/realtime_refactor_checklist.md` — mark M20b items complete
   - `CHANGELOG.md` — add M20b entries under `## Unreleased`
   - `docs/capability_maturity.md` — update durable asset / result-reload row
   - `README.md` — update if replay examples reference fragile local paths
8. If you materially revise the detailed milestone plan, save the revision
   under `docs/realtime_refactor_plans/` and archive superseded versions under
   `docs/realtime_refactor_plans/archive/`.
9. Stop when blocked, when a compatibility guardrail would be at risk, or when
   the next step would require a larger risky batch that should be split.

Important constraints:

- Stay manifest-driven and filesystem-backed in the first version.
- Do not break current result-bundle replay.
- Do not introduce a database-first architecture.
- Do not revert or conflict with M20a changes in `SlurmRunRecord`,
  `render_slurm_script()`, `retry()`, or `_submit_saved_artifact()`.
- If a durable reference cannot be resolved, report that explicitly rather than
  inventing a fallback path.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior,
  MCP contract, and tests aligned.

Validation (run before declaring M20b complete):

1. `python3 -m unittest tests.test_resolver tests.test_spec_executor tests.test_planning -v`
   — all existing and new tests pass
2. `python3 -m unittest` — full suite passes (M20a tests must still pass)
3. `git diff --check` — no trailing whitespace

Report back with:

- checklist items completed
- files changed
- validation run output summary
- current checklist status
- new or archived plan documents created
- remaining blockers or assumptions
```

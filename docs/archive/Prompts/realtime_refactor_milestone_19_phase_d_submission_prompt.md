Use this prompt when handing the Milestone 19 Phase D (deterministic cache-key
normalization and versioned invalidation) off to another session or when
starting the next implementation pass.

Phases A–C and Part B are complete as of 2026-04-12.  This Phase D resolves
the last open cache-key blocker from the Milestone 19 checklist.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the
rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-08-milestone-19-caching-resumability.md
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

Context — what has already landed:

Phase A (2026-04-12, durable local run records):
- `LocalRunRecord(SpecSerializable)` with schema version validation, per-node
  completion state, atomic writes.

Phase B (2026-04-12, local resume semantics):
- `LocalWorkflowSpecExecutor.execute()` accepts `resume_from: Path | None`.
- Prior record is identity-validated (workflow name + artifact path) via
  `_validate_resume_identity()`.
- Completed nodes are skipped; `node_skip_reasons` records why each was reused.

Phase C (2026-04-12, Slurm parity and approval gate):
- `SlurmRunRecord` gained `local_resume_node_state` and
  `local_resume_run_id`; the Slurm submission path accepts
  `resume_from_local_record`.
- `RecipeApprovalRecord(SpecSerializable)` gates composed-recipe execution
  through `approve_composed_recipe` MCP tool.
- `run_local_recipe` and `run_slurm_recipe` check approval for
  `generated_workflow` artifacts.

Part B (2026-04-12, async Slurm monitoring):
- Background asyncio/anyio poll loop in `src/flytetest/slurm_monitor.py`.
- File locking via `fcntl.flock` for concurrent writes.

Remaining blocker — the open checklist item from Phase A that no phase has
resolved yet:

    "Define deterministic cache-key inputs from frozen WorkflowSpec,
     BindingPlan, resolved inputs, runtime bindings, execution profile, and
     runtime-image or resource policy that should invalidate reuse of a prior
     record."

Additionally, the open-blockers section of the checklist notes:

    "Cache-key normalization still needs an explicit decision for
     manifest-backed inputs, local paths, runtime-image data, and
     resource-policy overrides."

    "Cache invalidation needs a versioned rule so handler or schema changes
     do not silently reuse stale outputs."

What Phase D must add:

1. Define a deterministic `cache_identity_key` function that produces a stable
   hex digest from the following frozen inputs:
   - `WorkflowSpec.to_dict()` (the full workflow shape including node names,
     edges, reference names, and output bindings)
   - `BindingPlan.to_dict()` (explicit user bindings, resolved prior assets,
     manifest-derived paths, runtime bindings, execution profile, resource
     spec, and runtime image)
   - Resolved planner inputs (the dict that `_resolve_planner_inputs()`
     produces after manifest scan and explicit overrides)

   The key must be computed from the frozen JSON serialization of these inputs,
   not from Python object identity.  Use `json.dumps(…, sort_keys=True)` and
   a standard hash (SHA-256 truncated to a readable prefix is fine).

2. Normalize paths in the cache key so that cosmetic filesystem differences do
   not produce spurious invalidation:
   - Convert all `Path` values to POSIX strings.
   - Strip the repo-root prefix when it appears, so the same logical input from
     a different checkout path does not invalidate the cache.
   - Document explicitly which path components are kept and which are stripped.

3. Include a `handler_schema_version` field (or equivalent) in the key so that
   a change to a handler's output shape or internal behavior invalidates prior
   records.  The initial implementation may use a repo-global version constant
   (e.g. `HANDLER_SCHEMA_VERSION = "1"`).  A per-handler version can come
   later if the global constant proves too coarse.

4. Persist the computed cache identity in the `LocalRunRecord` (add a
   `cache_identity_key: str` field).  Persist the same key in the
   `SlurmRunRecord` (add a matching field).

5. Extend `_validate_resume_identity()` — or introduce a stronger
   `_validate_resume_cache_key()` — so that resume is rejected when the
   prior record's cache key does not match the current key.  This replaces
   the current coarse workflow-name + artifact-path identity check with a
   content-level check.  Keep the old checks as fast pre-filters but add the
   key comparison as the authoritative gate.

6. Add tests covering:
   - The cache key is deterministic: same inputs → same digest.
   - Changing the workflow spec nodes → different digest.
   - Changing a runtime binding → different digest.
   - Changing the resource spec or runtime image → different digest.
   - Cosmetic path differences (repo-root prefix) → same digest.
   - Resume is accepted when cache keys match.
   - Resume is rejected when cache keys differ, with a clear limitation
     message naming the mismatch.
   - `handler_schema_version` change invalidates an otherwise-matching record.
   - Round-trip: `cache_identity_key` survives save/load for both
     `LocalRunRecord` and `SlurmRunRecord`.

7. Mark the open checklist item under Phase A as complete.
8. Update `CHANGELOG.md`, `docs/capability_maturity.md`, and the open-blockers
   section of the checklist.

Task:

1. Read the checklist under `## Milestone 19` and the `### Open blockers and
   design questions` section; confirm that Phases A–C are complete before
   writing any Phase D code.
2. Audit `src/flytetest/specs.py` for the `SpecSerializable.to_dict()` method
   to confirm JSON round-trip stability before building a key on top of it.
3. Audit `_validate_resume_identity()` in `src/flytetest/spec_executor.py` to
   understand the current identity check before extending it.
4. Implement the `cache_identity_key()` function in `src/flytetest/spec_executor.py`
   (or a new `src/flytetest/cache_keys.py` module if the function is large
   enough to warrant separation).
5. Add the `cache_identity_key` field to `LocalRunRecord` and `SlurmRunRecord`.
6. Wire the key computation into `LocalWorkflowSpecExecutor.execute()` and
   `SlurmWorkflowSpecExecutor._submit_saved_artifact()`.
7. Strengthen the resume identity check to include the cache key.
8. Add focused tests.
9. Update the checklist, CHANGELOG, and capability maturity doc.
10. Stop when blocked, when a compatibility guardrail would be at risk, or when
    the next step would trigger a larger risky batch that should be split.

Important constraints:

- Do not merge `LocalRunRecord` and `SlurmRunRecord` — keep separate shapes.
- Do not change the schema version constants unless you add new required
  fields.  If you add `cache_identity_key` as an optional field with a
  default, the existing schema version is fine.  If you make it required,
  bump the schema version and handle migration from v1 records explicitly.
- The key function must be pure: no filesystem reads, no network calls.  All
  inputs are passed in as already-resolved dicts or dataclass instances.
- Do not strip or normalize inputs that would mask a genuine semantic
  difference.  The goal is: same biology + same runtime policy → same key;
  different biology or different runtime → different key.
- Keep all Milestone 13, 16, 18, and Phase A–C semantics intact.
- Do not rename or remove existing MCP tool names.
- Update docs, manifests, and tests that describe any changed behavior.

Report back with:

- checklist item(s) completed
- files changed
- validation run (test count before and after; all pre-existing tests must
  still pass)
- current checklist status for Milestone 19
- remaining blockers or assumptions
```

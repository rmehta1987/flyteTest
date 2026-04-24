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

Context:

- This is Milestone 20b. Milestone 20a (HPC Failure Recovery) must be merged
  before starting this work. Confirm the `## Milestone 20a` section in
  `docs/realtime_refactor_checklist.md` is marked complete before proceeding.
- M20a owns `SlurmWorkflowSpecExecutor.retry()`, `render_slurm_script()`,
  `SlurmRunRecord`, and the server retry/monitor tools. Do not modify those.
- M20b owns `LocalWorkflowSpecExecutor.execute()`, manifest sidecar writing,
  `resolver.py`, and `spec_artifacts.py`.
- The design is already decided — read the plan doc in full before writing
  any code. Do not re-litigate the architecture.

Key decisions already made (do not re-litigate):

- The durable reference model is a `DurableAssetRef` dataclass added to
  `src/flytetest/spec_artifacts.py`. See the plan doc for the exact fields.
- The index is a `durable_asset_index.json` sidecar file written alongside
  `local_run_record.json`. It is NOT a new field on `LocalRunRecord`.
- `run_manifest.json` format is unchanged. M20b does not touch registered
  stage handlers.
- `LocalManifestAssetResolver.resolve()` gains a `durable_index` parameter
  but does not break any existing callers (default `()`).
- When a manifest path is missing and a durable ref is available, report
  explicitly — do not invent a fallback path and do not silently succeed.
- `_write_json_atomically()` must not be duplicated; move it from
  `spec_executor.py` to `spec_artifacts.py` so the index writer can use it.
  The executor imports from `spec_artifacts`, not vice versa (avoids circular
  imports).

Task:

Phase 1 — Data model (no inter-phase deps):
1. Add `DURABLE_ASSET_INDEX_SCHEMA_VERSION = "durable-asset-index-v1"` to
   `src/flytetest/spec_artifacts.py`.
2. Add `DurableAssetRef` dataclass to `src/flytetest/spec_artifacts.py`.
   Exact fields: `schema_version`, `run_id`, `workflow_name`, `output_name`,
   `node_name`, `asset_path: Path`, `manifest_path: Path | None`,
   `created_at`, `run_record_path: Path`.
3. Add `save_durable_asset_index(refs, run_dir)` and
   `load_durable_asset_index(run_dir)` to `spec_artifacts.py`.
4. Move `_write_json_atomically()` from `spec_executor.py` to
   `spec_artifacts.py` and update the import in `spec_executor.py`.

Phase 2 — Executor integration (depends on Phase 1):
5. Add `_durable_refs_from_record(record: LocalRunRecord) -> list[DurableAssetRef]`
   private helper to `spec_executor.py`. Iterate `record.node_results`; for
   each `node_result`, emit one `DurableAssetRef` per `Path`-valued output
   (skip non-Path outputs). Use `node_result.manifest_paths.get(output_name)`
   for `manifest_path`.
6. After `save_local_run_record(record)` in `LocalWorkflowSpecExecutor.execute()`,
   compute `refs = _durable_refs_from_record(record)` and call
   `save_durable_asset_index(refs, record.run_record_path.parent)` if
   `refs` is non-empty.

Phase 3 — Resolver integration (depends on Phase 1):
7. Add `durable_index: Sequence[DurableAssetRef] = ()` parameter to
   `LocalManifestAssetResolver.resolve()`.
8. In the manifest loading loop, when a manifest source path does not exist
   on the filesystem, check whether any `DurableAssetRef` in `durable_index`
   has a matching `manifest_path` or `asset_path`. If a match is found, add
   a limitation:
   "Manifest at <path> no longer exists; it was last captured in run
   <run_id> (output '<output_name>'). To reuse this output, restore the path
   or re-run the workflow."
   Do not skip the entry silently and do not succeed using the durable ref's
   path as a substitute.

Phase 4 — Tests (parallel with Phase 3):
9. Add 8 tests to the files listed in the plan doc. The exact test cases are
   described in the "8 Test Cases" section of the plan doc — implement all 8.

Phase 5 — Docs:
10. Update `docs/realtime_refactor_checklist.md` — mark M20b items complete.
11. Update `CHANGELOG.md` — add M20b entries under `## Unreleased`.
12. Update `docs/capability_maturity.md` — durable asset / result-reload row.
13. Update `README.md` if any walkthrough references fragile local paths only.

Important constraints:

- Do not modify `run_manifest.json` format or registered stage handlers.
- Do not add fields to `LocalRunRecord` — the index is a sidecar only.
- Do not revert or conflict with M20a changes in `SlurmRunRecord`,
  `render_slurm_script()`, `retry()`, or `_submit_saved_artifact()`.
- Keep README, DESIGN, checklist docs, registry metadata, planner behavior,
  MCP contract, and tests aligned.
- `_write_json_atomically()` must not be duplicated — move it to
  `spec_artifacts.py`, do not copy it.

Validation (run before declaring M20b complete):

1. `python3 -m unittest tests.test_resolver tests.test_spec_executor tests.test_spec_artifacts tests.test_planning -v`
   — all existing and new tests pass
2. `python3 -m unittest` — full suite passes (M20a tests must still pass)
3. `git diff --check` — no trailing whitespace

Report back with:

- checklist items completed
- files changed
- validation run output summary
- current checklist status
- remaining blockers or assumptions
```

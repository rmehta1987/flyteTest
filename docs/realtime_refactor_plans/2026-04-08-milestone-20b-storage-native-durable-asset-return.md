# Milestone 20b Storage-Native Durable Asset Return

Date: 2026-04-08  
Revised: 2026-04-14  
Status: Ready to implement

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 20b

Ordering note:
- Milestone 20a (HPC Failure Recovery) must be merged before starting this
  work. M20a and M20b touch different sections of `spec_executor.py`; see
  the `## Can They Run in Parallel?` section of the original M20 plan for the
  branch isolation strategy.

---

## Current State

- `LocalWorkflowSpecExecutor.execute()` (`spec_executor.py`) writes a
  `local_run_record.json` with a deterministic `run_id` per run.
- `LocalNodeExecutionResult.manifest_paths: dict[str, Path]` already tracks
  which output directories contain a `run_manifest.json`.
- `LocalRunRecord` (fields: `run_id`, `workflow_name`, `created_at`,
  `node_results`, `artifact_path`, `final_outputs`) is the single source of
  truth for a completed local run.
- There is no index or pointer structure that lets a subsequent session find
  the outputs from a prior run without knowing the exact filesystem path.
- Historical manifests use raw filesystem paths; any new reference model must
  be additive (not a replacement).

---

## Target State

- A `DurableAssetRef` dataclass (in `spec_artifacts.py`) captures the stable
  identity of one workflow output: `run_id`, `workflow_name`, `output_name`,
  `node_name`, `asset_path`, `manifest_path | None`, `created_at`,
  `run_record_path`.
- A `durable_asset_index.json` sidecar file is written alongside
  `local_run_record.json` after every successful local execution.  One entry
  per output, keyed by `output_name`.
- `LocalManifestAssetResolver.resolve()` accepts an optional
  `durable_index: Sequence[DurableAssetRef]` parameter.  When a canonical
  filesystem path is missing, it checks the index and reports explicitly:
  *"output 'busco_run_dir' was last seen at <path> in run <run_id> but the
  path no longer exists."*  It does not invent a fallback.
- `list_durable_assets(run_dir)` is a new server-layer helper that scans a
  run directory for `durable_asset_index.json` files and returns a flat list
  of refs — lightweight, no Slurm dependency.
- Legacy `LocalRunRecord` files written before M20b load without error; the
  index is a new sidecar, not a field change.

---

## Concrete Design

### `DurableAssetRef` dataclass

Add to `src/flytetest/spec_artifacts.py`.

```python
DURABLE_ASSET_INDEX_SCHEMA_VERSION = "durable-asset-index-v1"

@dataclass(frozen=True, slots=True)
class DurableAssetRef(SpecSerializable):
    schema_version: str          # DURABLE_ASSET_INDEX_SCHEMA_VERSION
    run_id: str                  # from LocalRunRecord.run_id
    workflow_name: str           # from LocalRunRecord.workflow_name
    output_name: str             # output field name (key in final_outputs)
    node_name: str               # which node produced this output
    asset_path: Path             # absolute path to the output directory or file
    manifest_path: Path | None   # path to run_manifest.json inside asset_path, or None
    created_at: str              # from LocalRunRecord.created_at
    run_record_path: Path        # absolute path to local_run_record.json
```

### Index file location and format

```
{run_root}/{run_id}/
    local_run_record.json         ← existing
    durable_asset_index.json      ← NEW sidecar (M20b)
```

`durable_asset_index.json` structure:

```json
{
  "schema_version": "durable-asset-index-v1",
  "run_id": "20260414T120000Z-select_annotation_qc_busco-abc123",
  "workflow_name": "select_annotation_qc_busco",
  "entries": [
    {
      "schema_version": "durable-asset-index-v1",
      "run_id": "...",
      "workflow_name": "select_annotation_qc_busco",
      "output_name": "results_dir",
      "node_name": "annotation_qc_busco",
      "asset_path": "/abs/path/to/busco_results",
      "manifest_path": "/abs/path/to/busco_results/run_manifest.json",
      "created_at": "2026-04-14T12:00:00Z",
      "run_record_path": "/abs/path/to/local_run_record.json"
    }
  ]
}
```

### New helpers in `spec_artifacts.py`

```python
def save_durable_asset_index(refs: Sequence[DurableAssetRef], run_dir: Path) -> Path:
    """Write durable_asset_index.json atomically to run_dir."""

def load_durable_asset_index(run_dir: Path) -> list[DurableAssetRef]:
    """Load durable_asset_index.json from run_dir; return [] if absent."""
```

### Change in `spec_executor.py` — `LocalWorkflowSpecExecutor.execute()`

After `save_local_run_record(record)` succeeds, derive `DurableAssetRef`
entries from `record.node_results` and call `save_durable_asset_index()`.
No change to `LocalRunRecord` fields — the index is a parallel artifact.

```python
refs = _durable_refs_from_record(record)   # new private helper
if refs:
    save_durable_asset_index(refs, record.run_record_path.parent)
```

`_durable_refs_from_record()` iterates `record.node_results`, looks up each
output in `node_result.manifest_paths`, and constructs a `DurableAssetRef`.

### Change in `resolver.py` — `LocalManifestAssetResolver.resolve()`

Add optional parameter:

```python
def resolve(
    self,
    target_type_name: str,
    *,
    explicit_bindings: ...,
    manifest_sources: ...,
    result_bundles: ...,
    durable_index: Sequence[DurableAssetRef] = (),   # NEW
) -> ResolutionResult:
```

When `durable_index` is provided and a manifest source path is missing from
the filesystem, check if the index has a matching entry and add a descriptive
limitation rather than silently failing:
*"Manifest at <path> no longer exists; it was last captured in run <run_id>
(output '<output_name>'). To reuse this output, restore the path or re-run
the workflow."*

---

## Implementation Steps

**Phase 1 — Data model (no inter-phase deps):**
1. Add `DURABLE_ASSET_INDEX_SCHEMA_VERSION` constant to `spec_artifacts.py`.
2. Add `DurableAssetRef` dataclass to `spec_artifacts.py`.
3. Add `save_durable_asset_index()` and `load_durable_asset_index()` to
   `spec_artifacts.py`.  Use `_write_json_atomically()` (already in
   `spec_executor.py`) — move it to `spec_artifacts.py` or keep it local
   and call it from there; don't duplicate it.

**Phase 2 — Executor integration (depends on Phase 1):**
4. Add `_durable_refs_from_record(record: LocalRunRecord) -> list[DurableAssetRef]`
   private helper to `spec_executor.py`.
5. Call `save_durable_asset_index()` after `save_local_run_record()` in
   `LocalWorkflowSpecExecutor.execute()`.  Guard with `if refs:` so an empty
   output set doesn't write an empty index.

**Phase 3 — Resolver integration (depends on Phase 1):**
6. Add `durable_index` parameter to `LocalManifestAssetResolver.resolve()`.
7. In the resolution loop, when a manifest source path does not exist, check
   whether a `DurableAssetRef` in `durable_index` matches by path.  If yes,
   produce an explicit limitation message (not a crash, not a silent skip).

**Phase 4 — Tests (can run parallel with Phase 3):**
8. Add or extend tests in `tests/test_spec_artifacts.py` and
   `tests/test_spec_executor.py` covering the 8 cases below.

**Phase 5 — Docs:**
9. Update `docs/realtime_refactor_checklist.md` — mark M20b items complete.
10. Update `CHANGELOG.md` — add M20b entries under `## Unreleased`.
11. Update `docs/capability_maturity.md` — durable asset / result-reload row.
12. Update `README.md` if any walkthrough references fragile local paths.

---

## 8 Test Cases

Add to `tests/test_spec_artifacts.py` (tests 1–3) and
`tests/test_spec_executor.py` (tests 4–6) and `tests/test_resolver.py`
(tests 7–8).

**Test 1** — `test_durable_asset_ref_round_trips_through_save_load`  
  Construct a `DurableAssetRef` with known fields, call
  `save_durable_asset_index([ref], run_dir)`, call
  `load_durable_asset_index(run_dir)`.  Assert fields survive round-trip.

**Test 2** — `test_load_durable_asset_index_returns_empty_for_missing_file`  
  Call `load_durable_asset_index()` on a directory without
  `durable_asset_index.json`.  Assert returns `[]` without raising.

**Test 3** — `test_durable_asset_index_schema_version_is_validated`  
  Write a `durable_asset_index.json` with a wrong `schema_version`.  Assert
  `load_durable_asset_index()` raises a descriptive error (same pattern as
  `load_local_run_record()` version check).

**Test 4** — `test_local_execution_writes_durable_asset_index_alongside_run_record`  
  Run `LocalWorkflowSpecExecutor.execute()` with a synthetic handler that
  returns a result directory.  Assert `durable_asset_index.json` is written
  next to `local_run_record.json`.  Assert the entry has the correct
  `run_id`, `workflow_name`, `output_name`, and `asset_path`.

**Test 5** — `test_durable_asset_index_fields_match_run_record`  
  After local execution (test 4 fixture), load both `local_run_record.json`
  and `durable_asset_index.json`.  Assert `run_id`, `workflow_name`, and
  `created_at` are identical in both.

**Test 6** — `test_legacy_run_record_loads_without_durable_index`  
  Load a `LocalRunRecord` from a directory that has no
  `durable_asset_index.json` (simulates pre-M20b run directories).  Assert
  `load_local_run_record()` succeeds and `load_durable_asset_index()` returns
  `[]`.

**Test 7** — `test_resolver_reports_missing_path_with_durable_ref_context`  
  Build a resolver with a manifest source pointing to a nonexistent path.
  Provide a `durable_index` entry for that path.  Assert
  `resolve()` returns a `ResolutionResult` with a limitation that mentions
  the `run_id` and `output_name` from the durable ref (not a silent failure).

**Test 8** — `test_resolver_succeeds_when_durable_ref_path_exists`  
  Build a resolver with a manifest source that exists on disk.  Provide a
  matching `durable_index` entry.  Assert resolution succeeds normally (the
  durable ref does not interfere with the happy path).

---

## Files Changed

| File | Change |
|---|---|
| `src/flytetest/spec_artifacts.py` | Add `DurableAssetRef`, `save_durable_asset_index()`, `load_durable_asset_index()` |
| `src/flytetest/spec_executor.py` | Add `_durable_refs_from_record()`, call `save_durable_asset_index()` in `execute()` |
| `src/flytetest/resolver.py` | Add `durable_index` param to `LocalManifestAssetResolver.resolve()` |
| `tests/test_spec_artifacts.py` | Tests 1–3 |
| `tests/test_spec_executor.py` | Tests 4–6 |
| `tests/test_resolver.py` | Tests 7–8 |
| `docs/realtime_refactor_checklist.md` | Mark M20b items complete |
| `CHANGELOG.md` | Add M20b entries |
| `docs/capability_maturity.md` | Update durable asset row |

---

## Validation

```bash
python3 -m unittest tests.test_resolver tests.test_spec_executor tests.test_spec_artifacts tests.test_planning -v
python3 -m unittest   # full suite — M20a tests must still pass
git diff --check
```

---

## Blockers or Assumptions

- `_write_json_atomically()` is currently private in `spec_executor.py`
  (line ~820).  Either expose it or duplicate the pattern for the index
  writer in `spec_artifacts.py`.  Prefer moving it to `spec_artifacts.py`
  so the executor can import from there (not the other way around, to avoid
  a circular import).
- `LocalRunRecord.final_outputs` values are `Any`; `_durable_refs_from_record()`
  must handle cases where an output is not a `Path` (e.g. a string or int)
  — only emit `DurableAssetRef` entries for `Path`-valued outputs.
- The manifest field in `run_manifest.json` is written by registered handlers,
  not by the executor.  M20b does **not** modify `run_manifest.json` format;
  the durable index is a parallel sidecar, keeping manifests unchanged.
- This is V1: filesystem-backed only.  No content-addressed storage.
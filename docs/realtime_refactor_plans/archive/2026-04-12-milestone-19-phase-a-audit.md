# Milestone 19 Core Phase A Audit Report

**Date:** 2026-04-12  
**Status:** Audit complete; ready for implementation  
**Previous Checkpoint:** Milestone 15 complete (237 tests passing, zero regressions)  

---

## Executive Summary

This audit maps the current execution state in `spec_executor.py`, identifies the smallest insertion point for a durable local run-record, and validates the design against the existing Slurm record save/load pattern from M16/18.

**Key Finding:** The local execution path (`LocalWorkflowSpecExecutor.execute()`) currently produces transient `LocalSpecExecutionResult` objects with no durable state. Adding a minimal `LocalRunRecord` dataclass and persisting it after execution completes is the smallest insertion point that enables the later resume semantics (Phase B/C).

**Next Step Before Phase B:** Implement Phase A prototype with `LocalRunRecord` dataclass, save/load helpers, and round-trip validation test. **Do not add resume logic until Phase A's record model is proven cleanly.**

---

## Current State Analysis

### 1. Local Execution Architecture

**File:** `src/flytetest/spec_executor.py` lines 1295–1398

**Flow:**
```
LocalWorkflowSpecExecutor.execute(artifact_source)
  ├─ Load SavedWorkflowSpecArtifact
  ├─ Resolve planner inputs
  ├─ For each node in workflow_spec.nodes:
  │  ├─ Build node inputs
  │  ├─ Get registered handler
  │  └─ Execute handler → outputs
  │     Append LocalNodeExecutionResult(node_name, reference_name, outputs, manifest_paths)
  └─ Collect final_outputs
     Return LocalSpecExecutionResult(supported, workflow_name, node_results, final_outputs, ...)
```

**Critical Limitation:** Nothing persisted; all state is transient memory.

### 2. LocalNodeExecutionResult Current Shape

**File:** `spec_executor.py` lines 59–67

```python
@dataclass(frozen=True, slots=True)
class LocalNodeExecutionResult:
    """Execution details recorded for one saved-spec node."""
    node_name: str                                # e.g., "repeat_filtering"
    reference_name: str                           # e.g., "annotation_repeat_filtering"
    outputs: Mapping[str, Any]                    # Handler output dict
    manifest_paths: Mapping[str, Path] = field(default_factory=dict)  
```

**Properties:**
- Immutable (frozen, slots)
- NOT SpecSerializable (no `to_dict()`, `from_dict()`, schema version)
- Successfully captures per-node output + manifest references
- **Suitable for local run records** with minor additions

### 3. LocalSpecExecutionResult Current Shape

**File:** `spec_executor.py` lines 73–88

```python
@dataclass(frozen=True, slots=True)
class LocalSpecExecutionResult:
    """Outcome of executing a saved workflow spec through local handlers."""
    supported: bool
    workflow_name: str
    execution_profile: str | None                 # e.g., "local"
    resolved_planner_inputs: Mapping[str, Any]    # Frozen inputs dict
    resource_spec: ResourceSpec | None
    runtime_image: RuntimeImageSpec | None
    node_results: tuple[LocalNodeExecutionResult, ...]
    final_outputs: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
```

**Properties:**
- Immutable, no schema version
- Captures workflow-level metadata + all node results
- **Suitable as template for LocalRunRecord**
- Missing: run_id, run_record_path, created_at, artifact_path, per-node completion state

### 4. Slurm Run Record Pattern (M16/M18)

**File:** `spec_executor.py` lines 117–164

**Key Structure:**
```python
@dataclass(frozen=True, slots=True)
class SlurmRunRecord(SpecSerializable):
    schema_version: str                      # Must check on deserialize
    run_id: str                              # Stable, unique identifier
    recipe_id: str                           # Artifact filename stem
    workflow_name: str
    artifact_path: Path                      # Frozen recipe reference
    run_record_path: Path                    # Location of this record
    job_id: str                              # Slurm job ID
    execution_profile: str                   # Always "slurm"
    submitted_at: str                        # ISO UTC timestamp
    scheduler_state: str                     # Slurm state (PENDING, RUNNING, etc.)
    final_scheduler_state: str | None        # Terminal state if reached
    attempt_number: int                      # Retry lineage tracking
    retry_parent_run_id: str | None          # If this is a retry
    retry_child_run_ids: tuple[str, ...]     # Linked retry children
    failure_classification: SlurmFailureClassification | None
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
```

**Key Patterns to Adopt for LocalRunRecord:**
1. ✓ SpecSerializable base (enables `to_dict()`, `from_dict()`)
2. ✓ schema_version constant for versioning
3. ✓ run_id, run_record_path, created_at metadata
4. ✓ artifact_path reference to frozen recipe
5. ✓ execution_profile string identifier
6. ✓ frozen dataclass + slots
7. ⚠ Slurm-specific fields (job_id, scheduler_state) → local equivalents needed

### 5. Slurm Save/Load Helpers

**Save function:** `save_slurm_run_record()` (lines 666–674)
```python
def save_slurm_run_record(record: SlurmRunRecord) -> Path:
    """Persist one Slurm run record atomically."""
    _write_json_atomically(record.run_record_path, record.to_dict())
    return record.run_record_path
```

**Load function:** `load_slurm_run_record()` (lines 649–663)
```python
def load_slurm_run_record(source: Path) -> SlurmRunRecord:
    """Load one durable Slurm run record from a directory or JSON path."""
    record_path = _slurm_run_record_path(source)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != SLURM_RUN_RECORD_SCHEMA_VERSION:
        raise ValueError(f"Unsupported Slurm run record schema version: {schema_version!r}")
    return SlurmRunRecord.from_dict(payload)
```

**Atomic Write Helper:** `_write_json_atomically()` (lines 784–793)
```python
def _write_json_atomically(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON payload through a temporary file before replacing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n")
    os.replace(temporary_path, path)
```

**SpecSerializable Interface:**
```python
class SpecSerializable:
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self: ...
```

### 6. Existing Helper Functions Available for Reuse

**Run ID generation:** `_run_id_for_artifact()` (lines 1216–1229)
- Creates stable, human-readable ID from artifact path + creation time
- Includes hash suffix to ensure uniqueness
- Returns: `"<YYYYMMDDTHHMMSSZ>-<workflow-slug>-<hash>"`

**Run directory allocation:** `_allocate_run_dir()` (lines 1232–1245)
- Creates unique run directory with retry suffix if needed
- Handles concurrent runs in the same second
- Returns: `(run_id, run_dir)` tuple

**JSON timestamp:** `_created_at()` (lines 1209–1213)
- Returns ISO UTC timestamp: "2026-04-12T12:34:56Z"

**Path resolution:** `_slurm_run_record_path()` (lines 795–802)
- Handles directory-vs-file semantics
- Returns directory → append FILENAME; file → return as-is

**JSON normalization:** `_json_ready()` (lines 745–756)
- Converts Path, dataclasses, dicts, lists to JSON-safe forms
- Handles nested structures recursively

---

## Phase A Design: LocalRunRecord

### Proposed Schema

```python
LOCAL_RUN_RECORD_SCHEMA_VERSION = "local-run-record-v1"
DEFAULT_LOCAL_RUN_RECORD_FILENAME = "local_run_record.json"

@dataclass(frozen=True, slots=True)
class LocalRunRecord(SpecSerializable):
    """Durable run record for local saved-spec execution.
    
    Captures frozen recipe identity, resolved inputs, per-node completion state,
    and outputs so interrupted work can resume without recomputing stages.
    """

    schema_version: str                      # LOCAL_RUN_RECORD_SCHEMA_VERSION
    run_id: str                              # Stable, human-readable identifier
    workflow_name: str                       # Workflow name from spec
    artifact_path: Path                      # Path to SavedWorkflowSpecArtifact
    run_record_path: Path                    # Location of this record's JSON
    created_at: str                          # ISO UTC timestamp (e.g., "2026-04-12T12:34:56Z")
    execution_profile: str                   # Always "local" (for parity with Slurm="slurm")
    resolved_planner_inputs: Mapping[str, Any]  # Frozen planner input dict
    resource_spec: ResourceSpec | None       # Resource request (if any)
    runtime_image: RuntimeImageSpec | None   # Runtime image (if any)
    binding_plan_target: str | None          # Binding plan target name
    
    # Per-node completion tracking (Phase B will validate & skip completed nodes)
    node_completion_state: dict[str, bool]   # { node_name: completed? }
    node_results: tuple[LocalNodeExecutionResult, ...]  # Persistent node results
    
    # Final workflow outputs (populated only if execution completed)
    final_outputs: Mapping[str, Any] = field(default_factory=dict)
    
    # Metadata for audit and troubleshooting
    completed_at: str | None = None          # ISO timestamp if workflow ran to completion
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)
```

### Why This Design

1. **Minimal insertion:** Reuses existing helper infrastructure (atomic write, JSON ready, ID generation)
2. **Parity with Slurm:** Same pattern (schema version, artifact reference, frozen inputs, run ID)
3. **Resume-ready:** `node_completion_state` dict enables Phase B bypass logic
4. **Explicit boundaries:** No hidden state; all inputs and outputs captured
5. **Serializable:** SpecSerializable interface with `to_dict()`/`from_dict()` + schema validation
6. **Single responsibility:** Records execution outcome, not execution logic

### What Phase A Does Not Include

- ✗ Cache key derivation (Phase C)
- ✗ Resume logic (Phase B)
- ✗ Node skipping (Phase B)
- ✗ Slurm integration (Phase C)
- ✗ Resumability validation across recipe versions (Phase C)

---

## Save/Load Pattern for LocalRunRecord

### Save Helper (New)

```python
def save_local_run_record(record: LocalRunRecord) -> Path:
    """Persist one local run record atomically."""
    _write_json_atomically(record.run_record_path, record.to_dict())
    return record.run_record_path
```

### Load Helper (New)

```python
def load_local_run_record(source: Path) -> LocalRunRecord:
    """Load one durable local run record from a directory or JSON path."""
    record_path = _local_run_record_path(source)
    payload = json.loads(record_path.read_text())
    schema_version = payload.get("schema_version")
    if schema_version != LOCAL_RUN_RECORD_SCHEMA_VERSION:
        raise ValueError(f"Unsupported local run record schema version: {schema_version!r}")
    return LocalRunRecord.from_dict(payload)

def _local_run_record_path(source: Path) -> Path:
    """Resolve a directory or JSON path to the local run record file."""
    return (
        source / DEFAULT_LOCAL_RUN_RECORD_FILENAME
        if source.is_dir()
        else source
    )
```

### Integration Point in LocalWorkflowSpecExecutor.execute()

```python
def execute(self, artifact_source, *, explicit_bindings=None, ...):
    # ... existing setup code ...
    
    # After execution loop completes:
    final_outputs = { ... }
    
    # NEW: Build and persist run record
    run_id, run_dir = _allocate_run_dir(self._run_root, _run_id_for_artifact(...))
    record = LocalRunRecord(
        schema_version=LOCAL_RUN_RECORD_SCHEMA_VERSION,
        run_id=run_id,
        workflow_name=workflow_spec.name,
        artifact_path=artifact_path_from_source,
        run_record_path=run_dir / DEFAULT_LOCAL_RUN_RECORD_FILENAME,
        created_at=_created_at(),
        execution_profile="local",
        resolved_planner_inputs=resolved_planner_inputs,
        resource_spec=binding_plan.resource_spec,
        runtime_image=binding_plan.runtime_image,
        binding_plan_target=binding_plan.target_name,
        node_completion_state={node.name: True for node in workflow_spec.nodes},
        node_results=tuple(node_results),
        final_outputs=final_outputs,
        completed_at=_created_at(),
        assumptions=tuple(dict.fromkeys(assumptions)),
    )
    save_local_run_record(record)
    
    return LocalSpecExecutionResult(...)
```

---

## Round-Trip Validation Test (Phase A)

**Test File:** `tests/test_spec_executor.py`

**Test Pattern:**
```python
def test_local_run_record_round_trip(tmp_path):
    """Verify LocalRunRecord persists and deserializes cleanly."""
    # 1. Create a minimal LocalRunRecord
    run_dir = tmp_path / "test_run_001"
    run_dir.mkdir()
    
    record = LocalRunRecord(
        schema_version="local-run-record-v1",
        run_id="20260412T123456Z-test-workflow-abc1234",
        workflow_name="test_workflow",
        artifact_path=Path("/path/to/artifact.json"),
        run_record_path=run_dir / "local_run_record.json",
        created_at="2026-04-12T12:34:56Z",
        execution_profile="local",
        resolved_planner_inputs={"ConsensusAnnotation": {...}},
        resource_spec=None,
        runtime_image=None,
        binding_plan_target="test",
        node_completion_state={"node_1": True, "node_2": True},
        node_results=(
            LocalNodeExecutionResult(
                node_name="node_1",
                reference_name="task_1",
                outputs={"out_1": str(run_dir / "output_1.txt")},
            ),
        ),
        final_outputs={"result": "success"},
        completed_at="2026-04-12T12:34:57Z",
    )
    
    # 2. Save atomically
    saved_path = save_local_run_record(record)
    assert saved_path.exists()
    assert saved_path == run_dir / "local_run_record.json"
    
    # 3. Load and verify round-trip
    loaded = load_local_run_record(run_dir)
    assert loaded.run_id == record.run_id
    assert loaded.workflow_name == record.workflow_name
    assert loaded.node_completion_state == record.node_completion_state
    assert loaded.final_outputs == record.final_outputs
    
    # 4. Verify schema version check
    with pytest.raises(ValueError, match="Unsupported local run record schema version"):
        bad_payload = record.to_dict()
        bad_payload["schema_version"] = "unknown-v99"
        bad_path = run_dir / "bad_record.json"
        bad_path.write_text(json.dumps(bad_payload))
        load_local_run_record(bad_path)
```

---

## Current Code Inventory

### Files Requiring Modifications

| File | Modifications |
|------|---|
| `src/flytetest/spec_executor.py` | Add LocalRunRecord dataclass, save/load helpers, constants; update execute() to persist record |
| `tests/test_spec_executor.py` | Add round-trip and persistence tests |

### Files Not Required for Phase A

| File | Reason |
|------|--------|
| `server.py` | Only calls execute() at a high level; no changes needed in Phase A |
| `spec_artifacts.py` | SavedWorkflowSpecArtifact unchanged; still the source of truth |
| `specs.py` | WorkflowSpec/NodeSpec/BindingPlan unchanged |
| `planner.py` | Planner logic unchanged |

### New Constants

```python
LOCAL_RUN_RECORD_SCHEMA_VERSION = "local-run-record-v1"
DEFAULT_LOCAL_RUN_RECORD_FILENAME = "local_run_record.json"
```

### New Public Functions

```python
def save_local_run_record(record: LocalRunRecord) -> Path: ...
def load_local_run_record(source: Path) -> LocalRunRecord: ...
```

### Helper Function (Internal)

```python
def _local_run_record_path(source: Path) -> Path: ...
```

---

## Design Decisions Made

### 1. Schema Versioning
- Use simple string version: `"local-run-record-v1"`
- Match Slurm pattern for consistency
- Enables future migration if structure changes

### 2. Completion State Representation
- Use dict[str, bool] keyed by node_name
- Phase B will derive cache-key logic from this
- Simpler than hash-based cache keys for Phase A

### 3. Resolved Inputs Storage
- Store complete resolved_planner_inputs in record
- Phase B will use these without re-resolving
- Ensures deterministic resume behavior

### 4. Run Directory Allocation
- Reuse existing `_allocate_run_dir()` helper
- Use existing `_run_id_for_artifact()` for stable IDs
- Create run dir before first write (atomic persist already ensures safety)

### 5. Execution Profile String
- Use "local" for LOCAL execution (matches "slurm" for Slurm)
- Enables unified query path across both execution modes

---

## Risk Analysis

### Low Risk
- ✓ No changes to existing execute() logic (inside the node loop)
- ✓ No changes to handler contracts
- ✓ Reuses proven atomic-write pattern from Slurm code
- ✓ SpecSerializable is standard across the codebase
- ✓ Frozen dataclass prevents accidental mutations

### Medium Risk
- ⚠ New dataclass must be added to `__all__` export list
- ⚠ Tests must verify schema version validation
- ⚠ Run directory path conventions must be documented

### Handled by Design
- ✓ Atomic persistence prevents incomplete writes
- ✓ Schema version check prevents old records being loaded as new
- ✓ Immutable Records prevent state mutations
- ✓ No reverse-compatibility needed (Phase A only, no Phase 1 users yet)

---

## Success Criteria for Phase A

1. ✓ LocalRunRecord dataclass defined and SpecSerializable
2. ✓ save_local_run_record() persists atomically with temp file pattern
3. ✓ load_local_run_record() validates schema_version on deserialize
4. ✓ Round-trip test proves deserialization exact-matches serialization
5. ✓ LocalWorkflowSpecExecutor.execute() persists record after success
6. ✓ New code passes all existing 237 tests (no regressions)
7. ✓ New tests added for save/load/round-trip (minimum 3 tests)
8. ✓ Constants exported in `__all__`
9. ✓ Public functions documented with docstrings
10. ✓ No changes to execute() loop internals (clean separation)

---

## Open Questions Resolved

### Q1: Where should LocalRunRecord live relative to SlurmRunRecord?
**A:** Same file (`spec_executor.py`), immediately after SlurmRunRecord definitions. Enables single import and clear visual grouping.

### Q2: Should node_completion_state use hash-based cache keys now or string flags?
**A:** String flags (node_name → bool) for Phase A. Phase C will derive cache keys from frozen inputs; Phase A only tracks completion.

### Q3: Should resolved_planner_inputs be included in record or derived fresh on resume?
**A:** Store in record. Guarantees deterministic resume; prevents re-resolution from finding different inputs later.

### Q4: Should we add run_record_path to LocalWorkflowSpecExecutor constructor?
**A:** No. Phase A only saves after success. Phase B will add optional `load_from=` path. Keep constructor minimal.

---

## Next Steps (Do Not Start Until Phase A Complete)

### Phase B Direction
- Add `load_local_run_record(source)` option to execute()
- Check if run_id and artifact match; skip completed nodes
- Add resumption tests

### Phase C Direction
- Derive cache keys from frozen spec hash + resolved inputs hash + binding hash
- Implement skipping logic using cache keys
- Add Slurm parity tests

### After Phase C
- Add approval-acceptance gate for composed execution
- Extend to async Slurm monitoring (Part B)

---

## Summary

Phase A audit confirms that adding a minimal `LocalRunRecord` class with atomic save/load helpers is the cleanest insertion point for durable run records in local execution. The design mirrors the Slurm pattern for consistency and reuses existing helper infrastructure. **No execute() loop changes required; record persistence happens only after workflow completion.**

Round-trip validation ensures the record persists and deserializes cleanly before Phase B adds resumption logic.

**Ready to proceed with implementation.**

# Dataclass Serialization Consolidation

## Context

The codebase uses a strong dataclass style throughout — frozen dataclasses with
hand-rolled `to_dict()` / `from_dict()` serialization. The main problem is not
the dataclass choice itself but three sources of accumulated duplication:

1. **Duplicate type names across layers** — `ReferenceGenome` exists in both
   `planner_types.py` and `types/assets.py`; similar duplicates exist for read
   sets and transcript evidence types.
2. **Repeated metadata fields** — `notes: tuple[str, ...]`,
   `source_result_dir: Path | None`, and `source_manifest_path: Path | None`
   appear verbatim in five modules.
3. **Three near-identical serialization implementations** — `planner_types.py`,
   `types/assets.py`, and `specs.py` each maintain their own `_serialize*`,
   `_deserialize*`, `to_dict()`, and `from_dict()` logic.

This plan consolidates all three into shared infrastructure without changing
runtime behavior or the public planner surface.

**Gate:** Implement after M19 phases C and D are confirmed complete. This
refactor touches the same shared files M19 is still writing to
(`planner_types.py`, `spec_executor.py`, `specs.py`, `server.py`). Starting
before M19 closes will create merge conflicts in exactly the wrong files.

---

## Affected Files

| File | Problem |
|---|---|
| `src/flytetest/planner_types.py` | Duplicate `ReferenceGenome`; repeated `notes` / provenance fields; own serialization helpers |
| `src/flytetest/types/assets.py` | Duplicate `ReferenceGenome`; repeated provenance fields; own serialization helpers |
| `src/flytetest/specs.py` | Own serialization helpers; repeated field patterns |
| `src/flytetest/spec_executor.py` | `LocalRunRecord` and `SlurmRunRecord` (added M19) repeat `notes`-style fields and hand-rolled serialization |
| `src/flytetest/planner_adapters.py` | Repeated provenance field assignments at planner/asset boundary |
| `src/flytetest/server.py` | Minor repeated field patterns in response construction |

---

## Implementation Steps

### Step 1: Create `src/flytetest/serialization.py`

One shared serialization module used by all layers:

```python
# src/flytetest/serialization.py

def serialize_value(value: Any) -> Any: ...
def deserialize_value(annotation: Any, value: Any) -> Any: ...

class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]): ...
```

**Constraint:** Do not use `slots=True`. The existing codebase uses
`frozen=True` without slots throughout. Flyte's serialization layer relies on
`dataclasses.fields()` and `dataclasses.asdict()`; slots-enabled frozen
dataclasses can behave differently with pickling and `asdict()` in ways that
could silently break Flyte task boundaries.

### Step 2: Create `src/flytetest/common_types.py`

Shared mixin dataclasses for the repeated field groups:

```python
# src/flytetest/common_types.py

@dataclass(frozen=True)
class NotesMixin:
    notes: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class ProvenanceMixin:
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
```

### Step 3: Refactor `planner_types.py`

- Import `NotesMixin`, `ProvenanceMixin`, `SerializableDataclass`
- Remove the repeated field definitions from individual dataclasses
- Remove the duplicate `_serialize*` / `_deserialize*` helpers; delegate to
  `serialization.py`

### Step 4: Refactor `types/assets.py`

- Import the same shared mixins
- Rename the duplicate `ReferenceGenome` to `ReferenceGenomeAsset` (or keep an
  alias for backwards compatibility with historical manifests)
- Preferred naming convention: **Option 1** — planner types are canonical,
  asset-layer counterparts get the `Asset` suffix
  - `ReferenceGenome` (planner) stays as-is
  - `ReferenceGenomeAsset` (asset layer)
  - `ReadPairAsset` instead of `ReadPair` in assets
- Remove duplicate serialization helpers

### Step 5: Refactor `spec_executor.py`

- Apply `NotesMixin` / `ProvenanceMixin` to `LocalRunRecord` and `SlurmRunRecord`
  where appropriate
- Consolidate their hand-rolled serialization to use `SerializableDataclass`

### Step 6: Refactor `specs.py`

- Replace the local serialization helpers with `serialize_value` /
  `deserialize_value` from `serialization.py`

### Step 7: Add explicit adapter functions at the planner/asset boundary

Replace the repeated field-assignment patterns in `planner_adapters.py` with
named converter functions:

```python
def reference_genome_from_asset(asset: ReferenceGenomeAsset) -> ReferenceGenome: ...
def reference_genome_asset_from_planner(planner: ReferenceGenome) -> ReferenceGenomeAsset: ...
```

This makes the layer boundary explicit instead of scattered across adapter
functions.

### Step 8: Rename / alias cleanup

- Add `__all__` to both `planner_types.py` and `types/assets.py` to make the
  public surface explicit
- Where renaming `ReferenceGenome` in assets would break historical manifest
  replay, preserve the old name as an alias:
  `ReferenceGenome = ReferenceGenomeAsset  # legacy alias`

---

## What Does Not Change

- The planner type names as seen by the MCP surface (`ReferenceGenome`,
  `ReadSet`, `TranscriptEvidenceSet`, etc.)
- The `ManifestSerializable` protocol in `types/assets.py` — keep it as the
  asset-layer serialization contract
- The `PlannerSerializable` mixin in `planner_types.py` — keep it as the
  planner-layer contract; `SerializableDataclass` backs it, not replaces it
- Flyte task and workflow signatures — no `@task` or `@workflow` boundaries
  change
- Registry entries and MCP tool contracts

---

## Out of Scope for This Plan

- `InterfaceField` builder centralization in `registry.py` — that is a
  separate registry cleanup, not a serialization concern
- Adding new biological types or planner types
- Changing the `ManifestSerializable.to_dict()` wire format (must remain
  backwards-compatible with existing `run_manifest.json` files on disk)

---

## Validation

After each step:

1. `python3 -m compileall src/flytetest/` — no import errors
2. `.venv/bin/python -m pytest tests/ -q` — all passing tests remain passing
3. `grep -r "source_result_dir\|source_manifest_path\|notes: tuple" src/flytetest/` —
   count should drop toward the two mixin definitions only
4. `grep -r "def _serialize\|def _deserialize\|def to_dict\|def from_dict" src/flytetest/` —
   count should converge toward `serialization.py` plus the two protocol mixins

Final check: load a historical `run_manifest.json` through the resolver and
confirm manifest replay still works end-to-end.

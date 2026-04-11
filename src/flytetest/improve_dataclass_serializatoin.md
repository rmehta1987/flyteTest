Collecting exact duplicate type definitions and common field patterns from planner and asset models so the analysis can be concrete.

Searched for regex `class ReferenceGenome|class ReadSet|class ReadPair|class TranscriptEvidenceSet|class TranscriptomeReference|class QualityAssessmentTarget|class ConsensusAnnotation|class ProteinEvidenceSet|class AnnotationEvidenceSet` (`**/src/**/*.py`), 10 results

Searched for regex `source_result_dir|source_manifest_path|notes: tuple\[str, \.\.\.` (`**/src/**/*.py`), 142 results

## Analysis: centralizing dataclass logic and avoiding duplicate names

The repo currently uses a strong dataclass style, and that is a good fit to keep. The main issue is not “dataclass vs Pydantic” but rather duplicate model names and repeated serialization/provenance fields across layers.

---

## 1. What is duplicated now

### a. Repeated names across layers
- `ReferenceGenome` exists in both:
  - planner_types.py
  - assets.py
- `ReadSet` vs `ReadPair`
- `TranscriptEvidenceSet` (planner) vs `TranscriptomeReference` / specific asset bundles
- `QualityAssessmentTarget` / `ConsensusAnnotation` / `AnnotationEvidenceSet` have no direct asset analogs, but similar provenance fields repeat.

This is a naming smell because the same biological concept is being expressed in parallel but with only layer-specific distinctions.

### b. Repeated metadata fields
Many dataclasses repeat:
- `notes: tuple[str, ...] = field(default_factory=tuple)`
- `source_result_dir: Path | None = None`
- `source_manifest_path: Path | None = None`

That repetition appears in:
- planner_types.py
- `types/assets.py`
- planner_adapters.py
- spec_executor.py
- server.py

### c. Repeated serialize/deserialize logic
There are three near-identical serialization systems:
- planner_types.py
- assets.py
- specs.py

Each has its own `_serialize*`, `_deserialize*`, `to_dict()`, and `from_dict()`.

---

## 2. Centralization strategy

### a. Shared metadata mixins
Create small reusable dataclass mixins for recurring fields, for example:

- `class NotesMixin: notes: tuple[str, ...] = field(default_factory=tuple)`
- `class ProvenanceMixin: source_result_dir: Path | None = None; source_manifest_path: Path | None = None`
- `class PathAssetMixin: ...` if other path groups recur

Then use them in both planner and asset dataclasses:

- `class ReferenceGenome(plannerSerializable, NotesMixin, ProvenanceMixin): ...`
- `class TranscriptEvidenceSet(..., ProvenanceMixin): ...`

This keeps shared fields centralized and avoids copy/paste.

### b. Shared serialization utilities
Move all serialization logic into one shared helper module, for example:

- `src/flytetest/serialization.py`

That module can expose:
- `serialize_dataclass(value)`
- `deserialize_dataclass(annotation, payload)`
- `is_optional_annotation(annotation)`

Then each mixin can reuse it:
- `class PlannerSerializable:`
  - `to_dict(self) -> dict[str, Any]`
  - `from_dict(...)`
- `class ManifestSerializable:`
  - same with the shared helpers

This avoids maintaining three similar implementations.

### c. Layer-specific wrappers around shared type definitions
Instead of duplicate names, use a common base plus layer-specific wrappers:

Example:
- `class ReferenceGenomeBase: fasta_path: Path; organism_name: str | None; ...`
- `class ReferenceGenomeAsset(ReferenceGenomeBase, ManifestSerializable): ...`
- `class ReferenceGenome(ReferenceGenomeBase, PlannerSerializable): ...`

Or if the intent is to keep the planner name as canonical:
- `class ReferenceGenome(ReferenceGenomeBase, PlannerSerializable): ...`
- `class ReferenceGenomeAsset(ReferenceGenomeBase, ManifestSerializable): ...`

This gives a clear naming convention:
- `*Asset` for lower-level manifest/local asset models
- plain names for planner-facing abstractions
- optionally `*Spec` for planning/runtime metadata

---

## 3. Naming recommendations

### a. Pick a consistent suffix convention
To avoid confusion across layers, choose one of:

Option 1: Planner-types are canonical, assets get suffixes
- `ReferenceGenome`
- `ReadSet`
- `TranscriptEvidenceSet`
- `ReferenceGenomeAsset`
- `ReadPairAsset`
- `SalmonIndexAsset`

Option 2: Base shared canonical names, layer wrappers suffix
- `ReferenceGenomeBase`
- `ReferenceGenomePlanner`
- `ReferenceGenomeAsset`

I recommend **Option 1** in this repo, because the planner layer is the new stable surface and the asset layer is legacy/local.

### b. Use adapter functions instead of duplicate names
Where planner code needs an asset object, convert explicitly:
- `planner_ref = reference_genome_from_asset(asset_reference_genome)`
- `asset_ref = reference_genome_asset_from_planner(planner_reference_genome)`

This makes the boundary explicit and avoids accidental mixing of types.

### c. If renaming is too disruptive, preserve aliases
You can keep compatibility by defining aliases:
- `ReferenceGenomeAsset = ReferenceGenome`
- `ReadPair = ReadSetAsset`
- `__all__ = [...]`

That allows gradual cleanup.

---

## 4. Practical consolidation plan

### Step 1: add shared helpers
Create `src/flytetest/serialization.py` containing:
- one generic `_serialize_value`
- one generic `_deserialize_value`
- `SerializableDataclass` mixin

### Step 2: add shared metadata mixins
Create `src/flytetest/common_types.py` containing:
- `NotesMixin`
- `ProvenanceMixin`
- `SourceManifestMixin` / `RunProvenanceMixin`

### Step 3: refactor planner_types.py
- import `NotesMixin`, `ProvenanceMixin`, `SerializableDataclass`
- make the repeated fields come from mixins
- remove duplicate serialization functions

### Step 4: refactor `types/assets.py`
- import the same shared mixins
- use `ReferenceGenomeAsset` or `ReferenceGenomeBase` instead of duplicate plain `ReferenceGenome`
- keep asset-specific fields as needed

### Step 5: refactor specs.py
- use the same `SerializableDataclass` logic for spec serialization
- reduce duplicate helper functions

### Step 6: rename / alias types
- Prefer `ReadPairAsset` or `SequencingReadPair` in `types/assets.py`
- Keep `ReadSet` planner type as-is
- Add one shared base if you want common fields preserved

---

## 5. Example structure

```python
# src/flytetest/common_types.py
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True, slots=True)
class NotesMixin:
    notes: tuple[str, ...] = field(default_factory=tuple)

@dataclass(frozen=True, slots=True)
class ProvenanceMixin:
    source_result_dir: Path | None = None
    source_manifest_path: Path | None = None
```

```python
# src/flytetest/serialization.py
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping, TypeVar, get_args, get_origin, Union
import types

def serialize_value(value: Any) -> Any: ...
def deserialize_value(annotation: Any, value: Any) -> Any: ...

class SerializableDataclass:
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]): ...
```

Then:
```python
@dataclass(frozen=True, slots=True)
class ReferenceGenome(SerializableDataclass, NotesMixin, ProvenanceMixin):
    fasta_path: Path
    organism_name: str | None = None
    ...
```

---

## 6. Why this is the best fit now

- preserves the current dataclass style
- avoids adding a new dependency
- keeps planner vs asset semantics separate
- reduces maintenance burden from repeated hand-rolled serialization
- makes future typed adapter code easier to reason about

---

## 7. Additional cleanups worth doing
- centralize `InterfaceField` builders in registry.py for repeated standard inputs
- centralize common `Path | None = None` provenance assignments in planner adapters
- use explicit adapter functions for planner/asset boundary conversion instead of repeating field assignment patterns

If you want, I can next implement the concrete refactor skeleton for:
1. `src/flytetest/common_types.py`
2. `src/flytetest/serialization.py`
3. a small cleanup in planner_types.py and `types/assets.py`
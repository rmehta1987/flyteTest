Use this prompt when starting the Step A1 shared serialization module slice
or when handing it off to another session.

```text
You are continuing the FLyteTest serialization consolidation under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/checklist.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/serialization_registry_restructure_plan.md

Read the relevant repo-local guides under `.codex/`:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- This is Step A1. Step A0 (regression fixtures) must be complete before
  starting. Confirm A0 is marked complete in the checklist before proceeding.
- Three modules maintain near-identical serialize/deserialize helpers with
  distinct behavioral differences. This step creates the shared module with
  layer-specific wrappers — it does NOT rewire any existing code yet.

Key decisions already made (do not re-litigate):

- Behavioral preservation matters more than deduplication. Each layer retains
  its current round-trip semantics via layer-specific wrappers.
- Behavioral difference table:

  | Capability                    | Planner | Specs | Assets |
  |-------------------------------|---------|-------|--------|
  | Dict recursion (serialize)    | No      | Yes   | Yes    |
  | to_dict() fallback (serialize)| No      | No    | Yes    |
  | Scalar coercion (deserialize) | No      | No    | Yes    |
  | Dict recursion (deserialize)  | No      | Yes   | Yes    |

- `SerializableMixin` is a plain class (not a dataclass) to work with
  `@dataclass(frozen=True, slots=True)` consumers via MRO.

Key files to read before implementing:

- `src/flytetest/planner_types.py` lines 38-157
- `src/flytetest/specs.py` lines 22-137
- `src/flytetest/types/assets.py` lines 32-145

Task:

1. Create `src/flytetest/serialization.py` with:

   Shared primitives:
   - `_is_optional(annotation)` — shared Optional unwrapping logic (compare the
     three current implementations; they should be identical).
   - `_serialize_core(value)` — Path->str, tuple->list, dataclass field-by-field,
     scalar passthrough. The common subset all three serializers share.
   - `_deserialize_core(annotation, value)` — None/Any passthrough, Path, tuple,
     Optional unwrapping, dataclass from_dict() with field-by-field fallback.
     Common subset of all three deserializers.

   Layer-specific serialize wrappers:
   - `serialize_value_plain(value)` — for planner types: Path, tuple, dataclass
     field-by-field only. No dict recursion.
   - `serialize_value_with_dicts(value)` — for specs: adds dict recursion over
     _serialize_core.
   - `serialize_value_full(value)` — for assets: adds dict recursion + to_dict()
     fallback on nested dataclasses.

   Layer-specific deserialize wrappers:
   - `deserialize_value_strict(annotation, value)` — for specs and planner types:
     delegates to _deserialize_core without scalar coercion.
   - `deserialize_value_coercing(annotation, value)` — for assets only: adds
     scalar coercion (str/int/bool). Preserves ManifestSerializable behavior.

   Mixin:
   - `class SerializableMixin` — plain class (not dataclass), provides
     `to_dict()`/`from_dict()`.

     Design constraints (match existing pattern in specs.py, planner_types.py,
     types/assets.py):

     - `to_dict(self)` is an instance method. It calls `dataclasses.fields(self)`
       — this works because `self` IS the dataclass instance (the mixin is in
       MRO but `fields()` resolves on the concrete class).
     - `from_dict(cls, payload)` is a `@classmethod`. It calls
       `dataclasses.fields(cls)` and `get_type_hints(cls)` — same reason.
       Do NOT call `fields()` on the mixin class itself; that raises TypeError.
     - The existing serializers call module-level functions (`_serialize()`,
       `_deserialize_value()`) — NOT overridable instance/class methods.
       Follow this same pattern: each subclass mixin sets class-level attributes
       pointing to the appropriate serialize/deserialize functions:
       ```python
       class SpecSerializable(SerializableMixin):
           _serialize_fn = staticmethod(serialize_value_with_dicts)
           _deserialize_fn = staticmethod(deserialize_value_strict)
       ```
       `SerializableMixin.to_dict()` reads `self._serialize_fn`, and
       `from_dict()` reads `cls._deserialize_fn`. This avoids the
       @classmethod binding pitfall where an instance method override would
       receive `cls` as `self`.

2. Create `tests/test_serialization.py` with edge-case round-trip tests:
   - Path serialization and deserialization
   - Nested dataclass round-trips
   - Optional field handling (None and non-None)
   - Tuple field handling
   - Dict field handling (verify plain skips dicts, with_dicts handles them)
   - Scalar coercion (verify strict rejects, coercing accepts)
   - None passthrough
   - Test BOTH deserializer variants explicitly

3. Verify the A0 regression fixtures still pass (they should — no existing code
   was modified):
   `python3 -m unittest tests.test_serialization_regression -v`

4. Update `CHANGELOG.md` and `docs/dataserialization/checklist.md`.

Important constraints:

- Do NOT modify any existing serialization code in specs.py, planner_types.py,
  or types/assets.py. This step only creates the new shared module.
- The new module must be independently testable without importing from the
  three existing serializer modules.
- Use `unittest.TestCase`, not pytest.
- Do not add docstrings or type annotations beyond what is needed for clarity.

Validation:

1. `python3 -m unittest tests.test_serialization -v` — new module tests pass
2. `python3 -m unittest tests.test_serialization_regression -v` — regression fixtures unchanged
3. `python3 -m unittest discover -s tests` — full suite passes
4. `python3 -m compileall src/flytetest/serialization.py` — no syntax errors

Report back with:

- checklist items completed
- files created
- number of new test cases
- validation run summary
- any design decisions made during implementation (e.g. how _serialize_core
  handles edge cases)
```

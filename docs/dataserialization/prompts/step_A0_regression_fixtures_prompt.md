Use this prompt when starting the Step A0 serialization regression fixtures slice
or when handing it off to another session.

```text
You are beginning the FLyteTest serialization consolidation + registry restructure
under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/checklist.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/serialization_registry_restructure_plan.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- This is Step A0 — the prerequisite for all serialization rewiring (A1-A4).
- Three modules each maintain near-identical serialize/deserialize helpers with
  subtle behavioral differences. Before touching any serializer, lock current
  behavior with snapshot tests so any rewiring that changes behavior is caught
  immediately.
- The project uses `unittest` (not pytest). Run tests via
  `python3 -m unittest discover -s tests`.
- Work on the `datatypes` branch.

Key decisions already made (do not re-litigate):

- Three layers have distinct serialization behaviors that must be preserved:
  - Planner (`planner_types.py`): Path, tuple, dataclass only — no dict recursion.
  - Specs (`specs.py`): Path, tuple, dict recursion, dataclass — no to_dict() fallback.
  - Assets (`types/assets.py`): Path, tuple, dict recursion, dataclass with
    to_dict() fallback + scalar coercion on deserialize.
- Regression fixtures gate all subsequent A steps.

Key files to read before writing tests:

- `src/flytetest/planner_types.py` lines 38-157 — PlannerSerializable mixin
  and its _serialize_value/_deserialize_value helpers
- `src/flytetest/specs.py` lines 22-137 — SpecSerializable mixin and its
  _serialize/_deserialize helpers
- `src/flytetest/types/assets.py` lines 32-145 — ManifestSerializable mixin
  and its _serialize_manifest_value/_deserialize_manifest_value helpers

Task:

1. Create `tests/test_serialization_regression.py` with these snapshot tests:

   Spec layer:
   - Construct a representative spec (use an existing spec class from the
     codebase — e.g. a TaskSpec or WorkflowSpec with Path fields, Optional
     fields, nested dataclass fields, and tuple fields).
   - Serialize it to dict via `to_dict()`, assert the exact output matches a
     hardcoded expected dict.
   - Round-trip: `from_dict(to_dict(spec))` must produce field-level equality.

   Planner layer:
   - Construct a representative planner type (e.g. ReferenceGenome or ReadSet
     with Path and Optional fields).
   - Round-trip through `to_dict()`/`from_dict()`, assert field-level equality.
   - Serialize to dict and assert exact output shape.

   Asset layer:
   - Construct a representative manifest asset (e.g. a concrete asset subclass
     with Path, dict, nested dataclass, and scalar fields).
   - Serialize and assert exact JSON output.
   - Create and commit a `tests/fixtures/run_manifest_regression.json` fixture:
     Use a real manifest from `results/` as a starting point (e.g.
     `results/braker3_results_20260331_170831/run_manifest.json` — it has
     nested assets, null fields, and nested dataclass-like dicts). Sanitize
     absolute paths to relative placeholders so the fixture is portable across
     machines. The fixture must be committed to git (not generated at test
     time) so it survives `results/` being gitignored and works on clean clones.
   - Test that loading this committed fixture via the asset deserialization path
     produces the expected asset objects. This tests the reload-from-disk path,
     not just freshly serialized in-memory objects.

   Edge cases to cover:
   - None values for Optional fields
   - Path objects (must serialize to strings)
   - Tuple fields (must serialize to lists)
   - Nested dataclass fields

2. Run the full test suite to confirm the new tests pass alongside existing
   tests:
   `python3 -m unittest discover -s tests -v`

3. Update `CHANGELOG.md` with a dated entry for A0.

4. Update `docs/dataserialization/checklist.md` — mark A0 items complete.

Important constraints:

- Do not modify any existing serialization code in this step — only add tests.
- Use `unittest.TestCase`, not pytest.
- Use concrete types from the actual codebase, not synthetic test-only types.
  The point is to lock real behavior.
- `tests/fixtures/` does not exist yet — create it and commit the fixture files.
  `results/` is gitignored, so the fixture must be a committed copy (sanitized
  of absolute paths), not a symlink or runtime-generated file.
- Source a representative manifest from `results/` (many exist locally —
  braker3, protein_evidence, busco, evm_prep, agat). Pick one with nested
  assets and null fields for maximum coverage.

Validation:

1. `python3 -m unittest tests.test_serialization_regression -v` — all new tests pass
2. `python3 -m unittest discover -s tests` — full suite passes
3. `git diff --check` — no trailing whitespace

Report back with:

- checklist items completed
- files created
- number of new test cases
- validation run summary
- any surprising behavioral differences discovered between the three layers
```

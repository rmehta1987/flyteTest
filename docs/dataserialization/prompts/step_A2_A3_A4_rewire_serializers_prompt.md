Use this prompt when starting the Step A2-A4 serializer rewiring slice
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

- This covers Steps A2, A3, and A4. Steps A0 (regression fixtures) and A1
  (shared serialization module) must both be complete. Confirm in the checklist
  before proceeding.
- Each step rewires one serializer mixin to use the shared module from A1.
- The A0 regression fixtures are the behavioral safety net — they must pass
  after EACH rewiring step, not just at the end.

Key decisions already made (do not re-litigate):

- Layer-specific wrappers preserve exact current behavior per layer.
- Specs and Planner use `deserialize_value_strict` (no scalar coercion).
  Specs use `serialize_value_with_dicts`, Planner uses `serialize_value_plain`.
- Assets use `deserialize_value_coercing` and `serialize_value_full`.

Task:

Do these steps sequentially, running the regression fixtures after each one.

Step A2 — Rewire specs.py:

1. In `src/flytetest/specs.py` (use `rg "def _serialize|def _is_optional|def _deserialize"
   src/flytetest/specs.py` to find actual line numbers):
   - Remove `_serialize()`, `_is_optional()`, and `_deserialize()`.
   - Make `SpecSerializable` a thin subclass of `SerializableMixin` from
     `src/flytetest/serialization.py`.
   - Wire it to use `serialize_value_with_dicts` and `deserialize_value_strict`.

2. Run regression fixtures:
   `python3 -m unittest tests.test_serialization_regression -v`

3. Run spec-specific tests:
   `python3 -m unittest tests.test_specs tests.test_spec_artifacts tests.test_spec_executor tests.test_recipe_approval -v`

Step A3 — Rewire planner_types.py:

4. In `src/flytetest/planner_types.py` (use `rg "def _serialize|def _is_optional|def _deserialize"
   src/flytetest/planner_types.py` to find actual line numbers):
   - Remove `_serialize_value()`, `_is_optional()`, and `_deserialize_value()`.
   - Make `PlannerSerializable` a thin subclass of `SerializableMixin`.
   - Wire it to use `serialize_value_plain` and `deserialize_value_strict`.

5. Run regression fixtures:
   `python3 -m unittest tests.test_serialization_regression -v`

6. Run planner-specific tests:
   `python3 -m unittest tests.test_planner_types tests.test_planning -v`

Step A4 — Rewire types/assets.py:

7. In `src/flytetest/types/assets.py` (use `rg "def _serialize|def _is_optional|def _deserialize"
   src/flytetest/types/assets.py` to find actual line numbers):
   - Remove `_serialize_manifest_value()`, `_is_optional_manifest_type()`,
     and `_deserialize_manifest_value()`.
   - Make `ManifestSerializable` a thin subclass of `SerializableMixin`.
   - Wire it to use `serialize_value_full` and `deserialize_value_coercing`.

8. Run regression fixtures (including the manifest reload-from-disk test):
   `python3 -m unittest tests.test_serialization_regression -v`

9. Run the full test suite:
   `python3 -m unittest discover -s tests -v`

10. Verify consolidation:
    `rg "def _serialize|def _deserialize" src/flytetest/`
    — should only appear in `serialization.py` (plus unrelated helpers in
    `spec_executor.py`, `server.py`, `planning.py` that are not part of
    this refactor).

11. Update `CHANGELOG.md` and `docs/dataserialization/checklist.md`.

Important constraints:

- Do NOT skip the regression fixture run between steps. If A2 breaks a
  regression test, fix it before proceeding to A3.
- Do not change any behavior — only change where the code lives.
- Preserve the exact public API of each mixin class (to_dict, from_dict,
  field names, class hierarchy).
- Do not add docstrings, comments, or type annotations to code you didn't change.
- If a regression test fails, diagnose whether the shared module has a bug or
  the test expectation was wrong. Fix the module, not the test.

Validation:

1. `python3 -m unittest tests.test_serialization_regression -v` — all regression fixtures pass
2. `python3 -m unittest discover -s tests` — full suite passes (421+ tests)
3. `rg "def _serialize|def _deserialize" src/flytetest/` — only in serialization.py + unrelated helpers
4. `git diff --check` — no trailing whitespace

Report back with:

- checklist items completed (A2, A3, A4 separately)
- files modified
- lines of duplicated serialization code removed (approximate)
- any behavioral differences discovered during rewiring
- validation run summary
```

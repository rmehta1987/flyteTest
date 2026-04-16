Use this prompt when starting the Step B1+B2 registry package restructure slice
or when handing it off to another session. This is the largest single step in
the refactor — it converts the registry monolith into a package in one pass.

```text
You are beginning Track B of the FLyteTest serialization consolidation + registry
restructure under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/checklist.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/serialization_registry_restructure_plan.md

Read the relevant repo-local guides under `.codex/`:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- This covers Steps B1 and B2 as a single atomic change. Track B is
  independent of Track A and can proceed in parallel.
- The current `src/flytetest/registry.py` is a 2679-line monolith with 73
  entries + 3 parallel dicts + query functions. This step replaces it with a
  package of 7 family files + types + init.
- Work on the `refactor/serialization-registry` branch.

Why B1+B2 are atomic:

  Splitting these into separate commits would create a dangerous intermediate
  state: a `_registry_legacy.py` file at the package level that re-exports
  through `registry/__init__.py`. If the session stalls between B1 and B2,
  or CI runs on the intermediate state, the legacy file becomes a confusing
  artifact that invites accidental direct imports. The package restructure
  must go from monolith → package in one commit with no intermediate file.

Key decisions already made (do not re-litigate):

- Plain data (tuples of RegistryEntry dataclasses) organized by pipeline family
  in a package. No decorators, no metaclasses, no import-order tricks.
- `showcase_module: str = ""` is added to `RegistryEntry` (not to
  `RegistryCompatibilityMetadata`). MCP exposure is a separate concern from
  planner/type-graph behavior.
- `RegistryEntry.to_dict()` currently uses `asdict(self)`. Adding
  `showcase_module` changes the payload shape. Override `to_dict()` to exclude
  `showcase_module` from the serialized output.
- 73 entries = 57 tasks + 16 workflows, split into 7 family files.
- Each family file exports a tuple of RegistryEntry constructions.
- `__init__.py` concatenates them and provides query functions.

Key files to read before implementing:

  Read `src/flytetest/registry.py` in full. Line numbers below are approximate
  (from plan-writing time; M21c-M26 modified this file since). Use `rg` to
  locate the actual positions:

  - Dataclass definitions (Category, InterfaceField, RegistryCompatibilityMetadata,
    RegistryEntry) — near top of file.
    `rg "^class (Category|InterfaceField|RegistryCompatibility|RegistryEntry)" src/flytetest/registry.py`
  - RegistryEntry.to_dict() — uses `asdict(self)`.
    `rg "def to_dict" src/flytetest/registry.py`
  - All 73 RegistryEntry constructions — bulk of the file.
  - 3 parallel dicts to fold:
    `rg "_WORKFLOW_COMPATIBILITY_METADATA|_WORKFLOW_LOCAL_RESOURCE_DEFAULTS|_WORKFLOW_SLURM_RESOURCE_HINTS" src/flytetest/registry.py`
  - Merge function to eliminate:
    `rg "_backfill_workflow_compatibility_metadata|_with_resource_defaults" src/flytetest/registry.py`
  - Query functions (list_entries, get_entry, get_pipeline_stages) — near end.
    `rg "^def (list_entries|get_entry|get_pipeline_stages)" src/flytetest/registry.py`

Task:

Phase 1 — Create the package structure and types:

1. Create the package directory:
   ```
   src/flytetest/registry/
       __init__.py
       _types.py
   ```

2. In `_types.py`, move from `registry.py`:
   - `Category` type alias (line 15)
   - `InterfaceField` dataclass (line 19)
   - `RegistryCompatibilityMetadata` dataclass (line 32)
   - `RegistryEntry` dataclass (line 54)
   - Add `showcase_module: str = ""` field to `RegistryEntry`
   - Override `to_dict()` to exclude `showcase_module` from the output:
     ```python
     def to_dict(self) -> dict:
         d = asdict(self)
         d.pop("showcase_module", None)
         return d
     ```

Phase 2 — Create family files with self-contained entries:

3. Create the 7 family files, each with a tuple of self-contained entries.
   Work one file at a time. After each file, run `python3 -m compileall`
   on that file to catch syntax errors early.

   | File | Tuple name | Entry count |
   |---|---|---|
   | `_transcript_evidence.py` | `TRANSCRIPT_EVIDENCE_ENTRIES` | 8 |
   | `_consensus.py` | `CONSENSUS_ENTRIES` | 16 |
   | `_protein_evidence.py` | `PROTEIN_EVIDENCE_ENTRIES` | 6 |
   | `_annotation.py` | `ANNOTATION_ENTRIES` | 5 |
   | `_evm.py` | `EVM_ENTRIES` | 12 |
   | `_postprocessing.py` | `POSTPROCESSING_ENTRIES` | 21 |
   | `_rnaseq.py` | `RNASEQ_ENTRIES` | 5 |

   For each entry that has compatibility metadata in
   `_WORKFLOW_COMPATIBILITY_METADATA`, fold it inline. For entries that have
   resource defaults in `_WORKFLOW_LOCAL_RESOURCE_DEFAULTS` and
   `_WORKFLOW_SLURM_RESOURCE_HINTS`, fold those into
   `execution_defaults.resources` and `execution_defaults.slurm_resource_hints`
   within the compatibility metadata.

   Each family file imports only from `flytetest.registry._types`.

   Family file assignment — see the plan doc for the full mapping table.

Phase 3 — Wire up __init__.py and delete the monolith:

4. In `__init__.py`:
   - Re-export everything from `_types.py`
   - Import all 7 family tuples
   - Concatenate into `REGISTRY_ENTRIES`
   - Build `_REGISTRY` lookup dict
   - Move query functions (`list_entries`, `get_entry`, `get_pipeline_stages`)
     from `registry.py` into `__init__.py`

5. Delete `src/flytetest/registry.py` (the monolith).
   Do NOT rename it to `_registry_legacy.py` — go directly from monolith to
   package with no intermediate file.

Phase 4 — Verify:

6. Verify all existing imports still work:
   `python3 -c "from flytetest.registry import REGISTRY_ENTRIES, list_entries, get_entry, RegistryEntry, InterfaceField, RegistryCompatibilityMetadata, Category; print(f'{len(REGISTRY_ENTRIES)} entries loaded')"`

7. Verify entry count and to_dict() stability:
   ```python
   python3 -c "
   from flytetest.registry import REGISTRY_ENTRIES
   assert len(REGISTRY_ENTRIES) == 73, f'Expected 73, got {len(REGISTRY_ENTRIES)}'
   for e in REGISTRY_ENTRIES:
       d = e.to_dict()
       assert 'showcase_module' not in d, f'{e.name} leaks showcase_module'
   print('73 entries, to_dict() stable')
   "
   ```

8. Verify the parallel dicts are eliminated:
   `rg "_WORKFLOW_COMPATIBILITY_METADATA|_WORKFLOW_LOCAL_RESOURCE|_WORKFLOW_SLURM" src/flytetest/`
   — must return 0 hits.

9. Verify `get_pipeline_stages("annotation")` returns the same order as before.

10. Verify no legacy file exists:
    `ls src/flytetest/_registry_legacy.py 2>&1`
    — must return "No such file"

11. Run the full test suite:
    `python3 -m unittest discover -s tests -v`

12. Update `CHANGELOG.md` and `docs/dataserialization/checklist.md`.

Important constraints:

- All existing `from flytetest.registry import ...` statements must still work
  without modification in any consuming file. These are the known consumers:
  - `src/flytetest/__init__.py`
  - `src/flytetest/composition.py`
  - `src/flytetest/server.py`
  - `src/flytetest/spec_executor.py`
  - `src/flytetest/pipeline_tracker.py`
  - `src/flytetest/planning.py`
  - `tests/test_composition.py`
  - `tests/test_pipeline_tracker.py`
  - `tests/test_registry.py`
  - `tests/test_specs.py`
- Do NOT create a `_registry_legacy.py` intermediate file. The monolith is
  deleted in the same commit the package replaces it.
- Entry order within each family file should follow pipeline_stage_order
  (workflows first, then their constituent tasks grouped logically).
- Do not change any entry data — only restructure where it lives and fold
  inline metadata. The to_dict() output for every entry must be identical
  to what existed before.
- Do not add `showcase_module` values yet — that happens in B3.
- `to_dict()` output must not include `showcase_module` — downstream consumers
  (tests, MCP tools) depend on the current payload shape.

Validation:

1. `python3 -m compileall src/flytetest/` — no import errors
2. `python3 -m unittest discover -s tests` — full suite passes
3. `python3 -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` — 73
4. `rg "_WORKFLOW_COMPATIBILITY_METADATA|_WORKFLOW_LOCAL_RESOURCE|_WORKFLOW_SLURM" src/flytetest/` — 0 hits
5. `rg "from flytetest.registry import" src/flytetest/ tests/` — no broken imports
6. `ls src/flytetest/_registry_legacy.py 2>&1` — no such file

Report back with:

- checklist items completed (B1 and B2 together)
- files created and deleted
- entry count per family file (verify totals to 73)
- confirmation that to_dict() output is identical for all entries
- validation run summary
```

Use this prompt when starting the Step B3-B4 MCP and server derivation slice
or when handing it off to another session.

```text
You are continuing Track B of the FLyteTest registry restructure under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/checklist.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/serialization_registry_restructure_plan.md

Read the relevant repo-local guides under `.codex/`:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- This covers Steps B3 and B4. Step B1+B2 (registry package restructure) must
  be complete. Confirm in the checklist before proceeding.
- B3 derives ShowcaseTarget entries from registry `showcase_module` fields
  instead of hardcoding them in mcp_contract.py.
- B4 simplifies the handler dispatch map in server.py using the derived tuples.

Key decisions already made (do not re-litigate):

- 4 named constants MUST be preserved as explicit policy seams in
  mcp_contract.py — they are used as branch points in planning.py and server.py:

  | Constant | Used in |
  |---|---|---|
  | SUPPORTED_WORKFLOW_NAME | planning.py (prompt classification, BRAKER3 evidence guard, input extraction, assumptions), server.py (default workflow, evidence validation) |
  | SUPPORTED_PROTEIN_WORKFLOW_NAME | planning.py (protein workflow classification, input extraction, assumptions) |
  | SUPPORTED_TASK_NAME | planning.py (task intent classification, assumptions) |
  | SUPPORTED_BUSCO_FIXTURE_TASK_NAME | planning.py (BUSCO fixture goal construction) |

- The other 8 SUPPORTED_*_NAME constants (BUSCO_WORKFLOW, EGGNOG, AGAT x3,
  TABLE2ASN, FASTQC, GFFREAD) can be replaced by derived tuples.
- TASK_PARAMETERS (4 entries in server.py) stays manual — MCP tool-validation
  schemas, not biological metadata.

Key files to read (line numbers are approximate — from plan-writing time,
use `rg` to find actual positions):

- `src/flytetest/mcp_contract.py` — ShowcaseTarget class, SUPPORTED_*
  constants, hardcoded ShowcaseTarget constructions.
  `rg "class ShowcaseTarget|SUPPORTED_.*_NAME" src/flytetest/mcp_contract.py`
- `src/flytetest/server.py` — imports of SUPPORTED_* constants,
  `_local_node_handlers()` function.
  `rg "SUPPORTED_|def _local_node_handlers" src/flytetest/server.py`
- `src/flytetest/planning.py` — imports of the 4 policy constants.
  `rg "SUPPORTED_" src/flytetest/planning.py`

Task:

Step B3 — Derive mcp_contract.py showcase targets:

1. In each registry family file, add `showcase_module` values for the entries
   that are currently exposed as ShowcaseTargets. Cross-reference the 12
   hardcoded ShowcaseTarget entries in mcp_contract.py to determine which
   entries need showcase_module set.

2. In `src/flytetest/mcp_contract.py`:
   - Keep the 4 named policy constants (SUPPORTED_WORKFLOW_NAME,
     SUPPORTED_PROTEIN_WORKFLOW_NAME, SUPPORTED_TASK_NAME,
     SUPPORTED_BUSCO_FIXTURE_TASK_NAME) as explicit string assignments.
   - Add `_resolve_source_path()` helper.
   - Derive `SHOWCASE_TARGETS` from `REGISTRY_ENTRIES` where `showcase_module`
     is set.
   - `SUPPORTED_TARGET_NAMES`, `SUPPORTED_WORKFLOW_NAMES`, and
     `SUPPORTED_TASK_NAMES` already exist as derived tuples (currently at
     lines 178-180). Do NOT add duplicate definitions — replace the
     derivation source (SHOWCASE_TARGETS becomes registry-derived) and the
     existing tuple derivations will automatically reflect the new source.
   - Delete the 12 hardcoded ShowcaseTarget(...) blocks.
   - Delete the 8 replaceable SUPPORTED_*_NAME constants.
   - Update SHOWCASE_LIMITATIONS: the first string contains a hardcoded list of
     target names. Replace only the name list portion with the derived
     SUPPORTED_TARGET_NAMES (e.g. `", ".join(SUPPORTED_TARGET_NAMES)`), but
     keep the surrounding prose ("The MCP recipe surface executes ... through
     explicit local handlers.") as curated text. Review the generated output
     to ensure it reads naturally — if it looks mechanical, keep it as a
     manually curated string that is updated alongside target changes.

3. Add a safety test that asserts the derived SUPPORTED_TARGET_NAMES matches
   the expected set (hardcode the expected tuple in the test to catch accidental
   additions or removals):
   ```python
   def test_supported_target_names_match_expected_set(self):
       from flytetest.mcp_contract import SUPPORTED_TARGET_NAMES
       expected = (...)  # hardcoded expected tuple
       self.assertEqual(set(SUPPORTED_TARGET_NAMES), set(expected))
   ```

4. Run MCP-specific tests:
   `python3 -m unittest tests.test_server tests.test_mcp_prompt_flows -v`

Step B4 — Derive server.py handler dispatch:

5. In `src/flytetest/server.py`:
   - Update imports: remove the 8 deleted SUPPORTED_*_NAME constants, import
     SUPPORTED_WORKFLOW_NAMES and SUPPORTED_TASK_NAMES instead.
   - Replace the 8 explicit workflow name constants in `_local_node_handlers()`
     with:
     ```python
     return {
         **{name: workflow_handler for name in SUPPORTED_WORKFLOW_NAMES},
         **{name: task_handler for name in SUPPORTED_TASK_NAMES},
     }
     ```
   - TASK_PARAMETERS stays manual (4 entries).

6. Run server tests:
   `python3 -m unittest tests.test_server -v`

7. Run the full test suite:
   `python3 -m unittest discover -s tests -v`

8. Verify ShowcaseTarget derivation:
   `rg "ShowcaseTarget(" src/flytetest/mcp_contract.py`
   — should return 0 hits (all derived from registry).

9. Update `CHANGELOG.md` and `docs/dataserialization/checklist.md`.

Important constraints:

- Do NOT delete the 4 named policy constants. planning.py branches on them
  by identity — removing them breaks prompt classification.
- Do NOT modify planning.py in this step. Only mcp_contract.py and server.py.
- The derived set of supported targets must be identical to what existed before.
  No accidental additions or removals.
- Target-specific validation guards, stage-to-input translation logic, and
  execution policy in server.py remain manual. Only the handler map changes.

Validation:

1. `python3 -m unittest tests.test_server tests.test_mcp_prompt_flows -v` — all pass
2. `python3 -m unittest discover -s tests` — full suite passes
3. `rg "ShowcaseTarget(" src/flytetest/mcp_contract.py` — 0 hits
4. Verify the 4 policy constants still exist:
   `rg "SUPPORTED_WORKFLOW_NAME =|SUPPORTED_PROTEIN_WORKFLOW_NAME =|SUPPORTED_TASK_NAME =|SUPPORTED_BUSCO_FIXTURE_TASK_NAME =" src/flytetest/mcp_contract.py`

Report back with:

- checklist items completed (B3, B4 separately)
- files modified
- number of ShowcaseTarget blocks removed
- number of SUPPORTED_*_NAME constants removed vs preserved
- confirmation that derived target set matches expected set
- validation run summary
```

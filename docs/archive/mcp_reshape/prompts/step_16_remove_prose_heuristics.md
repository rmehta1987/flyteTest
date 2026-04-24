Use this prompt when starting Step 16 or when handing it off to another session.

Model: Opus recommended — heuristic-removal surgery has high surprise potential (dead branches, over-preserved helpers, test fallout in unexpected places).

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§5)

Context:

- This is Step 16. Remove prose-parsing helpers from `src/flytetest/planning.py`.
- `plan_request` (free-text preview) still attempts supported NL planning via
  structured match against `biological_stage` / `name`, and via
  `_try_composition_fallback` on structured planning goals. What goes away
  is prose EXTRACTION of paths, execution profiles, and runtime images.

Key decisions already made (do not re-litigate):

- `_try_composition_fallback` is preserved unchanged.
- M15 P2 approval gating is preserved: composed novel DAGs set
  `requires_user_approval=True`.

Task:

1. Delete from `planning.py`:
   - `_extract_prompt_paths` (lines 254-414 in the current tree)
   - `_extract_braker_workflow_inputs`
   - `_extract_protein_workflow_inputs`
   - `_extract_execution_profile` (regex)
   - `_extract_runtime_images` (regex)
   - `_classify_target` (keyword scoring)
   - M18 BUSCO keyword branch in biological-goal derivation (lines 921-985).

2. Reshape `plan_typed_request` to a structured-only entrypoint per the
   master plan §5 code block.

3. `plan_request` (the free-text MCP tool) keeps working: structured match
   against registered entries, then composition fallback, then a structured
   decline with the three recovery channels (§10) if both fail.

4. The empty-prompt advisory (§9) — append a non-fatal limitation to the
   reply when `source_prompt == ""` — lives here or in the reshaped run
   tools. Implement in whichever sits naturally; most likely in
   `plan_typed_request`.

Tests:

- Previously prose-parsed flows either now work via structured calls
  (update the test to the structured shape) or decline cleanly.
- Add a test that an empty `source_prompt` surfaces the advisory in
  `limitations`.

Verification:

- `python -m compileall src/flytetest/planning.py`
- `rg -n "_extract_prompt_paths|_extract_braker_workflow_inputs|_extract_protein_workflow_inputs|_classify_target|_extract_execution_profile|_extract_runtime_images" src/flytetest/` → zero hits
- `pytest tests/`

Commit message: "planning: remove prose heuristics; plan_typed_request is structured-only".

Then mark Step 16 Complete in docs/mcp_reshape/checklist.md.
```

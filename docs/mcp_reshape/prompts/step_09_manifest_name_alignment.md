Use this prompt when starting Step 09 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3b — registry-manifest name alignment sweep)

Context:

- This is Step 09. Per-task decision: either rename the manifest key or
  update the registry declaration. Registry is typically the stale side,
  so prefer updating it. Touch each `src/flytetest/registry/_<family>.py`
  + the corresponding task module under `src/flytetest/tasks/`.

Key decisions already made (do not re-litigate):

- Registry is the public contract; the manifest may carry additional internal
  audit keys (debug scalars, intermediate-file pointers) without polluting
  scientist-facing replies. Named-output projection (Step 11) silently omits
  undeclared manifest keys.
- Conditional outputs (e.g. GATK TBI when `emit_ref_confidence != GVCF`) get
  `required=False` on the registry declaration (Step 01 added the flag).

Task:

1. For every showcased entry, confirm `entry.outputs[*].name` matches what
   the corresponding task's `manifest["outputs"]` actually contains. Known
   divergence: BUSCO registry declares `results_dir` while the manifest
   carries `run_dir`, `short_summary`, `full_table`, `summary_notation`.

2. Reconcile:
   - If the manifest name is stable and well-known, rename the registry
     declaration to match.
   - If the registry name is better (e.g. `gvcf_path` vs `gvcf`), update the
     task to write under the registry's name.
   - Flag any truly optional outputs with `required=False`.

3. Update inline task docstrings to list the manifest keys they write.

Tests:

- Adjust any tests that assert registry output names so they match the
  reconciled state.
- Step 10 exports `MANIFEST_OUTPUT_KEYS` per task module; Step 11 locks the
  contract so future divergence fails CI.

Verification:

- `python -m compileall src/flytetest/`
- `pytest tests/`

Commit message: "registry+tasks: align InterfaceField.name with manifest output keys".

Then mark Step 09 Complete in docs/mcp_reshape/checklist.md.
```

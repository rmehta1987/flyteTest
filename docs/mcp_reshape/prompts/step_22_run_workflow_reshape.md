Use this prompt when starting Step 22 or when handing it off to another session.

Model: Opus recommended — symmetric BC break with Step 21; any divergence between the two tools breaks the bundle-spread contract (`run_workflow(..., **bundle)` must read the same as `run_task(..., **bundle)`).

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md  (hard constraints: freeze before execute; never modify frozen artifacts)
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§8.7 coordinated migration)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3, §3b, §3g, §3i — run_workflow reshape symmetric with run_task)

Context:

- This is Step 22. Depends on Steps 01-21. Mirrors Step 21 one-to-one:
  `run_workflow` takes the same shape as `run_task`
  (bindings + inputs + resources + execution_profile + runtime_images +
  tool_databases + source_prompt + dry_run) so a bundle spreads identically
  into either tool.

Key decisions already made (do not re-litigate):

- Symmetric surface is the contract — do NOT diverge (§3 "Why symmetric").
- Preserve the BRAKER3 evidence-check limitation at `server.py:934-949`, but
  generalize it so the satisfying evidence can come from either
  `inputs.protein_fasta_path` (legacy scalar) or `bindings.ProteinEvidenceSet`
  / `bindings.ReadSet` (typed form). Call the helper
  `_braker_has_evidence(bindings, inputs)`.
- Use the same `_execute_run_tool(...)` wrapper from Step 19 so typed
  resolver exceptions translate to `PlanDecline`.
- `dry_run=True` behavior is identical to `run_task`: freeze the artifact to
  disk, skip executor dispatch, return `DryRunReply` (§3i).
- Named outputs via `_collect_named_outputs(entry, run_record_path)` — same
  projection rule as `run_task`.
- `execution_status` + `exit_status` populated from the run record on local;
  `"success"` + `None` on slurm submit (terminal state via monitor_slurm_job).

Task:

1. Rewrite the body at `server.py:869` matching §3 of the master plan.
   Mirror the Step 21 body almost verbatim — only the entry-contract,
   BRAKER3 guard, and `SUPPORTED_WORKFLOW_NAMES` lookup differ.

2. Factor out `_braker_has_evidence(bindings, inputs) -> bool` so the
   guard reads cleanly. Accept satisfaction from either shape; the legacy
   scalar path should keep working for a bundle that only fills `inputs`.

3. Return a `RunReply` (asdict at boundary) with `workflow_name` populated
   (not `task_name`). Keep every other field identical to `run_task`.

4. Accept `runner: Any = subprocess.run` as the test seam, same as
   `run_task`; do not expose it in the MCP schema docstring.

Tests to add (tests/test_server.py):

- Bundle spread into run_workflow succeeds (same bundle that spreads into
  run_task in Step 21 tests).
- BRAKER3 with only `bindings.ProteinEvidenceSet` satisfies the evidence
  guard (legacy scalar path unreachable).
- BRAKER3 with only legacy `inputs.protein_fasta_path` still satisfies the
  guard (BC path preserved at call-site level even as the MCP shape changes).
- BRAKER3 with neither form declines with the evidence-required limitation.
- Unknown binding type decline.
- Freeze happens: `.runtime/specs/<id>.json` exists after a successful call.
- Named outputs dict keyed by registry (names, no paths list).
- Empty `source_prompt` → advisory in `limitations`.
- `dry_run=True` → artifact exists, no run record, returns `DryRunReply`.
- Chained dry_run → `run_slurm_recipe(artifact_path=...)` executes with the
  unchanged artifact bytes.
- Local executor non-zero exit → `supported=True`, `execution_status="failed"`.

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`
- `rg -n 'run_workflow\(' src/ tests/` — every hit uses the new shape.

Commit message: "server: reshape run_workflow (symmetric with run_task; freeze, named outputs, dry_run)".

Then mark Step 22 Complete in docs/mcp_reshape/checklist.md.
```

Use this prompt when starting Step 26 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§12 — call-site sweep for the BC migration)

Context:

- This is Step 26. Depends on Steps 21 (`run_task` reshape) and 22
  (`run_workflow` reshape). The plan rejects a compatibility shim — every
  call site breaks the moment the signature changes. This step is the
  coordinated sweep that makes CI green again.

Key decisions already made (do not re-litigate):

- No back-compat shim for the flat `inputs=...` shape. Every caller moves
  to `bindings + inputs + resources + execution_profile + runtime_images +
  tool_databases + source_prompt` in the same commit series.
- Sweep is a single atomic-enough commit (or tight series) — partial
  migration is not acceptable; the tree stays green.
- The verification gates in the master plan (`rg -n 'run_task\(|
  run_workflow\(' src/ tests/ docs/ scripts/` → zero hits of the old shape)
  are acceptance criteria for this step.

Task:

1. Inventory every call site via
   `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/`. Each
   hit is a review item.

2. Categorize hits:
   - Tests under `tests/` — rewrite to the new typed shape. Prefer
     exercising via a bundle fixture when possible so the test doubles as
     a bundle-spread integration test.
   - Smoke scripts under `scripts/` — update; run the smoke to confirm.
   - Doc examples under `docs/` — update the snippet to show the new shape.
     The docs rewrite in Step 29 adds narrative; Step 26 only fixes the
     syntax so no stale example survives.
   - Active planning docs under `docs/realtime_refactor_plans/` — update
     quoted shapes. Do NOT edit archived plans.

3. Confirmed test files to touch (grep to find any others):
   - `tests/test_server.py`
   - `tests/test_mcp_prompt_flows.py`
   - `tests/test_planning.py`
   - `tests/test_spec_executor.py`
   (Plus any test the grep surfaces — don't assume this list is complete.)

4. After the sweep, re-run the grep. If any hit still uses the old shape,
   fix it or document why it must stay (e.g. a changelog snippet quoting
   historical state — quote it inside a fenced code block tagged as old-
   shape, not as executable example).

Tests / verification (no new tests — this step fixes existing ones):

- `pytest tests/` — green.
- `rg -n "inputs\s*=\s*\{" tests/ | rg 'run_task|run_workflow'` — zero hits
  (approximate — visual inspection of residual hits is fine).
- `rg -n 'run_task\(|run_workflow\(' src/ tests/ docs/ scripts/` — every
  surviving hit uses the new shape.
- Any smoke script updated under `scripts/` runs end-to-end against a
  `tmp_path`-rooted fixture without errors.

Commit message: "sweep: migrate run_task/run_workflow call sites to typed shape".

Then mark Step 26 Complete in docs/mcp_reshape/checklist.md.
```

Use this prompt when starting Step 27 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md  (§6.2 MCP tool surface)
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§6 — tool descriptions reframe)

Context:

- This is Step 27. Depends on Steps 21-25 (the server surface is now stable).
  Reframes the public tool descriptions in `mcp_contract.py` around "the
  scientist's experiment loop" so a client-side LLM reading the tool list
  picks the right entrypoint without inferring biology from prose.

Key decisions already made (do not re-litigate):

- Primary group = experiment loop: `list_entries`, `list_bundles`,
  `load_bundle`, `run_task`, `run_workflow`.
- Secondary group = inspect-before-execute (power-user):
  `prepare_run_recipe`, `run_local_recipe`, `run_slurm_recipe`,
  `approve_composed_recipe`, `validate_run_recipe`.
- Tertiary group = lifecycle (unchanged): `monitor_slurm_job`,
  `cancel_slurm_job`, `retry_slurm_job`, `wait_for_slurm_job`,
  `fetch_job_log`, `get_run_summary`, `inspect_run_result`,
  `get_pipeline_status`, `list_available_bindings`.
- Every `run_task` / `run_workflow` / `run_slurm_recipe` description carries
  a one-sentence note on resource-hint handoff (DESIGN §7.5):
  `execution_defaults["slurm_resource_hints"]` supplies sensible defaults
  for `cpu` / `memory` / `walltime`, but `queue` and `account` must come
  from the user — the server never invents them.
- Module docstring cross-references `mcp_replies.py` as the canonical
  reply-shape definition (so a reader discovers `RunReply`, `PlanDecline`,
  `PlanSuccess`, `DryRunReply` etc. in one place).

Task:

1. Rewrite every tool description in `mcp_contract.py` so the first
   sentence frames the tool in experiment-loop / inspect-before-execute /
   lifecycle terms.

2. Ensure group membership is discoverable — either via a module-level
   constant listing the groups, or via an explicit marker in each
   description. Whatever you choose, keep it greppable.

3. On `run_task`, `run_workflow`, `run_slurm_recipe`: append the
   queue/account handoff sentence verbatim across all three so tooling
   that surfaces tool descriptions to an LLM stays consistent.

4. On `validate_run_recipe`, `list_bundles`, `load_bundle`: write
   descriptions that match the actual signatures landed in Steps 24 / 25.

5. Module docstring: add a "Canonical reply shapes live in
   `src/flytetest/mcp_replies.py`" pointer.

Tests to add (tests/test_mcp_contract.py):

- Every tool registered on the server has a description in
  `mcp_contract.py` (no orphans).
- No description references removed helpers (`_extract_prompt_paths`,
  `_classify_target`, etc.) or the old flat-`inputs` shape.
- `run_task` / `run_workflow` / `run_slurm_recipe` descriptions each
  contain the queue/account handoff sentence.
- `list_tools()` order reflects the experiment-loop → inspect →
  lifecycle grouping (or group metadata is queryable).

Verification:

- `python -m compileall src/flytetest/mcp_contract.py`
- `pytest tests/test_mcp_contract.py`
- `rg -n 'plan_typed_request\(|_extract_prompt_paths|_classify_target' src/flytetest/mcp_contract.py` → zero hits.

Commit message: "mcp_contract: reframe tool descriptions around the experiment loop".

Then mark Step 27 Complete in docs/mcp_reshape/checklist.md.
```

Use this prompt when starting Step 18 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3e — operator-side logging)

Context:

- This is Step 18. Narrow error-path logging so a shared-deploy operator
  has a trail when something unexpected happens. Scientists still get their
  answers from the MCP reply (typed replies + named outputs + decline
  routing) and disk-persisted run record; they do not read server stderr.
- Does NOT touch sbatch stdout/stderr, job-side manifests, or any lifecycle
  observability. Slurm job-side debugging stays via existing tools.

Key decisions already made (do not re-litigate):

- `_LOG = logging.getLogger(__name__)` per module (mirrors the existing
  `slurm_monitor.py` pattern).
- No happy-path logs. No correlation IDs beyond `recipe_id`.
- Exception logs re-raise, not swallow.

Task:

Add log emission at three sites:

| Site | Level | Fields |
|---|---|---|
| Uncaught exception in `_materialize_bindings` / `artifact_from_typed_plan` / executor dispatch | `ERROR` | `recipe_id` (if assigned), `tool_name`, exception type, traceback |
| `SlurmWorkflowSpecExecutor.submit` short-circuit from `check_offline_staging` | `INFO` | `recipe_id`, finding count, `shared_fs_roots` |
| `$ref` binding resolution failure in `_materialize_bindings` | `WARNING` | `recipe_id` (pending), offending `run_id`, `output_name`, reason |

The ERROR site is in `_execute_run_tool` (Step 19) — coordinate ordering.
The INFO site is in the executor preflight (Step 23). The WARNING site is
in `_materialize_bindings` (Steps 13-14). If Step 18 lands BEFORE those
others, add the logger setup and emit calls at their eventual positions
(marked TODO: wire in Step XX); safer: order Step 18 after 13/14 and
BEFORE 19/23.

Tests:

- `caplog` assertions at each site (INFO line present + no sbatch call;
  WARNING line present with the offending run_id; ERROR line present for
  a simulated propagate).

Verification:

- `python -m compileall src/flytetest/`
- `pytest tests/` (the relevant logging tests pass)

Commit message: "server+executor+resolver: error-path logging with recipe_id context".

Then mark Step 18 Complete in docs/mcp_reshape/checklist.md.
```

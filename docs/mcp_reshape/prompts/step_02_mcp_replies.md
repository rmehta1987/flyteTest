Use this prompt when starting Step 02 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/CLAUDE.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3d, with §3g / §3i / §3j cross-references for field additions)

Read the relevant repo-local guides under `.codex/`:

- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/documentation.md

Context:

- This is Step 02. It is pure-additive — no existing code is touched.
- This module becomes the canonical source of truth for MCP reply shapes.
  Later steps (18-25) import from it instead of constructing dict literals.

Key decisions already made (do not re-litigate):

- FastMCP serializes dataclasses fine via `asdict()`; tool bodies return a
  dataclass instance and a thin wrapper at the tool boundary calls `asdict()`
  if needed. JSON wire shape is unchanged from the dict-literal version.
- Lifecycle-tool replies (monitor_slurm_job, inspect_run_result,
  get_pipeline_status, etc.) are NOT migrated here — they keep their current
  dict shapes. Migration is a trivial follow-up if the pattern proves out.

Task:

1. Create `src/flytetest/mcp_replies.py` with the dataclasses defined in
   §3d of the master plan: `SuggestedBundle`, `SuggestedPriorRun`, `RunReply`
   (including §3g's `execution_status` + `exit_status` fields), `PlanDecline`,
   `PlanSuccess` (including §3j's `artifact_path` + `suggested_next_call` +
   `composition_stages`), `BundleAvailabilityReply`, `ValidateRecipeReply`,
   `DryRunReply` (from §3i).

2. All dataclasses are `@dataclass(frozen=True)`. Tuples, not lists, for
   collections. Every field has a type annotation.

3. Module docstring explains the asdict-at-the-boundary pattern and that
   this is the one source of truth for the MCP wire format across the
   reshaped surface.

Tests to add (tests/test_mcp_replies.py):

- Construction + asdict round-trip for every dataclass.
- `RunReply` carries `task_name` OR `workflow_name` but never both non-empty
  (contract test — not enforced by type system).
- `PlanDecline` defaults all three recovery channels to empty tuples.

Verification:

- `python -m compileall src/flytetest/mcp_replies.py`
- `pytest tests/test_mcp_replies.py`

Commit message: "mcp_replies: add typed reply dataclasses for reshape".

Then mark Step 02 Complete in docs/mcp_reshape/checklist.md.
```

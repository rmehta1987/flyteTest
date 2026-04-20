Use this prompt when starting Step 20 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§10 — structured decline routing)

Context:

- This is Step 20. Depends on Steps 02 (PlanDecline), 04 (bundles + availability),
  14 ($ref via durable index). Extends `_limitation_reply` /
  `_unsupported_target_reply` (or their equivalents) to populate three
  recovery channels whenever the decline names a registered entry and its
  pipeline family.

Key decisions already made (do not re-litigate):

- `suggested_bundles` filters out unavailable bundles (no "try this" pointing
  at a broken starter kit).
- `suggested_prior_runs` reads the durable asset index for entries whose
  `produced_planner_types` match a planner type the declined target accepts.
- `next_steps` is a tuple of human-readable strings combining the above
  with generic recovery options.

Task:

1. Refactor `_limitation_reply(target, limitation, *, pipeline_family=None)`
   (and `_unsupported_target_reply`) to:
   - Query `bundles.list_bundles(pipeline_family=...)`, keep only
     bundles whose `applies_to` includes the target AND `available=True`.
   - Query the durable asset index for prior runs whose
     `produced_planner_types` overlap with the target's
     `accepted_planner_types`. Return them as `SuggestedPriorRun` entries.
   - Compose `next_steps` from the two above plus generic strings
     ("reformulate the request", "call list_available_bindings()").
   - Return a `PlanDecline` instance (asdict at tool boundary).

2. Use the new helpers anywhere the old dict-literal decline pattern was
   constructed.

Tests to add (tests/test_server.py — decline routing block):

- Decline for BRAKER3 with no inputs returns all three channels populated.
- Decline with no available bundle returns only `next_steps` populated for
  bundles.
- Prior-run suggestion includes a `$ref`-shaped hint in `hint` field.

Verification:

- `python -m compileall src/flytetest/server.py`
- `pytest tests/test_server.py`

Commit message: "server: structured decline routing (bundles/prior-runs/next-steps)".

Then mark Step 20 Complete in docs/mcp_reshape/checklist.md.
```

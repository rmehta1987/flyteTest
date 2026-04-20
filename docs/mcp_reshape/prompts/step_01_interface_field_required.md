Use this prompt only when auditing or backfilling Step 01 on the current MCP
reshape branch.

Status on this branch:

- `src/flytetest/registry/_types.py` already includes
  `InterfaceField.required: bool = True`.
- The `InterfaceField` docstring already explains the required-vs-optional
  output distinction for later MCP reply shaping.
- `docs/mcp_reshape/checklist.md` already marks Step 01 Complete.

That means Step 01 is no longer a fresh implementation task. If this prompt is
used again, the goal is to verify or backfill any missing coverage without
reopening the design decision.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/CLAUDE.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3b)

Read the relevant repo-local guides under `.codex/`:

- /home/rmeht/Projects/flyteTest/.codex/registry.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md

Context:

- Step 01 is already implemented in code on the active branch.
- Treat this as a verification / backfill pass only.
- It remains the smallest foundation change and unblocks Step 21
  (run_task reshape) and Step 22 (run_workflow reshape), which use the flag
  to surface required-vs-optional output advisories in MCP replies.

Key decision already made (do not re-litigate):

- Default is `required=True` so every existing InterfaceField call site
  keeps current behavior. Only conditional outputs (e.g. GATK TBI in
  non-GVCF mode) explicitly set `required=False`.

Task:

1. Verify that `required: bool = True` remains the fourth field on
  `InterfaceField` in `src/flytetest/registry/_types.py`, and that the
  docstring still explains the role the flag plays in MCP replies
  (prominent-vs-soft advisory when a declared output is absent from a run
  manifest).

2. Add or preserve one focused round-trip test in `tests/test_registry.py`
  confirming that the default `required=True` value and an explicit
  `required=False` both serialize through `RegistryEntry.to_dict()`.

3. Do NOT mark any existing fields `required=False` in this step — the
  registry-wide sweep for conditional outputs is Step 09 (name alignment)
  and downstream steps. This step stays purely additive.

Tests to add:

- One round-trip test in `tests/test_registry.py` confirming `InterfaceField`
  default `required=True` and an explicit `required=False` round-trips through
  `RegistryEntry.to_dict()`.

Verification:

- `python -m compileall src/flytetest/registry/_types.py`
- `pytest tests/test_registry.py`
- `PYTHONPATH=src python -c "from flytetest.registry import REGISTRY_ENTRIES; print(len(REGISTRY_ENTRIES))"` (no import error)

If code changes are needed, use a coverage-oriented commit message such as:
"registry: backfill InterfaceField.required coverage".

Do not change the checklist status unless you discover the branch regressed and
Step 01 is no longer actually complete.
```

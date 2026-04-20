Use this prompt when starting Step 13 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3g — resolver raise path)

Context:

- This is Step 13. Depends on Step 03 (errors.py landed). Replace bare
  `KeyError` / `FileNotFoundError` inside `_materialize_bindings` with the
  typed `PlannerResolutionError` subclasses. Step 14 extends the resolver
  with the `$ref` binding form that uses these exceptions; Step 19 wires
  the tool-boundary translation.

Task:

1. In `src/flytetest/resolver.py::_materialize_bindings` (and any helpers
   it calls), replace resolution failures with the typed exceptions:
   - Unknown `$ref.run_id` → `UnknownRunIdError(run_id, available_count)`.
   - `$ref.run_id` known but `output_name` missing →
     `UnknownOutputNameError(run_id, output_name, known_outputs)`.
   - `$manifest` path that does not exist → `ManifestNotFoundError(path)`.
   - Raw-path binding pointing at a missing file →
     `BindingPathMissingError(path)`.

2. Do NOT catch these at the resolver layer — they must propagate so the
   tool-boundary translator (Step 19) can build a structured decline.

Tests to add (tests/test_resolver.py):

- Each failure mode raises the correct subclass with the correct attributes.
- `str(exc)` includes the key context.

Verification:

- `python -m compileall src/flytetest/resolver.py`
- `pytest tests/test_resolver.py`

Commit message: "resolver: raise typed PlannerResolutionError subclasses".

Then mark Step 13 Complete in docs/mcp_reshape/checklist.md.
```

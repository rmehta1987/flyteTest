Use this prompt when starting Step 03 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3g — the exception-to-decline translation design)

Context:

- This is Step 03. Pure-additive — no existing code is touched. The typed
  exceptions land first so Step 13 (resolver raise path) and Step 19
  (_execute_run_tool wrapper) can reference them.

Task:

1. Create `src/flytetest/errors.py` with:
   - `PlannerResolutionError(Exception)` — base class.
   - `UnknownRunIdError(PlannerResolutionError)` — carries `run_id`,
     `available_count`.
   - `UnknownOutputNameError(PlannerResolutionError)` — carries `run_id`,
     `output_name`, `known_outputs: tuple[str, ...]`.
   - `ManifestNotFoundError(PlannerResolutionError)` — carries
     `manifest_path`; represents a `$manifest` path that does not exist on
     disk.
   - `BindingPathMissingError(PlannerResolutionError)` — carries `path`;
     represents a raw-path binding pointing at a missing file.

2. Each subclass stores the contextual fields as attributes AND composes a
   human-readable message in `__init__` via `super().__init__(msg)`. The
   attributes let the _execute_run_tool wrapper (Step 19) populate a
   PlanDecline's `next_steps` field deterministically; the message is the
   human-readable `limitations` entry.

3. Keep this step minimal. Do not add richer metadata such as planner type,
  binding field name, or filesystem classification yet; that can be added in
  a later refinement if Step 19 or Step 13 proves it is needed.

3. Module docstring explains the opt-in semantics: raising a
   `PlannerResolutionError` subclass opts the failure into the exception-to-
   decline translation layer. Any other exception propagates (and is logged
   via §3e).

Tests to add (tests/test_errors.py):

- Each subclass carries the expected attributes.
- `str(exc)` contains the key context (`run_id`, `output_name`,
  `known_outputs`, `manifest_path`, or `path`, as appropriate).
- `isinstance(exc, PlannerResolutionError)` is True for every subclass.

Verification:

- `python -m compileall src/flytetest/errors.py`
- `pytest tests/test_errors.py`

Commit message: "errors: add PlannerResolutionError hierarchy for decline translation".

Then mark Step 03 Complete in docs/mcp_reshape/checklist.md.
```

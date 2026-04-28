# Step 04 — Codify Forward Convention in Docs

## Prerequisites

Steps 01–03 must be complete:
- All flat tools implemented, registered, and tested
- Full test suite passes: `python -m pytest`

## Context

This step codifies the rule that every new registered workflow or task with a `showcase_module` entry must ship a corresponding flat MCP tool at the same time. The convention is added as a checklist item in `.codex/workflows.md` and `.codex/tasks.md`, and noted in `AGENTS.md`.

No code changes are required in this step — only documentation.

## Files to read before editing

- `.codex/workflows.md` — find the appropriate section for a new checklist item (e.g. "Adding a new workflow" checklist, or a "Pull request checklist" section)
- `.codex/tasks.md` — same, for tasks
- `AGENTS.md` — find the "Core Rules" or "Behavior Changes" section where the note belongs
- `docs/2026-04-28-simplified-mcp-tools/simplified_mcp_tools_plan.md` — review the forward convention and naming table for accurate doc language

## Files to edit

| Action | File |
|---|---|
| Edit | `.codex/workflows.md` |
| Edit | `.codex/tasks.md` |
| Edit | `AGENTS.md` |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### `.codex/workflows.md`

Find the checklist or "adding a new workflow" section. Add one item:

> - If the new workflow sets `showcase_module`, add a corresponding flat-parameter MCP tool
>   in `src/flytetest/mcp_tools.py` following the naming convention in
>   `docs/2026-04-28-simplified-mcp-tools/simplified_mcp_tools_plan.md` (prefix table).
>   Register the tool in `create_mcp_server()`, add its name constant and description to
>   `mcp_contract.py`, add it to `EXPERIMENT_LOOP_TOOLS`, and write tests in
>   `tests/test_mcp_tools.py`.

### `.codex/tasks.md`

Same as above but scoped to tasks:

> - If the new task sets `showcase_module`, add a corresponding flat-parameter MCP tool
>   in `src/flytetest/mcp_tools.py` following the naming convention in
>   `docs/2026-04-28-simplified-mcp-tools/simplified_mcp_tools_plan.md` (prefix table).
>   Register the tool in `create_mcp_server()`, add its name constant and description to
>   `mcp_contract.py`, add it to `EXPERIMENT_LOOP_TOOLS`, and write tests in
>   `tests/test_mcp_tools.py`.

### `AGENTS.md`

Under "Core Rules" (or the closest appropriate section), add:

> - Every new registered workflow or task that sets `showcase_module` must ship a
>   corresponding flat-parameter MCP tool in `src/flytetest/mcp_tools.py` at the same
>   time. See `docs/2026-04-28-simplified-mcp-tools/simplified_mcp_tools_plan.md` for the
>   naming convention and implementation pattern.

### Docstring standard reminder

When reviewing the diff for this step, confirm that every flat tool in `mcp_tools.py` (from Steps 01–03) satisfies the docstring standard:
- Lists every named parameter
- Includes a concrete example with absolute paths
- States "All paths must be absolute"

If any tool is missing these elements, fix the docstring as part of this step.

## Validation

```bash
python -m pytest           # full suite must pass with no regressions
python -m py_compile src/flytetest/mcp_tools.py
python -m py_compile src/flytetest/mcp_contract.py
```

## Acceptance criteria

- `.codex/workflows.md` contains the flat-tool checklist item
- `.codex/tasks.md` contains the flat-tool checklist item
- `AGENTS.md` contains the flat-tool requirement note
- Full test suite passes with no regressions
- Every flat tool in `mcp_tools.py` has a docstring with a parameter list, absolute-path example, and the "All paths must be absolute" statement

## CHANGELOG entry template

```
### Changed
- `.codex/workflows.md`, `.codex/tasks.md`: added checklist item requiring a flat
  MCP tool for every new showcase_module workflow or task.
- `AGENTS.md`: added forward-convention note linking to the simplified-mcp-tools plan.
```

## Milestone close-out

After this step is complete and the full suite passes:

1. Archive the milestone folder:
   ```bash
   git mv docs/2026-04-28-simplified-mcp-tools docs/archive/2026-04-28-simplified-mcp-tools
   ```
2. Add a CHANGELOG entry noting milestone completion.
3. Commit with message: `docs: archive simplified-mcp-tools milestone`.

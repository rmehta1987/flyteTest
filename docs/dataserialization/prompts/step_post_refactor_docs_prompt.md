Use this prompt when starting the post-refactor documentation update slice
or when handing it off to another session.

```text
You are completing the FLyteTest serialization consolidation + registry restructure
under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/checklist.md
- /home/rmeht/Projects/flyteTest/docs/dataserialization/serialization_registry_restructure_plan.md

Read the relevant repo-local guides under `.codex/`:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/comments.md

Context:

- All implementation steps (A0-A4, B1-B5) must be complete before this step.
  Confirm in the checklist.
- This step updates project documentation to reflect the new registry package
  structure and serialization consolidation.

Task:

1. Create `.codex/registry.md` — deep guide for the registry package:
   - Package structure and conventions
   - Field semantics for RegistryEntry and RegistryCompatibilityMetadata
   - How to add a new entry (which family file, what fields are required)
   - How showcase_module controls MCP exposure
   - How pipeline_family and pipeline_stage_order drive pipeline sequencing

2. Create `.codex/agent/registry.md` — specialist role prompt following the
   pattern in `.codex/agent/task.md` and `.codex/agent/workflow.md`:
   - Purpose: Use when adding/modifying entries in `src/flytetest/registry/`
   - Read First: AGENTS.md, DESIGN.md, .codex/registry.md, target family file,
     mcp_contract.py if setting showcase_module
   - Role: Register new biological stages with complete, self-contained metadata
   - Core Principles (5 items — see plan doc)
   - Validation: compileall, full test suite, get_pipeline_stages() order
   - Handoff: entries added, family, type-graph connections, MCP surface

3. Update `AGENTS.md` — add a Project Structure quick-map section (~30 lines):
   - Registry package, Types, Tasks, Workflows, Core Concepts
   - Two-tier design: AGENTS.md = orientation layer, .codex/ = depth layer

4. Update `CLAUDE.md` — add registry guide to the specialist guides table:
   ```
   | Registry entries and pipeline families | `.codex/registry.md`, `.codex/agent/registry.md` |
   ```

5. Update `DESIGN.md` — reflect the registry package split and serialization
   consolidation in the architecture description.

6. Update the 9 `.codex/` files that reference `src/flytetest/registry.py`
   as a monolith path — change to `src/flytetest/registry/` (package):

   | File | Approximate lines to update |
   |---|---|
   | `.codex/workflows.md` | 21, 160 |
   | `.codex/documentation.md` | 34 |
   | `.codex/testing.md` | 18 |
   | `.codex/code-review.md` | 32, 53 |
   | `.codex/agent/workflow.md` | 19 |
   | `.codex/agent/code-review.md` | 20, 50 |
   | `.codex/agent/test.md` | 22, 50 |
   | `.codex/agent/architecture.md` | 71, 123 |
   | `.codex/agent/README.md` | 40 |

   Verify at implementation time — line numbers are approximate.

7. Update `CHANGELOG.md` with a comprehensive dated entry for the full refactor.

8. Update `docs/dataserialization/checklist.md` — mark post-refactor docs complete.

Important constraints:

- Do not modify any source code in this step — documentation only.
- Follow the documentation style guide in `.codex/documentation.md`.
- Keep AGENTS.md concise — it is loaded every conversation. Depth goes in
  .codex/ guides.
- Do not add emojis.

Validation:

1. `rg "src/flytetest/registry.py" .codex/ AGENTS.md CLAUDE.md DESIGN.md` — 0 hits
   (all references updated to registry package)
2. Verify .codex/registry.md and .codex/agent/registry.md exist and are non-empty
3. `git diff --check` — no trailing whitespace

Report back with:

- checklist items completed
- files created and modified
- summary of AGENTS.md changes
- any references to registry.py that still exist (should be 0 in docs)
```

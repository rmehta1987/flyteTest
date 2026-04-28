# User-Authored Workflow Composition — Checklist

## Open questions to resolve before starting

- [ ] Confirm composed workflow name
- [ ] Confirm input surface (BAM re-run vs VCF-only)
- [ ] Confirm flat tool naming convention
- [ ] Confirm scope boundary (single family or multi-family)

## Steps

| Step | Name | Status |
|---|---|---|
| 01 | Flat MCP tool `vc_custom_filter` | [ ] |
| 02 | Composed workflow + registry entry | [ ] |
| 03 | Flat MCP tool for composed workflow | [ ] |
| 04 | Tests — flat tool + dry-run + registry | [ ] |
| 05 | Docs update (`user_tasks.md`) | [ ] |
| 06 | Closure (CHANGELOG, full suite, commit) | [ ] |

## Verification gates

- [ ] `python3 -m compileall` passes on all touched files
- [ ] `PYTHONPATH=src pytest tests/test_mcp_tools.py -x -q` — flat tool tests green
- [ ] New workflow registry tests pass
- [ ] Full suite green (ignoring pre-existing `test_compatibility_exports.py` error)
- [ ] `git diff --name-only` contains no `planning.py`, `spec_executor.py`,
  `planner_types.py`, `bundles.py`

## Hard constraints

- Flat tools must follow the `vc_*` naming convention
- Composed workflow must use only existing planner types (`VariantCallSet`)
- No changes to `planning.py`, `mcp_contract.py`, `bundles.py`, `spec_executor.py`,
  or `planner_types.py`
- `download_sync()` is acceptable on VCF inputs (no companion index)

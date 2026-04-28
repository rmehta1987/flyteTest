# Simplified MCP Tools — Checklist

## Step 1 — variant_calling flat tools [SHOWCASE PRIORITY]

- [ ] Create `src/flytetest/mcp_tools.py` with module docstring and imports
- [ ] Implement `vc_germline_discovery`
- [ ] Implement `vc_prepare_reference`
- [ ] Implement `vc_preprocess_sample`
- [ ] Implement `vc_genotype_refinement`
- [ ] Implement `vc_small_cohort_filter`
- [ ] Implement `vc_post_genotyping_refinement`
- [ ] Implement `vc_sequential_interval_haplotype_caller`
- [ ] Implement `vc_pre_call_coverage_qc`
- [ ] Implement `vc_post_call_qc_summary`
- [ ] Implement `vc_annotate_variants_snpeff`
- [ ] Add tool name constants for all 10 tools to `mcp_contract.py`
- [ ] Add `TOOL_DESCRIPTIONS` entries for all 10 tools in `mcp_contract.py`
- [ ] Add all 10 tool names to `EXPERIMENT_LOOP_TOOLS` in `mcp_contract.py`
- [ ] Import `mcp_tools` and register all 10 tools in `create_mcp_server()` in `server.py`
- [ ] Write `tests/test_mcp_tools.py` covering all 10 variant_calling tools
- [ ] All tests pass: `python -m pytest tests/test_mcp_tools.py`
- [ ] Update `CHANGELOG.md`

## Step 2 — annotation flat tools

- [ ] Implement `annotation_braker3` in `mcp_tools.py`
- [ ] Implement `annotation_protein_evidence` in `mcp_tools.py`
- [ ] Add tool name constants for both to `mcp_contract.py`
- [ ] Add `TOOL_DESCRIPTIONS` entries for both in `mcp_contract.py`
- [ ] Add both to `EXPERIMENT_LOOP_TOOLS` in `mcp_contract.py`
- [ ] Register both in `create_mcp_server()` in `server.py`
- [ ] Add tests for both annotation tools to `tests/test_mcp_tools.py`
- [ ] All tests pass: `python -m pytest tests/test_mcp_tools.py`
- [ ] Update `CHANGELOG.md`

## Step 3 — rnaseq flat tools (and any remaining families)

- [ ] Implement `rnaseq_qc` in `mcp_tools.py`
- [ ] Add tool name constant, `TOOL_DESCRIPTIONS` entry, and `EXPERIMENT_LOOP_TOOLS` membership
- [ ] Register in `create_mcp_server()`
- [ ] Add tests for `rnaseq_qc`
- [ ] All tests pass: `python -m pytest tests/test_mcp_tools.py`
- [ ] Update `CHANGELOG.md`

## Step 4 — convention docs

- [ ] Add flat-tool checklist item to `.codex/workflows.md`
- [ ] Add flat-tool checklist item to `.codex/tasks.md`
- [ ] Add flat-tool requirement note to `AGENTS.md`
- [ ] Verify full test suite still passes: `python -m pytest`
- [ ] Update `CHANGELOG.md`

## Done criteria

- All flat tools are registered and appear in `MCP_TOOL_NAMES` via `EXPERIMENT_LOOP_TOOLS`
- Each tool's docstring names every parameter and shows an absolute-path example
- `tests/test_mcp_tools.py` covers happy path and missing-required-param for every tool
- `.codex/workflows.md` and `.codex/tasks.md` contain the forward-convention checklist
- `AGENTS.md` notes the flat-tool requirement
- Full test suite passes with no regressions

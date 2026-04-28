# Simplified MCP Tools — Checklist

## Step 1 — variant_calling flat tools [SHOWCASE PRIORITY]

- [x] Create `src/flytetest/mcp_tools.py` with module docstring and imports
- [x] Implement `vc_germline_discovery`
- [x] Implement `vc_prepare_reference`
- [x] Implement `vc_preprocess_sample`
- [x] Implement `vc_genotype_refinement`
- [x] Implement `vc_small_cohort_filter`
- [x] Implement `vc_post_genotyping_refinement`
- [x] Implement `vc_sequential_interval_haplotype_caller`
- [x] Implement `vc_pre_call_coverage_qc`
- [x] Implement `vc_post_call_qc_summary`
- [x] Implement `vc_annotate_variants_snpeff`
- [x] Add tool name constants for all 10 tools to `mcp_contract.py`
- [x] Add `TOOL_DESCRIPTIONS` entries for all 10 tools in `mcp_contract.py`
- [x] Add `FLAT_TOOLS` tuple to `mcp_contract.py` (replaces adding to EXPERIMENT_LOOP_TOOLS)
- [x] Import `mcp_tools` and register all 10 tools in `create_mcp_server()` in `server.py`
- [x] Write `tests/test_mcp_tools.py` covering all 10 variant_calling tools
- [x] All tests pass: `python -m pytest tests/test_mcp_tools.py`
- [x] Update `CHANGELOG.md`

## Step 2 — annotation flat tools

- [x] Implement `annotation_braker3` in `mcp_tools.py`
- [x] Implement `annotation_protein_evidence` in `mcp_tools.py`
- [x] Implement `annotation_busco_qc`, `annotation_eggnog`, `annotation_agat_stats`, `annotation_agat_convert`, `annotation_agat_cleanup`, `annotation_table2asn`, `annotation_gffread_proteins`, `annotation_busco_assess`, `annotation_exonerate_chunk`
- [x] Add tool name constants for all annotation tools to `mcp_contract.py`
- [x] Add `TOOL_DESCRIPTIONS` entries for all annotation tools in `mcp_contract.py`
- [x] Add all annotation tools to `FLAT_TOOLS` in `mcp_contract.py`
- [x] Register all annotation tools in `create_mcp_server()` in `server.py`
- [x] Add tests for all annotation tools to `tests/test_mcp_tools.py`
- [x] All tests pass: `python -m pytest tests/test_mcp_tools.py`
- [x] Update `CHANGELOG.md`

## Step 3 — rnaseq flat tools (and any remaining families)

- [x] Implement `rnaseq_qc` in `mcp_tools.py`
- [x] Implement `rnaseq_fastqc` in `mcp_tools.py`
- [x] Add `showcase_module` to `rnaseq_qc_quant` registry entry; add `MANIFEST_OUTPUT_KEYS` to workflow module
- [x] Add tool name constants, `TOOL_DESCRIPTIONS` entries, and `FLAT_TOOLS` membership
- [x] Register both in `create_mcp_server()`
- [x] Add tests for `rnaseq_qc` and `rnaseq_fastqc`
- [x] All tests pass: `python -m pytest tests/test_mcp_tools.py`
- [x] Update `CHANGELOG.md`

## Step 4 — convention docs

- [x] Add `FLAT_TOOLS` tuple description to `AGENTS.md` (`mcp_contract.py` and `mcp_tools.py` entries)
- [x] Verify full test suite still passes: 941 passed, 1 skipped
- [x] Update `CHANGELOG.md`

## Done criteria

- [x] All flat tools are registered and appear in `MCP_TOOL_NAMES` via `FLAT_TOOLS`
- [x] Each tool's docstring names every parameter and shows an absolute-path example
- [x] `tests/test_mcp_tools.py` covers happy path, optional-field exclusion, runtime_images, and resource_request for every tool
- [x] `AGENTS.md` notes the flat-tool module (`mcp_tools.py`) and `FLAT_TOOLS`
- [x] Full test suite passes with no regressions: 941 passed, 1 skipped

# GATK Milestone A — Submission Prompt

Branch: `gatkport`

## What Was Built

Milestone A of the Phase 3 GATK4 port. Seven germline variant calling tasks
implemented on `src/flytetest/tasks/variant_calling.py`, registered in
`src/flytetest/registry/_variant_calling.py`, and covered by 29 unit tests
in `tests/test_variant_calling.py`.

Pipeline path (BAM-in → VCF-out):

1. `create_sequence_dictionary` — produce `.dict` from reference FASTA
2. `index_feature_file` — index known-sites VCFs before BQSR
3. `base_recalibrator` — generate BQSR recalibration table
4. `apply_bqsr` — apply recalibration; emit recalibrated BAM
5. `haplotype_caller` — per-sample GVCF (`--emit-ref-confidence GVCF`)
6. `combine_gvcfs` — cohort-level GVCF merge
7. `joint_call_gvcfs` — GenomicsDBImport (ephemeral tempdir) → GenotypeGVCFs

## Key Files

| File | Role |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | All 7 task implementations + `MANIFEST_OUTPUT_KEYS` |
| `src/flytetest/registry/_variant_calling.py` | `VARIANT_CALLING_ENTRIES` tuple |
| `src/flytetest/registry/__init__.py` | Concatenates `VARIANT_CALLING_ENTRIES` |
| `src/flytetest/config.py` | `variant_calling_env`, `VARIANT_CALLING_*` constants |
| `src/flytetest/planner_types.py` | `AlignmentSet`, `VariantCallSet`, `KnownSites` types |
| `tests/test_variant_calling.py` | 29 unit tests |
| `tests/test_registry_manifest_contract.py` | 7 parametrized manifest-contract tests |
| `docs/tool_refs/gatk4.md` | Tool reference (command shapes, rationale, scope notes) |

## Verification

```bash
python -m compileall src/flytetest/
pytest tests/test_variant_calling.py -xvs
pytest tests/test_registry_manifest_contract.py -xvs
pytest
rg "variant_calling" src/flytetest/registry/__init__.py
python -c "import flytetest.server"
```

## Scope Boundaries

- Alignment and duplicate-marking: Milestone B
- VQSR: deferred
- Workflow compositions (multi-task wiring): Milestone B
- All tasks are catalog-only (`showcase_module=""`); no MCP handler
- GenomicsDB workspace is ephemeral (TemporaryDirectory, never persisted)

## Not Implemented (by design)

- `async def` / `await` / `asyncio.gather` patterns
- IPFS / Pinata / TinyDB patterns
- Interval-scoped calling (whole-genome pass only)

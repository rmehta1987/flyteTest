# GATK Milestone F — Submission Prompt

Branch: `gatkport-f`

Milestone F adds interval-scoped variant calling to the germline pipeline.
It extends `haplotype_caller` with an optional `intervals` parameter (backward
compatible), adds a `gather_vcfs` task that merges per-interval GVCFs via
GATK4 GatherVcfs, and wires both into a `scattered_haplotype_caller` workflow
that calls GVCFs across intervals in a synchronous Python `for` loop and then
gathers the results. No job arrays; no asyncio.

## What Was Built

| Item | Stage | Tests |
|---|---|---|
| `haplotype_caller` — optional `intervals` param | n/a (extension) | 2 new + 3 existing pass |
| `gather_vcfs` task | task stage 15 | 4 unit tests |
| `scattered_haplotype_caller` workflow | workflow stage 6 | 5 unit tests |

- `haplotype_caller` — `intervals: list[str] | None = None`; each entry adds
  one `-L <interval>` flag. `None` / `[]` → whole-genome, unchanged behavior.
- `gather_vcfs` — GATK4 GatherVcfs with one `-I` per path (in order) and
  `--CREATE_INDEX true`. Raises `ValueError` on empty input, `FileNotFoundError`
  if output absent.
- `scattered_haplotype_caller` — `ValueError` on empty intervals; calls
  `haplotype_caller` once per interval (synchronous loop), then `gather_vcfs`.
  GVCFs passed to gather in iteration order.
- `MANIFEST_OUTPUT_KEYS` extended with `gathered_gvcf` (tasks module) and
  `scattered_gvcf` (workflows module).
- `docs/tool_refs/gatk4.md` updated with full `gather_vcfs` section.

## Key Files

| File | Role |
|---|---|
| `src/flytetest/tasks/variant_calling.py` | `haplotype_caller` extension; `gather_vcfs` task |
| `src/flytetest/workflows/variant_calling.py` | `scattered_haplotype_caller` + updated `MANIFEST_OUTPUT_KEYS` |
| `src/flytetest/registry/_variant_calling.py` | Registry entries (task stage 15, workflow stage 6) |
| `tests/test_variant_calling.py` | 2 new HaplotypeCaller interval tests; 4 GatherVcfs tests |
| `tests/test_variant_calling_workflows.py` | 5 new ScatteredHaplotypeCaller tests |
| `tests/test_registry_manifest_contract.py` | `gather_vcfs` added to `_VARIANT_CALLING_TASK_NAMES` |
| `docs/tool_refs/gatk4.md` | `gather_vcfs` reference section |

## Verification

```bash
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src python -m compileall src/flytetest/
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest
VIRTUAL_ENV=.venv PATH=".venv/bin:$PATH" PYTHONPATH=src pytest tests/test_variant_calling.py -xvs -k "HaplotypeCaller"
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" \
  src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py
rg "gather_vcfs|scattered_haplotype_caller" src/flytetest/registry/_variant_calling.py
```

## Scope Boundaries

- `CalculateGenotypePosteriors` — deferred to Milestone G.
- `VariantAnnotator` / `PostprocessVariants` — deferred to Milestone G.
- `SplitIntervals` — out of scope; users supply interval lists directly.
- Parallel scatter (job arrays, asyncio) — out of scope; synchronous for loop only.

## Not Implemented (by design)

- `async def` / `await` / `asyncio.gather` patterns.
- IPFS / Pinata / TinyDB patterns.
- Interval auto-splitting (`SplitIntervals`).

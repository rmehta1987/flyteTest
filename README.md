# FLyteTest

FLyteTest is a prompt-driven bioinformatics platform built on Flyte v2. Scientists
describe an analysis in plain language; the system selects registered biological
stages, freezes a reproducible run recipe, and submits it locally or to a
Slurm-backed HPC cluster. Every run is inspectable before submission and
replayable from the frozen artifact afterward.

Current biological scope: eukaryotic genome annotation (BRAKER3, EVM, PASA,
BUSCO, EggNOG, repeat filtering, AGAT) and GATK4 germline variant calling
(chr20 NA12878 smoke test through full VQSR refinement and SnpEff annotation).

---

## What FLyteTest Is

| | FLyteTest |
|---|---|
| **What it does** | Runs bioinformatics jobs on a compute cluster and tracks them end-to-end |
| **How you interact** | Describe the analysis via MCP tools; the system prepares and submits the job |
| **Biology focus** | Eukaryotic genome annotation and GATK4 germline variant calling |
| **Job tracking** | Every submission is saved; jobs can be monitored, retried, or cancelled |
| **Reliability** | Plans are frozen into recipes before submission — nothing is guessed at run time |
| **What it is not** | A command generator or general-purpose bioinformatics assistant |

---

## Current Scope

| Family / surface | Coverage | Primary doc |
|---|---|---|
| Annotation (BRAKER3, EVM, PASA, ...) | Full pipeline through EggNOG + AGAT | `SCIENTIST_GUIDE.md` |
| Variant calling (GATK4 germline) | 21 tasks, 11 workflows | `docs/gatk_pipeline_overview.md` |
| Postprocessing | Protein evidence, repeat masking | `SCIENTIST_GUIDE.md` |
| MCP scientist surface | `run_task`, `run_workflow`, bundles, recipes | `SCIENTIST_GUIDE.md` |
| Slurm lifecycle | Submit, monitor, retry, preflight staging | `SCIENTIST_GUIDE.md` |

---

## Quick Start

### Scientist: MCP experiment loop

```
list_entries → list_bundles → load_bundle → run_workflow
```

Use `dry_run=True` to inspect the frozen recipe before committing.
Call `validate_run_recipe` for staging preflight, then `run_slurm_recipe` to submit.
See `SCIENTIST_GUIDE.md` for the full walkthrough including GATK runbooks.

### Developer: local environment

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-cluster.txt
PYTHONPATH=src python3 -m pytest tests/ -q
```

### HPC / cluster operator

```bash
bash scripts/rcc/check_minimal_fixtures.sh
bash scripts/rcc/check_gatk_fixtures.sh
```

See `scripts/rcc/README.md` for the full HPC setup guide: SIF management,
module configuration, data staging, and Slurm job lifecycle commands.

---

## Documentation Map

| Audience | Doc |
|---|---|
| Scientists (experiment loop) | `SCIENTIST_GUIDE.md` |
| Scientists (variant calling) | `docs/gatk_pipeline_overview.md` |
| Scientists (tool reference) | `docs/tool_refs/README.md` |
| Developers | `DESIGN.md`, `AGENTS.md` |
| HPC / cluster operators | `scripts/rcc/README.md` |
| Architecture / contributors | `DESIGN.md` |

---

## Current Limits

- Authenticated Slurm session required (2FA enforced on RCC; Flyte Slurm plugin blocked)
- Compute nodes must be offline-capable: data, SIFs, and tool databases must be pre-staged
- Scatter is serial (per-interval Python loop, not job-array fan-out)
- Artifact paths are local-filesystem only; no S3/GCS backend
- Composed workflow approval is required before execution (explicit user gate)
- VEP annotation deferred; SnpEff only for now

---

## Repository Layout

- `src/flytetest/` — tasks, workflows, registry, MCP server, planning, bundles
- `docs/` — pipeline family overviews, tool references, archive
- `scripts/rcc/` — HPC setup, data staging, and Slurm wrapper scripts
- `tests/` — automated validation (862 tests)
- `data/` — local fixtures and reference data (not committed)
- `results/` — run outputs (not committed)

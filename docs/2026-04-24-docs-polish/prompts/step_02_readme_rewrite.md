# Step 02 — README Rewrite

Rewrite `README.md` from its current 656 lines to ≤ 300 lines. The README becomes
a stable landing page — a front door that answers "what is this, who is it for, and
where do I go?" without enumerating every task, workflow, or tool parameter.

Read `docs/readme_replacement_outline.md` before starting — it contains the full
design rationale, content migration decisions, and draft skeleton.

---

## Target structure (7 sections)

### 1. Title + one-paragraph summary
- What FLyteTest is
- The interaction model (MCP + Flyte + Slurm)
- High-level biological scope

### 2. What FLyteTest Is
Keep the existing orientation table (what it does / how you interact / biology focus /
job tracking / reliability / what it is not). Trim any surrounding prose.

### 3. Current Scope
Replace the long "Implemented Now" section with a compact table:

| Family / surface | Coverage | Primary doc |
|---|---|---|
| Annotation (BRAKER3, EVM, PASA, ...) | Full pipeline | `SCIENTIST_GUIDE.md` |
| Variant calling (GATK4 germline) | 21 tasks, 11 workflows | `docs/gatk_pipeline_overview.md` |
| Postprocessing | Protein evidence, repeat masking | `SCIENTIST_GUIDE.md` |
| MCP scientist surface | run_task, run_workflow, bundles, recipes | `SCIENTIST_GUIDE.md` |
| Slurm lifecycle | Submit, monitor, retry, preflight | `SCIENTIST_GUIDE.md` |

Do not enumerate individual task or workflow names in the README.

### 4. Quick Start
Three short subsections — each ≤ 8 lines:

**Scientist: MCP experiment loop**
```
list_entries → list_bundles → load_bundle → run_workflow
```
Point to SCIENTIST_GUIDE.md for the full walkthrough.

**Developer: local environment**
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-cluster.txt
PYTHONPATH=src python -m pytest tests/ -q
```

**HPC / cluster operator**
```bash
bash scripts/rcc/check_minimal_fixtures.sh
bash scripts/rcc/check_gatk_fixtures.sh
```
Point to `scripts/rcc/README.md` for the full HPC setup guide.

### 5. Documentation Map
Audience-first table:

| Audience | Doc |
|---|---|
| Scientists (experiment loop) | `SCIENTIST_GUIDE.md` |
| Scientists (variant calling) | `docs/gatk_pipeline_overview.md` |
| Scientists (tool reference) | `docs/tool_refs/README.md` |
| Developers | `DESIGN.md`, `AGENTS.md` |
| HPC / cluster operators | `scripts/rcc/README.md` |
| Architecture / contributors | `DESIGN.md` |

### 6. Current Limits
Short bullet list (≤ 8 items) of honest boundaries:
- Authenticated Slurm session required (2FA; Flyte Slurm plugin blocked)
- Compute nodes require no-internet; data and SIFs must be pre-staged
- Scatter is serial (per-interval Python loop, not job-array fan-out)
- Artifact paths are local-filesystem; no S3/GCS backend yet
- VEP annotation deferred (SnpEff only for now)

### 7. Repository Layout
Short bullets only:
- `src/flytetest/` — tasks, workflows, registry, MCP server, planning
- `docs/` — pipeline family overviews, tool references, archive
- `scripts/rcc/` — HPC setup, staging, and Slurm wrapper scripts
- `tests/` — automated validation (858 tests)
- `data/` — local fixtures and reference data (not committed)
- `results/` — run outputs (not committed)

---

## Content to remove from README

Do not carry forward:
- Any enumeration of individual task or workflow names
- "Architecture Status", "M18/M19" milestone history
- Detailed MCP tool parameter lists
- Fixture provenance or smoke-test command galleries
- `Deferred` / `Roadmap` / detailed assumptions sections

These live in DESIGN.md, SCIENTIST_GUIDE.md, or docs/archive/.

---

## Verification

```bash
wc -l README.md          # must be ≤ 300
grep "scattered_haplotype_caller" README.md  # must return nothing (stale name)
grep "prepare_reference\|germline_short_variant" README.md  # should link, not enumerate
```

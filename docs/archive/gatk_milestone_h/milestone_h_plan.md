# GATK4 Germline Variant Calling — Milestone H

GATK production wiring and provenance hardening. Closes the claim-vs-reality
gap identified in the 2026-04-23 principal-bioinformatician review: registry
entries exist for all 16 GATK tasks and 7 workflows, but none are reachable
through the MCP experiment loop the README advertises as the primary
scientist entrypoint.

Source-of-truth references:

- `AGENTS.md`, `DESIGN.md`, `.codex/` — project rules and patterns.
- Milestones A–G plans under `docs/gatk_milestone_*/`.
- 2026-04-23 review findings (summarized here in §1).

## §1 Context

Milestones A–G delivered 16 GATK tasks, 7 workflows, 2 fixture bundles, and
an end-to-end pipeline overview. The 2026-04-23 review surfaced three
distinct gaps between those artifacts and the rest of the platform:

1. **MCP surface disconnection.** No variant_calling registry entry sets
   `showcase_module`, so the entries are absent from `SHOWCASE_TARGETS`,
   `SUPPORTED_TASK_NAMES` / `SUPPORTED_WORKFLOW_NAMES`,
   `_local_node_handlers()`, and `TASK_PARAMETERS`. `planning.py` has no
   variant_calling intent branch. `run_task` / `run_workflow` /
   `run_local_recipe` / `run_slurm_recipe` return `supported=False` for
   every GATK target.
2. **Two P0-grade defects** in the task module itself:
   - `bwa_mem2_mem` passes unquoted user paths to `subprocess.run(shell=True)`
     — any path containing a space already breaks it; a path with shell
     metacharacters is remote code execution.
   - All 16 variant_calling tasks write `{results_dir}/run_manifest.json`;
     inside multi-task workflows (e.g. `preprocess_sample`) each task
     clobbers the previous one's manifest, destroying per-stage provenance.
3. **Assorted drift** — stale "out of scope for Milestone A" text on
   `haplotype_caller` after Milestone F added the `intervals` parameter;
   the `variant_calling_germline_minimal` bundle declares a single typed
   `KnownSites` binding while supplying two scalar paths; unused `ref_path`
   parameter on `post_genotyping_refinement`; `prepare_reference` is not
   idempotent on rerun.

Milestone H addresses all three. The full port of the nine plain-Python
task helpers (bwa_mem2_*, sort_sam, mark_duplicates, variant_recalibrator,
apply_vqsr, merge_bam_alignment, gather_vcfs, calculate_genotype_posteriors)
to the `@variant_calling_env.task` + `File` I/O pattern is **explicitly
deferred to Milestone I**; their interiors are fixed here, but their
signatures stay as-is so workflow bodies do not need rewriting.

## §2 Pillars / Invariants

Same four pillars as Milestones A–G. No new exceptions. Additionally for
Milestone H:

- Only the workflow-level and Milestone A task-level surfaces are exposed
  through MCP. Plain-Python helpers remain internal until Milestone I ports
  them to the Flyte task pattern.
- No biology is added or removed. Hard-filtering, variant annotation, and
  post-call stats are deferred to Milestone I.
- P0 fixes must preserve exact output filenames and on-disk layout so
  downstream workflows and existing smoke tests keep working.

## §3 Data Model

No new planner types, no new `MANIFEST_OUTPUT_KEYS`, no new registry
stage orders.

### Manifest filename change (all variant_calling tasks)

Per-task manifests currently collide at `{results_dir}/run_manifest.json`.
Migrate to per-stage filenames:

```
run_manifest_<stage>.json
```

where `<stage>` matches the existing `stage` field inside the manifest
envelope (e.g. `run_manifest_bwa_mem2_mem.json`,
`run_manifest_base_recalibrator.json`). The *workflow-level* manifests
stay at `run_manifest.json` since each workflow task owns exactly one
`results_dir` and is the terminal write there.

### `showcase_module` assignments

| Entry | Category | showcase_module |
|---|---|---|
| `create_sequence_dictionary` | task | `flytetest.tasks.variant_calling` |
| `index_feature_file` | task | `flytetest.tasks.variant_calling` |
| `base_recalibrator` | task | `flytetest.tasks.variant_calling` |
| `apply_bqsr` | task | `flytetest.tasks.variant_calling` |
| `haplotype_caller` | task | `flytetest.tasks.variant_calling` |
| `combine_gvcfs` | task | `flytetest.tasks.variant_calling` |
| `joint_call_gvcfs` | task | `flytetest.tasks.variant_calling` |
| `prepare_reference` | workflow | `flytetest.workflows.variant_calling` |
| `preprocess_sample` | workflow | `flytetest.workflows.variant_calling` |
| `germline_short_variant_discovery` | workflow | `flytetest.workflows.variant_calling` |
| `genotype_refinement` | workflow | `flytetest.workflows.variant_calling` |
| `preprocess_sample_from_ubam` | workflow | `flytetest.workflows.variant_calling` |
| `scattered_haplotype_caller` | workflow | `flytetest.workflows.variant_calling` |
| `post_genotyping_refinement` | workflow | `flytetest.workflows.variant_calling` |

Plain-Python helper tasks keep `showcase_module=""` and remain
workflow-internal until Milestone I.

## §4 Implementation Notes

### Step 01 — P0 security + provenance fixes

**`bwa_mem2_mem` shell quoting.** Current shape
(`tasks/variant_calling.py:469-483`):

```python
pipeline = (
    f"bwa-mem2 mem -R '{rg}' -t {threads} {ref_path} {r1_path}"
    + (f" {r2_path}" if r2_path else "")
    + f" | samtools view -bS -o {output_bam} -"
)
```

Replace with `shlex.quote` on every user-supplied path:

```python
import shlex
pipeline = (
    f"bwa-mem2 mem -R {shlex.quote(rg)} -t {threads} "
    f"{shlex.quote(ref_path)} {shlex.quote(r1_path)}"
    + (f" {shlex.quote(r2_path)}" if r2_path else "")
    + f" | samtools view -bS -o {shlex.quote(str(output_bam))} -"
)
```

Route through `run_tool` when `sif_path` is set (container parity with the
rest of the module); otherwise use `subprocess.run(pipeline, shell=True,
check=False)` but keep the `returncode` check + `stderr` propagation.

**Per-stage manifest filenames.** Every `_write_json(out_dir /
"run_manifest.json", manifest)` in `tasks/variant_calling.py` becomes
`_write_json(out_dir / f"run_manifest_{manifest['stage']}.json", manifest)`.
Workflow-level emits in `workflows/variant_calling.py` stay as
`run_manifest.json`. Add a module-level helper if the pattern becomes ugly.

### Step 02 — MCP surface wiring

1. Set `showcase_module` on the 14 registry entries in §3.
2. Add `TASK_PARAMETERS` entries in `server.py` for the 7 exposed tasks
   (param name + required flag per entry, matching the registry `inputs`
   tuple semantics — `File` fields become the required bindings; `str`
   scalars like `sample_id`, `cohort_id`, and `gatk_sif` become
   `TASK_PARAMETERS` scalars).
3. No change needed to `_local_node_handlers()`: it derives handlers from
   `SUPPORTED_WORKFLOW_NAMES` / `SUPPORTED_TASK_NAMES`, which derive from
   `SHOWCASE_TARGETS`, which derive from `showcase_module`. Setting
   `showcase_module` is the only wiring change required.
4. Update README "Current local MCP execution" block (lines ~305-320) to
   list the 14 new exposed targets.
5. Update `docs/mcp_showcase.md` if it enumerates targets.

### Step 03 — Planning intent + bundle integrity

**Planning intent.** Add a `variant_calling` branch in `planning.py` that
maps prompts containing any of `{"variant", "germline", "vcf", "gvcf",
"haplotype", "genotype", "vqsr", "bqsr"}` (plus `(call|discover|recalibrate)`
verbs) to the matching registry entry. Follow the existing
`_typed_goal_for_target` / `plan_typed_request` pattern.

**Bundle typed-binding fix.** `variant_calling_germline_minimal` declares
one `KnownSites` binding but lists two `known_sites` paths in scalar inputs.
Two options; pick (a) for minimal churn:

- (a) Drop the typed `KnownSites` binding from the bundle. The scalar
  `known_sites` list is the authoritative channel; typed bindings for
  `KnownSites` remain available to callers via `explicit_bindings`.
- (b) Extend the bundle schema to accept `list[dict]` for typed bindings so
  both known-sites entries can be declared.

**Stale assumption text.** In `tasks/variant_calling.py:260`, remove
`"Whole-genome pass; intervals-scoped calling is out of scope for
Milestone A."` from `haplotype_caller`'s manifest assumptions. Sweep for
other `out of scope for Milestone A` strings in the module.

### Step 04 — Workflow/task signature cleanups

1. **Drop `ref_path` from `post_genotyping_refinement`.** GATK
   `CalculateGenotypePosteriors` has no `-R` flag (already noted in the
   task assumption). Remove the parameter from the workflow signature and
   from its call site to `calculate_genotype_posteriors`. Update the
   registry entry `inputs` tuple.
2. **Idempotency on `prepare_reference`.** Add `force: bool = False`. Each
   inner step checks for its expected output(s) and skips on existence when
   `force=False`. Document the behavior in the workflow manifest's
   `assumptions` list.
3. **Document GenomicsDB workspace as ephemeral-only** in
   `docs/gatk_pipeline_overview.md` under a new `## Deferred Items`
   sub-bullet. One line; no workflow change.

### Step 05 — Closure

Milestone CHANGELOG entry, submission prompt doc, smoke test through the
MCP surface, and branch merge.

## §5 Backward Compatibility

- Per-stage manifest filenames are a breaking change for any external
  consumer reading `{results_dir}/run_manifest.json`. No such consumer
  exists inside the repo (workflow bodies use return values, not manifest
  reads); smoke tests read the workflow-level `run_manifest.json` only.
  Call the change out explicitly in the CHANGELOG.
- `post_genotyping_refinement`'s signature loses `ref_path`. Any caller
  that pinned it must update; no internal caller exists.
- `prepare_reference` gains a `force: bool = False` kwarg. Existing calls
  inherit the new default, which is additive-safe (rerunning without
  `force=True` now skips instead of overwriting).
- `showcase_module` additions are additive; existing clients that filter
  by `SHOWCASE_TARGETS` see the new variant_calling entries but nothing
  else changes.

## §6 Steps

| # | Step | Prompt |
|---|------|--------|
| 01 | P0 fixes — shell quoting + per-stage manifest filenames | `prompts/step_01_p0_fixes.md` |
| 02 | MCP surface wiring — `showcase_module` + `TASK_PARAMETERS` + README | `prompts/step_02_mcp_surface_wiring.md` |
| 03 | Planning intent + bundle integrity + stale-assumption sweep | `prompts/step_03_planning_and_bundles.md` |
| 04 | Workflow cleanups — `post_genotyping_refinement`, idempotency, docs | `prompts/step_04_cleanups.md` |
| 05 | Closure — CHANGELOG, submission prompt, smoke, merge | `prompts/step_05_closure.md` |

## §7 Out of Scope (this milestone)

- **Porting 9 plain-Python helpers to the Flyte task pattern.** Deferred
  to Milestone I. The helpers remain workflow-internal; their signatures
  and return types (`dict`) are unchanged by Milestone H.
- **Biology completeness:** `VariantFiltration` hard-filtering fallback,
  variant annotation (SnpEff/VEP), post-call stats (`bcftools stats`,
  MultiQC), pre-call coverage QC (Picard `CollectWgsMetrics`). All deferred
  to Milestone I.
- **True scatter parallelism.** `scattered_haplotype_caller` stays
  synchronous; real scatter (job array or per-interval sbatch) is a
  Milestone I candidate.
- **VQSR annotation-set parameterization, read-group parameterization.**
  Milestone I.
- **GenomicsDB incremental workspace support.** Documented as a non-goal
  in Step 04; implementation deferred indefinitely.

## §8 Verification Gates

- `python -m compileall src/flytetest/` clean.
- `pytest tests/test_variant_calling.py -xvs` green.
- `pytest tests/test_variant_calling_workflows.py -xvs` green.
- `pytest tests/test_registry.py -xvs` green.
- `pytest tests/test_server.py -xvs` green.
- `pytest tests/test_mcp_contract.py -xvs` green.
- `pytest tests/test_planning.py -xvs` green.
- `pytest tests/test_bundles.py -xvs` green.
- `pytest` full suite green.
- `rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" src/flytetest/tasks/variant_calling.py src/flytetest/workflows/variant_calling.py` → zero hits.
- `rg "shell=True" src/flytetest/tasks/variant_calling.py` → at most one
  hit, inside the `bwa_mem2_mem` quoted-pipeline path.
- `rg "out of scope for Milestone A" src/flytetest/tasks/variant_calling.py` → zero hits.
- `rg "showcase_module" src/flytetest/registry/_variant_calling.py` → 14
  non-empty assignments.
- Smoke through MCP:
  `python -c "from flytetest.mcp_contract import SUPPORTED_WORKFLOW_NAMES; assert 'germline_short_variant_discovery' in SUPPORTED_WORKFLOW_NAMES"` exits 0.

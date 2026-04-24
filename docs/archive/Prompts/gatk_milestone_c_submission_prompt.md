# GATK Milestone C — Submission Prompt

Branch: `gatkport-c`

Milestone C closes the Phase 3 GATK port documentation layer. It delivers
the live-cluster validation prompt set for the `variant_calling` family and
refreshes `docs/mcp_full_pipeline_prompt_tests.md` to cover both annotation
and variant calling pipelines. Documentation-only — no new Python, tasks,
workflows, registry entries, or planner types were added.

## What landed

- `docs/mcp_variant_calling_cluster_prompt_tests.md` — 8 live-cluster
  scenarios: sanity check (list_entries), single-task happy path
  (haplotype_caller via load_bundle → run_task → poll), three workflow happy
  paths (prepare_reference, preprocess_sample, germline_short_variant_discovery
  via run_workflow), cancel idempotency, NODE_FAIL retry, and OOM escalation
  retry. All scenarios reuse `variant_calling_germline_minimal` bundle paths
  and `scripts/rcc/make_m18_retry_smoke_record.sh` for synthetic failure records.
- `docs/mcp_full_pipeline_prompt_tests.md` — retitled to cover both families;
  Prerequisites extended for GATK4 SIF + germline fixture staging; Variant
  Calling Pipeline section (Stages 0–3) appended, cross-referencing the cluster
  doc by Scenario number rather than duplicating prompt blocks.
- `AGENTS.md` — cluster prompt docs section added under Project Structure.
- `docs/gatk_milestone_c/milestone_c_plan.md` + `checklist.md` — tracker docs.

## What did not land

- `merge_bam_alignment` (uBAM alignment path) — deferred.
- VQSR (`variant_recalibrator`, `apply_vqsr`) — deferred.
- Interval-scoped HaplotypeCaller — deferred.
- Actual fixture data in the repo — cluster-staged only; no data files added.
- New `scripts/rcc/` helpers — reuses `pull_gatk_image.sh` and
  `make_m18_retry_smoke_record.sh` verbatim.

## Exit criteria

- `python -m compileall src/flytetest/` clean.
- `pytest` full suite green.
- `rg "variant_calling" docs/mcp_variant_calling_cluster_prompt_tests.md` matches.
- `rg "germline_short_variant_discovery" docs/mcp_full_pipeline_prompt_tests.md` matches.
- `rg "async def|await|asyncio.gather|\.cid\b|IPFS|Pinata|TinyDB"` — zero hits in both docs.
- `rg "mcp_variant_calling_cluster_prompt_tests" AGENTS.md` matches.
- `docs/gatk_milestone_c_submission_prompt.md` present and ≤ 100 lines.
- No `.py` files changed (`git diff --stat main...` shows docs only).

## Pointer docs

- `docs/gatk_milestone_c/milestone_c_plan.md` — scope, pillars, deliverables
- `docs/gatk_milestone_c/checklist.md` — step tracker
- `docs/mcp_variant_calling_cluster_prompt_tests.md` — cluster scenarios
- `docs/mcp_full_pipeline_prompt_tests.md` — full pipeline prompt reference
- `docs/gatk_milestone_a_submission_prompt.md` — Phase 3 context

## Next scoping targets (Milestone D candidates)

VQSR is the most significant gap: `variant_recalibrator` and `apply_vqsr`
tasks would extend the pipeline past hard-filtering to a statistically
calibrated output. The uBAM alignment path (`merge_bam_alignment`) and
interval-scoped HaplotypeCaller (scattered-scatter for large cohorts) are
the other two deferred items from the original Phase 3 plan. Any of these
could anchor Milestone D; VQSR is the highest-value addition given that it
is the standard production path for germline calling at scale.

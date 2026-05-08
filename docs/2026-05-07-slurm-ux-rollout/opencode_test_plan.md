# Slurm UX Rollout Phase 0 — opencode test plan

**Date:** 2026-05-08
**Companion to:** `scripts/rcc/phase0_smoke.py` (Python-level coverage)

The smoke script verifies the *implementation* against real Slurm.  This
plan verifies the *MCP-client UX* — the surface a scientist actually
sees when they drive the FLyteTest server through opencode.  Phase 1
priorities should be informed by which prompts feel rough here, not by
what the Python smoke says.

## Setup

1. Open `~/.config/opencode/opencode.json` (or wherever your local
   opencode config lives) and confirm the `flytetest` MCP entry points
   at this branch's checkout.  See `docs/opencode.config.example.json`
   for the canonical shape.
2. Restart opencode so it re-runs `python -m flytetest.server` against
   the post-Phase-0 code.
3. Verify the tool list includes `list_slurm_partitions` (new in
   step 05) — if it's missing, the server didn't restart.

## Prompts

For each, the **expected behaviour** column states what to look for in
opencode's response.  If anything is significantly worse, jot it under
*Issues* — those are the Phase 1 priority signals.

### Step 05 — `list_slurm_partitions`

| # | Prompt | Expected behaviour |
|---|---|---|
| 5.1 | "What partitions are available on this cluster?" | Tool call to `list_slurm_partitions`; structured reply with name / state / max_walltime / available_nodes per row.  No prompt for credentials. |
| 5.2 | "Which partition has the most idle nodes right now?" | Same tool call; the LLM should sort by `available_nodes` and answer in plain English. |

### Step 04 — ResourceSpec validators

| # | Prompt | Expected behaviour |
|---|---|---|
| 4.1 | "Prepare a recipe for `germline_short_variant_discovery` with memory `32 GB`, walltime `48h`, partition `caslake`, account `<your-account>`." | Server returns a `PlanDecline` (or equivalent) explaining the format violations.  The error mentions both the bad memory and the bad walltime, ideally with the corrected examples (`32G`, `48:00:00`).  No `.runtime/runs/<id>/` dir gets created. |
| 4.2 | (after a fixed prompt) "Prepare the same recipe with memory `32G` and walltime `48:00:00`." | Recipe freezes successfully; reply carries `recipe_id` and `artifact_path`. |

### Step 03 — `extend_module_loads`

| # | Prompt | Expected behaviour |
|---|---|---|
| 3.1 | "Prepare a recipe for `germline_short_variant_discovery` and add `bcftools/1.20` to the module loads, alongside the GATK/samtools defaults." | Server should freeze with `extend_module_loads=["bcftools/1.20"]` rather than `module_loads`.  The frozen `spec.json` should show `extend_module_loads` populated. |
| 3.2 | "Same prompt, but set `module_loads=["bcftools/1.20"]` instead." | Server still freezes (legacy semantics) but `_LOG.warning` should fire if `extend_module_loads` is also set.  Inspect server stderr for the warning. |
| 3.3 | (flat-tool variant) "Run `vc_germline_discovery` with `extend_module_loads=["bcftools/1.20"]`." | **Expected to fail today** — the 26 flat tools (`vc_*`, `annotation_*`, `rnaseq_*`) accept `module_loads` but not `extend_module_loads`.  This is the gap flagged in `CHANGELOG.md` under the Phase 0 wrap-up entry; if it's the first thing scientists hit, it bumps Phase 1 step 07's priority. |

### Step 02 — `runs/latest` and paths-in-response

| # | Prompt | Expected behaviour |
|---|---|---|
| 2.1 | "Submit the recipe from prompt 4.2 to Slurm." | Reply carries `run_record_path`, `job_id`, `recipe_id` and points the scientist at `cd .runtime/runs/latest`. |
| 2.2 | (separately, after the submit) "Run `cd .runtime/runs/latest && ls -la`" | Should resolve via the symlink to the recipe_id directory; should show `spec.json`, `slurm_run_record.json`, `slurm-<jobid>.{out,err}`, `outputs/`, and `inputs/` (if shared_fs_roots was declared at submit). |
| 2.3 | "Monitor the job from the previous prompt." | `monitor_slurm_job` reply lists `spec_path`, `run_record_path`, `stdout_path`, `stderr_path`, `outputs_dir`, `inputs_dir` as absolute paths.  The scientist should be able to copy any of them directly. |

### Step 01 — Canonical layout + recipe-id hash

| # | Prompt | Expected behaviour |
|---|---|---|
| 1.1 | "Prepare a recipe for `select_germline_short_variant_discovery` with the variant_calling_germline_minimal bundle." | The returned `recipe_id` ends in `-<4 hex chars>` because the target name exceeds 25 chars.  `artifact_path` ends in `/spec.json`, not `<recipe_id>.json`. |
| 1.2 | (compare to step 4.2) "Prepare a recipe for `germline_short_variant_discovery`." | Same target, shorter name (35 chars).  Confirm the recipe_id is `germline_short_variant_dis-<hash4>` (still truncated since 35 > 30). |

### Step 06 — `sbatch --test-only`

| # | Prompt | Expected behaviour |
|---|---|---|
| 6.1 | "Validate the recipe from 4.2 for slurm execution." | `validate_run_recipe` reply carries no `slurm_test_only` findings; `supported: true`. |
| 6.2 | "Prepare a recipe with partition `bogus_xyz` and validate it for slurm." | The validate reply should carry one `slurm_test_only` finding with `reason: partition_invalid` (or similar).  If you instead see `reason: test_only_failed`, the message-classifier table in `staging.py:_TEST_ONLY_REASON_PATTERNS` doesn't match what caslake's `sbatch --test-only` actually emits — patch the table and re-test. |
| 6.3 | "Submit the recipe from 6.2 anyway." | The submit should be blocked by validation up-front (the `_classify_test_only_failure` finding lands in the response).  No real sbatch should be queued. |

### Recovery / decline UX (smoke for §10 channels)

| # | Prompt | Expected behaviour |
|---|---|---|
| R.1 | "Run germline_short_variant_discovery." (no bindings, no inputs) | Decline with §10 recovery channels populated: `suggested_bundles` includes `variant_calling_germline_minimal`, `next_steps` lists `load_bundle`. |

## What to record after each prompt

For each row above, record one of:

- **PASS** — behaviour matched expectation
- **PARTIAL** — feature works but the response is awkward (e.g. paths are present but buried in nested `lifecycle_result.scheduler_snapshot`); jot one line on what to improve
- **FAIL** — feature doesn't work at all through the MCP client; needs Phase 1 fix

The PARTIAL cases feed Phase 1 step 08 (user-friendly failure presentation
layer) and step 10 (state_history / queue ETA) — they're the
"feature was built but didn't pay back" signals.

## Known gap to confirm or refute

The flat-tool `extend_module_loads` propagation (prompt 3.3) is the
biggest known gap.  If 3.3 fails as expected, that's the answer.  If it
works, the audit was wrong and the propagation already landed somewhere
upstream — investigate before drafting Phase 1.

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

> **Why most prompts name a bundle.** The MCP client has to figure out
> where biological bindings come from.  Without a hint, a reasoning
> model will spin trying to invent placeholders or asking the user for
> file paths instead of exercising the feature under test.  The
> ``variant_calling_germline_minimal`` bundle supplies real bindings, so
> a prompt like "use that bundle and prepare with bad walltime" gives
> the model exactly one place to find inputs and one place to mishandle.
> The validator / `--test-only` / hash-suffix / module-load tests then
> isolate cleanly.

### Step 05 — `list_slurm_partitions`

| # | Prompt | Expected behaviour |
|---|---|---|
| 5.1 | "What partitions are available on this cluster?" | Tool call to `list_slurm_partitions`; structured reply with name / state / max_walltime / available_nodes per row.  No prompt for credentials. |
| 5.2 | "Which partition has the most idle nodes right now?" | Same tool call; the LLM should sort by `available_nodes` and answer in plain English. |

### Step 04 — ResourceSpec validators

| # | Prompt | Expected behaviour |
|---|---|---|
| 4.1 | "Load the `variant_calling_germline_minimal` bundle and prepare a recipe for `germline_short_variant_discovery` with `memory: '32 GB'`, `walltime: '48h'`, `partition: 'caslake'`, `account: 'rcc-staff'`." | Server returns a structured decline (or limitation) explaining the format violations.  The error mentions both the bad memory and the bad walltime, ideally with the corrected examples (`32G`, `48:00:00`).  No `.runtime/runs/<id>/` directory should be created. |
| 4.2 | "Same prompt as 4.1 but with `memory: '32G'` and `walltime: '48:00:00'`." | Recipe freezes successfully; reply carries `recipe_id` and `artifact_path` ending in `/spec.json`. |

### Step 03 — `extend_module_loads`

| # | Prompt | Expected behaviour |
|---|---|---|
| 3.1 | "Load the `variant_calling_germline_minimal` bundle and prepare a recipe for `germline_short_variant_discovery` with `extend_module_loads: ['bcftools/1.20']`, `partition: 'caslake'`, `account: 'rcc-staff'`." | Server freezes; the saved `spec.json` shows `resource_spec.extend_module_loads = ["bcftools/1.20"]` and a default `module_loads = []`. |
| 3.2 | "Same prompt as 3.1 but also set `module_loads: ['mymod/1.0']`." | Server still freezes (legacy semantics) but the server log should carry a `[WARNING]` line from `flytetest.spec_executor` saying `module_loads wins`.  Check the server stderr or the captured log; the saved spec should record both fields. |
| 3.3 | (flat-tool variant) "Run `vc_germline_discovery` with the `variant_calling_germline_minimal` bundle and `extend_module_loads: ['bcftools/1.20']`, `partition: 'caslake'`, `account: 'rcc-staff'`, `dry_run: True`." | **Expected to fail today** — the 26 flat tools (`vc_*`, `annotation_*`, `rnaseq_*`) accept `module_loads` but not `extend_module_loads`.  Gap flagged in `CHANGELOG.md` under the Phase 0 wrap-up entry; if it's the first thing scientists hit, it bumps Phase 1 step 07's priority.  ``dry_run`` keeps it cheap. |

### Step 02 — `runs/latest` and paths-in-response

| # | Prompt | Expected behaviour |
|---|---|---|
| 2.1 | "Submit the recipe from prompt 4.2 to Slurm." | Reply carries `run_record_path`, `job_id`, `recipe_id` and points the scientist at `cd .runtime/runs/latest`. |
| 2.2 | (in a shell) `ls -la .runtime/runs/latest` | Should resolve via the symlink to the recipe_id directory; should show `spec.json`, `slurm_run_record.json`, `slurm-<jobid>.{out,err}`, `outputs/`, and `inputs/` (if `shared_fs_roots` was declared at submit). |
| 2.3 | "Monitor the job from the previous prompt." | `monitor_slurm_job` reply lists `spec_path`, `run_record_path`, `stdout_path`, `stderr_path`, `outputs_dir`, `inputs_dir` as absolute paths.  The scientist should be able to copy any of them directly. |

### Step 01 — Canonical layout + recipe-id hash

| # | Prompt | Expected behaviour |
|---|---|---|
| 1.1 | "Load the `variant_calling_germline_minimal` bundle and prepare a recipe for `germline_short_variant_discovery` with `partition: 'caslake'`, `account: 'rcc-staff'`." | Target name is 35 chars (> 30), so the returned `recipe_id` should end in `-<4 hex chars>`, e.g. `20260508T...Z-germline_short_variant_dis-<hash4>`.  `artifact_path` ends in `/spec.json`. |
| 1.2 | "Prepare a recipe for `prepare_reference` with the `variant_calling_germline_minimal` bundle, `partition: 'caslake'`, `account: 'rcc-staff'`." | Short name (17 chars).  recipe_id ends in `-prepare_reference` with no hash suffix — confirms the truncation only kicks in for long names. |

### Step 06 — `sbatch --test-only`

| # | Prompt | Expected behaviour |
|---|---|---|
| 6.1 | "Validate the recipe from prompt 4.2 for slurm execution with `shared_fs_roots: ['/scratch/midway3', '/project/<your-rcc-project>']`." | `validate_run_recipe` reply carries `supported: true` and no `slurm_test_only` findings. |
| 6.2 | "Load the `variant_calling_germline_minimal` bundle and prepare a recipe for `germline_short_variant_discovery` with `partition: 'bogus_xyz'`, `account: 'rcc-staff'`. Then validate it for slurm." | The validate reply should carry one `slurm_test_only` finding with `reason: partition_invalid` (or similar).  If you instead see `reason: test_only_failed`, the regex table in `staging.py:_TEST_ONLY_REASON_PATTERNS` doesn't match what caslake's `sbatch --test-only` actually emits — paste the stderr text back and I'll patch it. |
| 6.3 | "Submit the recipe from 6.2 anyway." | The submit should be blocked at validation (the `slurm_test_only` finding lands in the response).  No real sbatch should be queued. |

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

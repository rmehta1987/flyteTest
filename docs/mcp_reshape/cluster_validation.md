# MCP Reshape — Cluster Validation Checklist

Acceptance gate for the MCP Surface Reshape (Steps 1–30, tracker:
`docs/mcp_reshape/checklist.md`) as exercised against the live FLyteTest
MCP server on RCC.

Scope: validate only the behaviors changed by the reshape. End-to-end
lifecycle coverage (cancel, poll, OOM-retry storyline) lives in
`docs/mcp_cluster_prompt_tests.md`; full biology coverage lives in
`docs/mcp_full_pipeline_prompt_tests.md`. Update those docs once this
checklist passes.

Each check is an independent prompt you paste into an MCP client
(OpenCode) connected to a server started inside an authenticated RCC
login session.

## Prerequisites

- MCP server started from an authenticated RCC login session (CILogon 2FA
  already completed, `sbatch` works from this shell).
- `sbatch`, `squeue`, `scontrol`, `sacct`, `scancel` on `PATH`.
- Minimal BUSCO fixture staged: run
  `scripts/rcc/download_minimal_busco_fixture.sh` if `data/busco/test_data/eukaryota/`
  is missing.
- Minimal container image(s) staged per `scripts/rcc/download_minimal_images.sh`
  for the bundle you plan to exercise.
- User-supplied `account` + `partition` values ready to inject into
  `resource_request`. Do not rely on registry defaults.

## Status Labels

- `Not started`
- `Pass`
- `Fail <short reason>`
- `Blocked <short reason>`

Mark status inline next to each check as it is exercised on cluster.

---

## Group A — Surface sanity (no job submission)

### A1. `list_entries` widening (Step 8)
Status: Not started

Goal: confirm the widened per-entry payload includes
`supported_execution_profiles`, `slurm_resource_hints`, typed binding
fields, and tool-database slots.

Prompt:

```text
Use the flytetest MCP server. Call list_entries.

For annotation_qc_busco print:
- supported_execution_profiles
- slurm_resource_hints
- binding fields (name, type, required)
- tool_databases (name, required)
- runtime_images (name, required)
```

Pass:
- `supported_execution_profiles` contains `"slurm"` and `"local"`.
- `slurm_resource_hints` is a dict with at least `cpus`, `memory`, `runtime`.
- Binding fields list typed `InterfaceField` entries (no prose).
- `tool_databases` includes `busco_lineage` marked required.

### A2. `list_bundles` + bundle availability reporting (Step 30)
Status: Not started

Goal: `list_bundles` reports structural availability honestly and emits
`fetch_hints` when unavailable.

Prompt:

```text
Use the flytetest MCP server. Call list_bundles.

For each bundle print: name, pipeline_family, available, reasons, fetch_hints.

Then for any bundle where available=false, read fetch_hints aloud and
confirm each hint names either a concrete script path or an actionable
verb (pull, stage, download).
```

Pass:
- Every unavailable bundle has non-empty `fetch_hints` pointing at
  `scripts/rcc/download_minimal_images.sh` or `scripts/rcc/README.md`.
- No bundle is simultaneously `available=true` and missing a required
  container/tool database on disk (spot-check one).

### A3. `load_bundle` shape spreads into run tools (Steps 4, 25)
Status: Not started

Goal: `load_bundle(name)` returns a dict that is directly spreadable into
`run_task` / `run_workflow` — keys are exactly
`{bindings, inputs, resources, runtime_images, tool_databases}` (+ optional
`source_prompt`).

Prompt:

```text
Use the flytetest MCP server. Call load_bundle with the smallest available
bundle. Print the top-level keys of the returned dict and the type of
each value.
```

Pass:
- Top-level keys are a subset of `{bindings, inputs, resources,
  runtime_images, tool_databases, source_prompt}`.
- No extra legacy keys (`flat_inputs`, `params`, or pre-reshape names).

### A4. `validate_run_recipe` on a freshly frozen artifact (Step 24)
Status: Not started

Goal: `validate_run_recipe` can inspect a spec written by a prior dry-run
and report `supported=true` with empty findings when nothing is wrong.

Prompt:

```text
Use the flytetest MCP server. Call run_task for annotation_qc_busco with
a loaded bundle and dry_run=true. Capture the artifact_path.

Then call validate_run_recipe against that artifact_path with
execution_profile="slurm". Print supported, recipe_id, execution_profile,
findings.
```

Pass:
- `supported` is `true`.
- `recipe_id` matches `^\d{8}T\d{6}\.\d{3}Z-annotation_qc_busco$`
  (Step 7 format).
- `findings` is empty.

---

## Group B — Typed run surface (local before Slurm)

Exercise these on `execution_profile="local"` first to isolate surface
from scheduler issues. Rerun each as `"slurm"` to gate B5–B8.

### B1. `run_task` with bundle-spread (Step 21)
Status: Not started

Goal: `run_task(**load_bundle(...))` succeeds without any additional
wiring and returns a `RunReply`.

Prompt:

```text
Use the flytetest MCP server. Load the smallest available bundle and
spread it into run_task for the matching task. Set
execution_profile="local". Print supported, recipe_id, run_record_path,
artifact_path, execution_status, named_outputs.
```

Pass:
- `supported=true`, `execution_status="success"`.
- `recipe_id` uses the Step 7 timestamp format.
- `named_outputs` contains at least one entry keyed by output name.

### B2. `run_workflow` with bundle-spread (Step 22)
Status: Not started

Goal: `run_workflow(**load_bundle(...))` is symmetric with B1.

Prompt: as B1, targeting a workflow (e.g. `protein_evidence_alignment`).

Pass: same criteria as B1.

### B3. `dry_run=True` writes artifact, skips dispatch (Steps 21, 22)
Status: Not started

Goal: `dry_run=true` returns a `DryRunReply` with `resolved_bindings` and
`resolved_environment`, and the artifact is on disk.

Prompt:

```text
Use the flytetest MCP server. Call run_task with dry_run=true. Print
resolved_bindings keys, resolved_environment keys, artifact_path.

Then stat the artifact_path to confirm it exists on disk.
```

Pass:
- `resolved_bindings` is keyed by binding name; each value has `type` and
  concrete resolved `path`/`value`.
- No Slurm job was submitted (check `squeue -u $USER`).

### B4. Named-output binding by path (Step 14 grammar)
Status: Not started

Goal: binding a downstream input to an upstream run's named output by
`BindingPath` grammar works (`from_run: <recipe_id>`, `output: <name>`).

Prompt:

```text
Use the flytetest MCP server. Run a task that produces a named output
(e.g. annotation_qc_busco). Capture the recipe_id.

Call run_task for a downstream task whose binding spec references
{from_run: <recipe_id>, output: <name>}. Print the resolved bindings.
```

Pass:
- Downstream resolution succeeds.
- Resolved binding path points at the upstream run record's named
  output, not a raw filesystem guess.

### B5. Typed decline: unknown run id (Steps 3, 13, 20)
Status: Not started

Goal: `BindingPath` referencing a nonexistent recipe id produces a
`PlanDecline` with category mapped to `UnknownRunIdError`.

Prompt:

```text
Use the flytetest MCP server. Call run_task with a binding that
references {from_run: "19700101T000000.000Z-bogus", output: "x"}.
Print supported, limitations, suggested_bundles, suggested_prior_runs,
next_steps.
```

Pass:
- `supported=false`.
- `limitations` names the missing run id.
- `suggested_prior_runs` is populated (or empty with explanation, not
  missing).
- `next_steps` points at `list_bundles` or a concrete recovery tool call.

### B6. Typed decline: unknown output name (Steps 3, 13, 20)
Status: Not started

Goal: referencing a valid run with an unknown `output` returns a decline
naming the available output keys.

Prompt: as B5 but use a real prior `recipe_id` with `output: "nope"`.

Pass:
- Decline mentions the real available output names for that run.
- `next_steps` suggests the correct output name or `validate_run_recipe`.

### B7. Typed decline: binding type mismatch (Steps 3, 13, 20)
Status: Not started

Goal: binding a `GenomeFasta` slot to a binding whose resolved type is,
e.g., `ProteinFasta` produces a `BindingTypeMismatchError`-driven decline.

Prompt: construct a mismatched binding and submit via run_task.

Pass:
- Decline identifies both expected and observed binding types.

### B8. Bundle/prior-run suggestions on generic decline (Step 20)
Status: Not started

Goal: an incomplete but otherwise-valid request gets a `PlanDecline`
with `suggested_bundles` populated from the bundle catalog.

Prompt:

```text
Use the flytetest MCP server. Call run_task for annotation_qc_busco with
no bindings and no inputs.

Print suggested_bundles, suggested_prior_runs, next_steps.
```

Pass:
- `suggested_bundles` contains at least one bundle whose
  `pipeline_family` matches the requested target.

---

## Group C — Slurm-specific reshape behavior

Gate these on B1–B8 passing against local. Use the smallest available
bundle and set `resource_request` with your real `account` and
`partition`.

### C1. `check_offline_staging` short-circuits bad submit (Step 23)
Status: Not started

Goal: deliberately referencing an unreachable container or tool-database
path aborts submission before `sbatch` with structured findings.

Prompt:

```text
Use the flytetest MCP server. Call run_task with
execution_profile="slurm" and override runtime_images to point at a path
that does not exist on the shared filesystem.

Print the full decline payload including findings.
```

Pass:
- No `sbatch` is issued (`squeue -u $USER` shows nothing new).
- Decline findings identify the unreachable path and the failing image
  or tool-database key.

### C2. `recipe_id` format on real submit (Step 7)
Status: Not started

Goal: a successful Slurm submit produces a `recipe_id` matching
`^\d{8}T\d{6}\.\d{3}Z-<target_name>$`.

Prompt: run B1 with `execution_profile="slurm"`, print `recipe_id`.

Pass: regex matches.

### C3. `resource_request.module_loads` override (AGENTS.md)
Status: Not started

Goal: a recipe with `module_loads=["python/3.11.9"]` replaces — does not
append to — the default module list; a recipe with a different module
load is honored on the submitted job.

Prompt:

```text
Use the flytetest MCP server. Run a Slurm task with
resource_request.module_loads=["python/3.11.9", "apptainer/1.4.1",
"gcc/12.2.0"]. After submission, open the generated sbatch script from
the run record and print the `module load` lines.
```

Pass:
- sbatch script contains exactly the listed modules, in order.

### C4. Manifest output keys align with named outputs (Steps 9–11)
Status: Not started

Goal: `run_manifest.json` for a completed Slurm run uses the same output
names as `RunReply.named_outputs`.

Prompt: run B1 on Slurm to COMPLETED, then print `outputs` keys from
`run_manifest.json` alongside `named_outputs` keys from the reply.

Pass: key sets are equal.

### C5. `monitor_slurm_job` `tail_lines` bounds (AGENTS.md)
Status: Not started

Goal: `tail_lines` parameter is honored for terminal jobs (default 50,
max 500, 0 disables).

Prompt:

```text
Use the flytetest MCP server. For a COMPLETED run record, call
monitor_slurm_job three times with tail_lines=0, tail_lines=10,
tail_lines=500. Print the length of stdout_tail and stderr_tail each
time.
```

Pass:
- `tail_lines=0` → empty tails.
- `tail_lines=10` → ≤ 10 lines each.
- `tail_lines=500` → up to 500 lines each, no errors on over-cap request.

### C6. `retry_slurm_job` with `resource_overrides` (AGENTS.md)
Status: Not started

Goal: retrying an OOM/TIMEOUT job with `resource_overrides={memory: "..."}`
submits a new job with escalated resources without mutating the frozen
recipe.

Prompt:

```text
Use the flytetest MCP server. Pick (or induce) a FAILED OOM run record.
Call retry_slurm_job with resource_overrides={memory: "<larger>"}.

Print the new job_id and confirm the original recipe artifact on disk
is byte-identical before and after.
```

Pass:
- New job submitted with escalated memory in sbatch script.
- Original `WorkflowSpec` artifact unchanged (hash/mtime match).

---

## Exit criteria

All A/B/C checks marked `Pass`. Any `Fail` must either:

- be resolved by a code fix and re-run, or
- be explicitly accepted and recorded in
  `docs/mcp_reshape/checklist.md` with a follow-up issue.

Once passed, refresh `docs/mcp_cluster_prompt_tests.md` and
`docs/mcp_full_pipeline_prompt_tests.md` to the reshaped surface and
update `CHANGELOG.md` with the validation date.

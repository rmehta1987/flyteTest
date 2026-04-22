# MCP Cluster Prompt Tests

Five test scenarios for the live FLyteTest MCP server on RCC.  Each scenario
is a prompt you paste into OpenCode (or any MCP client connected to the
server).  The client calls the server tools over JSON-RPC; the server calls
real `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` on the cluster.

These are the live-cluster equivalent of the offline tests in
`tests/test_mcp_prompt_flows.py`.  They cover the same lifecycle paths but
exercise the full transport stack (OpenCode → JSON-RPC → MCP server → Slurm).

---

## Prerequisites

Before running any scenario:

- The MCP server is started from inside an authenticated RCC login session
  (CILogon 2FA already completed — `sbatch` works from this shell).
- `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are on `PATH`.
- OpenCode is connected to the server (stdio transport, no remote SSH).
- The BUSCO minimal fixture data exists: `data/busco/test_data/eukaryota/`
  (run `scripts/rcc/download_minimal_busco_fixture.sh` if not yet present).

Check connectivity before starting:

```text
Use the flytetest MCP server and call list_entries.

Print supported_execution_profiles for every entry.
```

Every entry that lists `"slurm"` in `supported_execution_profiles` is
available for these tests.  You should see `annotation_qc_busco` and
`protein_evidence_alignment` at minimum.

---

## Scenario 1 — Sanity check: list Slurm-capable targets

**Goal:** Confirm the server is reachable and exposes the expected Slurm
targets before submitting any jobs.

**Estimated time:** Seconds (no job submission).

```text
Use the flytetest MCP server.

Call list_entries.

Then print exactly:
- supported
- server_tools  (list all tool names)
- entries where supported_execution_profiles contains "slurm"  (name + slurm_resource_hints)
- limitations
```

**Pass criteria:**

- `supported` is `true`.
- `server_tools` includes `prepare_run_recipe`, `run_slurm_recipe`,
  `monitor_slurm_job`, `cancel_slurm_job`, `retry_slurm_job`,
  `list_slurm_run_history`.
- `annotation_qc_busco` appears in the Slurm-capable entries with
  `slurm_resource_hints` containing `cpu`, `memory`, and `walltime`.
- `limitations` is empty or describes only scope boundaries (not errors).

---

## Scenario 2 — Happy path: load bundle → run task → poll until COMPLETED

**Goal:** Full submit-and-monitor cycle for the BUSCO genome-mode fixture using
the primary scientist loop (`load_bundle` → `run_task`).  Validates the
`final_scheduler_state` polling gate.

**Estimated time:** 5–15 minutes on `caslake` (BUSCO eukaryota fixture is
small).

**Step 2a — Load the starter bundle:**

```text
Use the flytetest MCP server.

Call load_bundle with exactly this argument:
- name: "busco_eukaryota_genome_fixture"

Then print exactly:
- supported
- inputs   (show proteins_fasta, lineage_dataset, busco_mode)
- limitations
```

**Pass criteria for 2a:**

- `supported` is `true`.
- `inputs.proteins_fasta` points to `data/busco/test_data/eukaryota/genome.fna`.
- `inputs.busco_mode` is `"geno"`.
- `limitations` is empty.

---

**Step 2b — Freeze and submit in one step:**

```text
Use the flytetest MCP server.

Call run_task with exactly these arguments:
- task_name: "busco_assess_proteins"
- inputs: <inputs dict from load_bundle>
- runtime_images: <runtime_images dict from load_bundle>
- resources: {"cpu": 2, "memory": "8Gi", "partition": "caslake", "account": "rcc-staff", "walltime": "00:15:00"}
- execution_profile: "slurm"
- source_prompt: "Run BUSCO eukaryota genome-mode fixture for cluster validation"

Then print exactly:
- supported
- recipe_id
- run_record_path
- execution_profile
- limitations
```

**Pass criteria for 2b:**

- `supported` is `true`.
- `recipe_id` is a non-null string (timestamp-target format).
- `run_record_path` is a non-null path ending in `slurm_run_record.json`.
- `execution_profile` is `"slurm"`.
- `limitations` is empty or advisory only.

---

**Step 2c — Poll until terminal:**

Repeat this prompt until `final_scheduler_state` is non-null.  Wait 60–120
seconds between calls while the job is `PENDING` or `RUNNING`.

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path from run_task.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state   (null means keep polling; non-null means stop)
- stdout_path
- stderr_path
- run_record_path
- limitations
```

**Pass criteria for 2c:**

- `supported` is `true` on every call.
- While active: `scheduler_state` is `PENDING` or `RUNNING`;
  `final_scheduler_state` is `null`.
- On completion: `final_scheduler_state` is `COMPLETED`;
  `stdout_path` and `stderr_path` are non-null paths.
- `limitations` is empty (or contains only informational notes).

**If the job fails instead of completing:** See Scenario 4 (retry) or check
the `stderr_path` for the error.  A `FAILED` result with exit code `1:0`
means the BUSCO command itself failed (not an infra failure) — check that the
genome fixture FASTA exists and the `busco_mode` is correct.

---

## Scenario 3 — History: find the submitted job after a session restart

**Goal:** Verify that `list_slurm_run_history` surfaces the job after Scenario 2,
even in a new OpenCode session.  This is the client path for resuming
monitoring after a restart.

**Prerequisite:** Scenario 2, Step 2b (`run_task`) must have been completed in
any prior session (the run record is durable on disk).

```text
Use the flytetest MCP server.

Call list_slurm_run_history with exactly these arguments:
- limit: 5

Then print exactly:
- supported
- returned_count
- entries  (job_id, workflow_name, effective_scheduler_state, run_record_path for each)
- latest_run_record_path
- limitations
```

**Pass criteria:**

- `supported` is `true`.
- `returned_count` is at least 1.
- The most recent entry has the `job_id` from Scenario 2, Step 2b, and
  `workflow_name` contains `"busco"`.
- `latest_run_record_path` matches the `run_record_path` from Scenario 2.

**Bonus — filter by workflow name:**

```text
Use the flytetest MCP server.

Call list_slurm_run_history with exactly these arguments:
- limit: 10
- workflow_name: "annotation_qc_busco"

Then print job_id, effective_scheduler_state, and run_record_path for each entry.
```

---

## Scenario 4 — Cancel idempotency: cancel the same job twice

**Goal:** Verify that calling `cancel_slurm_job` twice on the same run record
returns `supported: true` both times and does NOT issue a second `scancel` to
the scheduler.

**Prerequisite:** Complete Scenario 2, Steps 2a and 2b (`load_bundle` +
`run_task`) to get a `run_record_path` for a submitted job.  This scenario
works best while the job is still `PENDING` or `RUNNING` — cancel it before
it finishes.

**Step 4a — First cancel:**

```text
Use the flytetest MCP server.

Call cancel_slurm_job with the run_record_path from run_slurm_recipe.

Then print exactly:
- supported
- scheduler_state
- limitations
```

**Pass criteria for 4a:**

- `supported` is `true`.
- `scheduler_state` is `"cancellation_requested"`.
- `limitations` is empty.

---

**Step 4b — Second cancel (idempotency check):**

```text
Use the flytetest MCP server.

Call cancel_slurm_job with the same run_record_path as the first cancel.

Then print exactly:
- supported
- scheduler_state
- limitations
```

**Pass criteria for 4b:**

- `supported` is `true` (idempotent — not an error).
- `scheduler_state` is `"cancellation_requested"` (same as first call).
- `limitations` mentions "already requested" or similar — confirms that
  no second `scancel` was issued.

---

**Step 4c — Confirm final state with monitor:**

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the same run_record_path.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state
- limitations
```

**Pass criteria for 4c:**

- After the scheduler processes the cancel: `final_scheduler_state` is
  `"CANCELLED"`.
- `supported` is `true`.

---

## Scenario 5 — Retry: resubmit after a retryable infrastructure failure

**Goal:** Verify that `retry_slurm_job` creates a new `run_record_path` and
new `job_id` for the resubmission, and that the child lifecycle is
independent of the parent.

**Prerequisite:** A retryable terminal run record must exist.  The easiest
way is to use the existing smoke-record helper to synthesise one from a prior
BUSCO submission without waiting for a real `NODE_FAIL`:

```bash
# Run this in the terminal (not in OpenCode) before the prompts below.
# Replace <run_record_path> with the path from Scenario 2, Step 2b.
FLYTETEST_M18_RETRY_SMOKE_STATE=NODE_FAIL \
  python scripts/rcc/m18_make_retry_smoke_record.py <run_record_path>
```

The script prints the path of the synthetic retryable run record.  Use that
path in the prompts below.

**Step 5a — Verify the synthetic record is seen as terminal:**

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path printed by m18_make_retry_smoke_record.py.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state   (expect: NODE_FAIL)
- limitations
```

**Pass criteria for 5a:**

- `final_scheduler_state` is `"NODE_FAIL"` (terminal, retryable).

---

**Step 5b — Retry the failed job:**

```text
Use the flytetest MCP server.

Call retry_slurm_job with the run_record_path of the NODE_FAIL record.

Then print exactly:
- supported
- job_id           (new Slurm job ID for the retry)
- retry_run_record_path   (path to the new child run record)
- limitations
```

**Pass criteria for 5b:**

- `supported` is `true`.
- `job_id` is a new numeric string different from the parent job.
- `retry_run_record_path` is a different path from the parent run record.
- `limitations` is empty.

---

**Step 5c — Poll the child run record to completion:**

Use the `retry_run_record_path` from Step 5b (not the parent path) in the
same polling pattern as Scenario 2, Step 2c:

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the retry_run_record_path from retry_slurm_job.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state
- run_record_path
- limitations
```

**Pass criteria for 5c:**

- While active: `scheduler_state` is `PENDING` or `RUNNING`; polling continues.
- On completion: `final_scheduler_state` is `COMPLETED`.
- `run_record_path` matches the `retry_run_record_path` from Step 5b — confirms
  the child record is independent of the parent.

---

## Scenario 6 — Escalation retry: resubmit after OOM with more memory

**Goal:** Verify that `retry_slurm_job` with `resource_overrides` creates a
new child run record that uses the escalated resources, and that the child
lifecycle reaches COMPLETED or FAILED independently of the parent.

**Prerequisite:** A terminal `OUT_OF_MEMORY` run record must exist.  Use the
smoke-record helper to synthesise one:

```bash
# Run this in the terminal (not in OpenCode) before the prompts below.
# Replace <run_record_path> with a path from a prior BUSCO Slurm submission.
FLYTETEST_M20A_ESCALATION_SMOKE_STATE=OUT_OF_MEMORY \
  python scripts/rcc/m18_make_retry_smoke_record.py <run_record_path>
```

The script prints the path of the synthetic `OUT_OF_MEMORY` record.  Use that
path in the prompts below.

**Step 6a — Verify the synthetic record shows OUT_OF_MEMORY:**

```text
Use the flytetest MCP server.

Call monitor_slurm_job with the run_record_path printed by m18_make_retry_smoke_record.py.

Then print exactly:
- supported
- scheduler_state
- final_scheduler_state   (expect: OUT_OF_MEMORY)
- limitations
```

**Pass criteria for 6a:**

- `final_scheduler_state` is `"OUT_OF_MEMORY"` (terminal, resource_exhaustion class).

---

**Step 6b — Escalation retry with more memory:**

```text
Use the flytetest MCP server.

Call retry_slurm_job with:
  run_record_path: <path from the terminal OUT_OF_MEMORY run>
  resource_overrides: {"memory": "64Gi"}

Then print exactly:
- supported
- job_id                  (new Slurm job ID)
- retry_run_record_path   (path to the child run record)
- limitations
```

**Pass criteria for 6b:**

- `supported` is `true`.
- `job_id` is a new numeric string different from the parent job.
- `retry_run_record_path` is a different path from the parent run record.
- `limitations` is empty.

---

**Step 6c — Confirm the child record carries the escalated memory:**

```text
Use the flytetest MCP server.

Read and print the child run record JSON at retry_run_record_path.
Then print:
- resource_spec.memory    (expect: 64Gi)
- resource_overrides.memory  (expect: 64Gi)
```

**Pass criteria for 6c:**

- `resource_spec.memory` is `"64Gi"`.
- `resource_overrides.memory` is `"64Gi"`.

---

**Step 6d — Poll the child run record:**

Use the same polling pattern as Scenario 2, Step 2c with `retry_run_record_path`.

**Pass criteria for 6d:**

- While active: `scheduler_state` is `PENDING` or `RUNNING`.
- On completion: `final_scheduler_state` is `COMPLETED`.

---

## Quick reference: fields to print for each tool

| Tool | Fields to print |
|---|---|
| `list_entries` | `supported`, `server_tools`, entries with `slurm_resource_hints` |
| `load_bundle` | `supported`, `inputs`, `runtime_images`, `limitations` |
| `run_task` | `supported`, `recipe_id`, `run_record_path`, `execution_profile`, `limitations` |
| `prepare_run_recipe` | `supported`, `artifact_path`, `limitations` |
| `run_slurm_recipe` | `supported`, `job_id`, `run_record_path`, `limitations` |
| `monitor_slurm_job` | `supported`, `scheduler_state`, `final_scheduler_state`, `stdout_path`, `stderr_path`, `run_record_path`, `limitations` |
| `cancel_slurm_job` | `supported`, `scheduler_state`, `limitations` |
| `retry_slurm_job` | `supported`, `job_id`, `retry_run_record_path`, `limitations` |
| `list_slurm_run_history` | `supported`, `returned_count`, entries (`job_id`, `workflow_name`, `effective_scheduler_state`, `run_record_path`) |

## If a tool returns `supported: false`

1. Print the full `limitations` list — it describes the failure in plain text.
2. Check that `sbatch`, `squeue`, `scontrol`, `sacct`, and `scancel` are on
   `PATH` from the shell where the MCP server was started.
3. Check that the `run_record_path` or `artifact_path` argument is a string
   (not a dict) — some clients silently coerce structured fields.
4. If the limitation mentions "schema version": the run record on disk was
   written by an older server version.  Discard it and start a fresh prepare
   + submit cycle.

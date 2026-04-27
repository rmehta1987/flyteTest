# Showcase Demo Cheat Sheet

One-page operator reference for the 20-minute talk in
`docs/showcase_flyte_plain_language.md`. Keep this open in a second window.

**Cluster assumptions:** UChicago RCC Midway3, `partition=caslake`,
`account=rcc-staff`, shared-FS roots `/scratch/midway3` and `/project/rcc`,
GATK + bwa-mem2 SIFs already staged via `bash scripts/rcc/stage_gatk_local.sh`,
`bash scripts/rcc/pull_gatk_image.sh`, `bash scripts/rcc/build_bwa_mem2_sif.sh`.
The MCP server must be running in an authenticated cluster session.

Calls below assume an MCP-connected Claude session (or equivalent Python REPL
that imports from `flytetest.server`). Bundle inputs are pipeline-shared, so
each `run_workflow` call constructs its own scalars — see Part 1 audit.

---

## T-Morning (kick off the long evidence run)

Morning of the talk, ~2 hours before showtime. This produces the joint VCF
you'll show in Scene 4 as "what a finished receipt looks like."

```python
bundle = load_bundle("variant_calling_germline_minimal")
assert bundle["supported"], bundle.get("reasons")

evidence = run_workflow(
    workflow_name="germline_short_variant_discovery",
    bindings=bundle["bindings"],
    inputs={
        "reference_fasta": bundle["inputs"]["ref_path"],
        "sample_ids": ["NA12878_chr20"],
        "r1_paths": [bundle["inputs"]["r1_path"]],
        "r2_paths": [bundle["inputs"]["r2_path"]],
        "known_sites": bundle["inputs"]["known_sites"],
        "intervals": bundle["inputs"]["intervals"],
        "cohort_id": bundle["inputs"]["cohort_id"],
    },
    runtime_images=bundle["runtime_images"],
    tool_databases=bundle["tool_databases"],
    execution_profile="slurm",
    resource_request={
        "partition": "caslake",
        "account": "rcc-staff",
        "cpu": "16",
        "memory": "64Gi",
        "walltime": "04:00:00",
        "shared_fs_roots": ["/scratch/midway3", "/project/rcc"],
    },
    dry_run=True,
)

# Inspect the artifact, then submit:
EVIDENCE_ARTIFACT = evidence["artifact_path"]
print(EVIDENCE_ARTIFACT)
print(evidence["staging_findings"])  # must be empty before submitting

evidence_run = run_slurm_recipe(
    artifact_path=EVIDENCE_ARTIFACT,
    shared_fs_roots=["/scratch/midway3", "/project/rcc"],
)
print(evidence_run["job_id"], evidence_run["run_record_path"])

# Save these for Scene 4:
EVIDENCE_RECORD = evidence_run["run_record_path"]
```

Expected walltime: 45–120 min (per `docs/mcp_variant_calling_cluster_prompt_tests.md`).
Verify it reached `final_scheduler_state=COMPLETED` before the talk:

```python
status = monitor_slurm_job(run_record_path=EVIDENCE_RECORD)
assert status["final_scheduler_state"] == "COMPLETED", status
```

If it didn't complete: drop the "completed receipt" beat from Scene 4 and
show the artifact JSON only. Don't talk around a half-finished job.

---

## T+0 — Scene 1 of the talk: discover (and quietly submit live job)

While narrating Scene 1, run these. The discover part is the demo; the
submit is the live job that will be done by Scene 4.

```python
# On screen — the lab menu:
list_entries()                                  # 45 showcase entries
list_bundles(pipeline_family="variant_calling") # 2 bundles
bundle = load_bundle("variant_calling_germline_minimal")

# Off screen (or in a side terminal) — kick off the live job:
live = run_workflow(
    workflow_name="prepare_reference",
    bindings=bundle["bindings"],
    inputs={
        "reference_fasta": bundle["inputs"]["ref_path"],
        "known_sites": bundle["inputs"]["known_sites"],
    },
    runtime_images=bundle["runtime_images"],
    tool_databases=bundle["tool_databases"],
    execution_profile="slurm",
    resource_request={
        "partition": "caslake",
        "account": "rcc-staff",
        "cpu": "4",
        "memory": "16Gi",
        "walltime": "01:00:00",
        "shared_fs_roots": ["/scratch/midway3", "/project/rcc"],
    },
    dry_run=True,
)
LIVE_ARTIFACT = live["artifact_path"]

live_run = run_slurm_recipe(
    artifact_path=LIVE_ARTIFACT,
    shared_fs_roots=["/scratch/midway3", "/project/rcc"],
)
LIVE_RECORD = live_run["run_record_path"]
print(live_run["job_id"], LIVE_RECORD)
```

Expected walltime: 5–15 min. Submitted at ~minute 4 of the talk → near-done
or done by Scene 4 at ~minute 14.

---

## T+5 — Scene 2: freeze a run (on screen)

Re-use the `live` dry-run reply from Scene 1. Make the artifact physical:

```bash
# In a terminal pane visible to the audience:
cat "$LIVE_ARTIFACT" | jq '{
  recipe_id, target_name,
  binding_plan: .binding_plan.target_kind,
  workflow_spec: {nodes: (.workflow_spec.nodes | length),
                  runtime_images: .workflow_spec.runtime_images,
                  resources: .workflow_spec.resource_spec}
}'
```

Talk track: "This is the written protocol for this run. Resolved inputs.
Exact container. Resource ask. Frozen before Slurm sees it."

---

## T+8 — Scene 3: validate cluster readiness

```python
validate = validate_run_recipe(
    artifact_path=LIVE_ARTIFACT,
    execution_profile="slurm",                              # required
    shared_fs_roots=["/scratch/midway3", "/project/rcc"],
)
print(validate["supported"])    # True
print(validate["findings"])     # [] when everything is reachable
```

If you forget `execution_profile="slurm"`, the shared-FS check is silently
skipped. The framing line in the talk depends on this kwarg.

---

## T+14 — Scene 4: submit and monitor

The live job submitted at T+0 should now be near-done or done. Then pivot
to the pre-staged evidence run record.

```python
# Live job — show real-time state:
status = monitor_slurm_job(run_record_path=LIVE_RECORD)
print(status["job_id"])
print(status["scheduler_state"])         # RUNNING or COMPLETED
print(status["final_scheduler_state"])   # COMPLETED if done
print(status["stdout_path"], status["stderr_path"])

# Pre-staged evidence — show what a finished receipt looks like:
done = monitor_slurm_job(run_record_path=EVIDENCE_RECORD)
print(done["final_scheduler_state"])     # COMPLETED
print(done["lifecycle_result"])          # full record dict
```

Then `cat` the run record file to make the "durable receipt" claim
physical:

```bash
cat "$EVIDENCE_RECORD" | jq '{
  job_id, recipe_id,
  scheduler: {submitted_at, started_at, final_scheduler_state, exit_code},
  artifacts: {stdout_path, stderr_path, run_record_path},
  resources: .resource_spec
}'
```

---

## T+16 — Scene 5: retry without changing the science

You don't actually need a failing job for this beat. Either:

(a) Show the API surface against a deliberately-failed prior record (kept
    around from a previous OOM), or
(b) Just talk through the call shape:

```python
# Valid override keys: cpu, memory, walltime, partition, account, gpu
retry = retry_slurm_job(
    run_record_path="<some-prior-OOM-record>",
    resource_overrides={"memory": "48Gi", "walltime": "06:00:00"},
)
print(retry["retry_run_record_path"])  # links back to the original
```

Talking point: same frozen recipe, escalated resources, original record
preserved. The biological plan does not change.

---

## Contingencies

| Situation | What to do |
|---|---|
| Live `prepare_reference` still QUEUED at Scene 4 | Show `scheduler_state=PENDING` + `job_id`; pivot to evidence record immediately. Frame as "real cluster, real queue, this is what scheduling looks like." |
| Live job FAILED (e.g., container moved) | This is actually a good demo — show `final_scheduler_state=FAILED` + the stdout/stderr tail in `status`, then run a `retry_slurm_job` with corrected resources. Turns the gaffe into Scene 5. |
| Evidence run incomplete | Drop the "completed receipt" pivot. Stay on the live `prepare_reference` artifact + monitor; lengthen Scene 2 instead. |
| Network or 2FA glitch on cluster session | Skip Slurm entirely. Run the same `run_workflow` call with `execution_profile="local"` against the local executor; show the run record on local disk. Soften "the cluster" → "the executor." |
| Audience asks for BRAKER3 mid-talk | Pre-staged annotation record (if you ran one): show `monitor_slurm_job` against it. Otherwise: "same machinery, different family — the catalogue lists annotation workflows; happy to run one offline and send the record." Don't try live. |

---

## Pre-flight checklist (run T-1h)

```bash
# 1. Bundle is available (no missing fixtures):
python3 -c "from flytetest.bundles import load_bundle; \
  b = load_bundle('variant_calling_germline_minimal'); \
  print(b['supported'], b.get('reasons', []))"

# 2. SIFs reachable from compute nodes (probe from a login session):
ls -lh data/images/gatk4.sif data/images/bwa_mem2.sif

# 3. Slurm tooling available:
which sbatch squeue sacct scancel

# 4. MCP server up:
ps aux | grep "flytetest.server"
```

If any of these fail, fix before the talk; do not fix on stage.

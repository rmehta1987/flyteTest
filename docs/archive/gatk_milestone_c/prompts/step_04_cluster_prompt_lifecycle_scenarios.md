# Step 04 — Cancel, Retry, and Escalation Scenarios

## Model

**Haiku 4.5** (`claude-haiku-4-5-20251001`). This is the most mechanical
step in Milestone C: near-verbatim adaptation of Scenarios 4, 5, and 6
from `docs/mcp_cluster_prompt_tests.md`, swapping the BUSCO target for
`haplotype_caller` and `run_task` arguments from the
`variant_calling_germline_minimal` bundle. The logic, pass criteria,
and smoke-record helper usage are identical. Haiku is sufficient and
keeps cost low.

## Goal

Append three scenarios (Scenarios 6–8, continuing the numbering from
Step 03) to `docs/mcp_variant_calling_cluster_prompt_tests.md`:

- Scenario 6 — Cancel idempotency (two `cancel_slurm_job` calls on the
  same run record).
- Scenario 7 — Retry after `NODE_FAIL`.
- Scenario 8 — Escalation retry after `OUT_OF_MEMORY`.

## Context

- Reference source: `docs/mcp_cluster_prompt_tests.md` — Scenarios 4
  (cancel idempotency, lines 214–286), 5 (retry, lines 290–376), and
  6 (escalation retry, lines 379–467).
- Smoke-record helper already exists at
  `scripts/rcc/make_m18_retry_smoke_record.sh` — reuse verbatim; do
  not create a new helper.
- `classify_slurm_failure()` semantics must not change (Milestone C is
  documentation-only).
- Target task for all three scenarios: `haplotype_caller` (shorter
  walltime than a full workflow, easier to cancel / fail cleanly).

## Inputs to read first

- `docs/mcp_cluster_prompt_tests.md` lines 214–467 — the three
  reference scenarios. Copy their section layout, Step-letter
  breakdown, and Pass-criteria bullets exactly.
- `scripts/rcc/make_m18_retry_smoke_record.sh` — confirm argument
  shape (`<run_record_path>` + `NODE_FAIL` | `OUT_OF_MEMORY`).
- Step 02 output: `docs/mcp_variant_calling_cluster_prompt_tests.md`
  already has a `run_task(task_name="haplotype_caller", …)` prompt
  block in Scenario 2 Step 2b. Reuse its argument shape.

## What to build

Append to `docs/mcp_variant_calling_cluster_prompt_tests.md`, **after
Scenario 5 and before the Quick-reference table**.

### Scenario 6 — Cancel idempotency

Mirror `mcp_cluster_prompt_tests.md` Scenario 4 exactly:

- Goal, estimated time, Prerequisite (Scenarios 2a + 2b completed to
  get a `run_record_path` while the job is still `PENDING` or
  `RUNNING`).
- **Step 6a** — first `cancel_slurm_job`. Pass criteria:
  `supported: true`, `scheduler_state: "cancellation_requested"`,
  empty `limitations`.
- **Step 6b** — second `cancel_slurm_job` (idempotency). Pass
  criteria: `supported: true`, same `scheduler_state`, `limitations`
  mentions "already requested".
- **Step 6c** — `monitor_slurm_job` confirming
  `final_scheduler_state: "CANCELLED"`.

### Scenario 7 — Retry after NODE_FAIL

Mirror `mcp_cluster_prompt_tests.md` Scenario 5 exactly, swapping BUSCO
references for `haplotype_caller`:

- Goal, Prerequisite (a retryable terminal run record; synthesise with
  `bash scripts/rcc/make_m18_retry_smoke_record.sh <run_record_path> NODE_FAIL`
  using the run record from Scenario 2b).
- **Step 7a** — `monitor_slurm_job` confirms synthetic record shows
  `final_scheduler_state: "NODE_FAIL"`.
- **Step 7b** — `retry_slurm_job` issues a new `job_id` and
  `retry_run_record_path`. Pass criteria: new numeric `job_id`, new
  path, empty `limitations`.
- **Step 7c** — poll child record to `COMPLETED` using the child
  `retry_run_record_path` (never the parent).

### Scenario 8 — Escalation retry after OUT_OF_MEMORY

Mirror `mcp_cluster_prompt_tests.md` Scenario 6 exactly, swapping BUSCO
for `haplotype_caller`:

- Goal, Prerequisite (synthesise with
  `bash scripts/rcc/make_m18_retry_smoke_record.sh <run_record_path> OUT_OF_MEMORY`).
- **Step 8a** — `monitor_slurm_job` confirms
  `final_scheduler_state: "OUT_OF_MEMORY"`.
- **Step 8b** — `retry_slurm_job` with
  `resource_overrides: {"memory": "64Gi"}`. Pass criteria as in
  reference Scenario 6 Step 6b.
- **Step 8c** — read child run record JSON; assert
  `resource_spec.memory == "64Gi"` and
  `resource_overrides.memory == "64Gi"`.
- **Step 8d** — poll child record to `COMPLETED`.

### Separator and ordering

- Use `---` between scenarios, matching the existing doc convention.
- Ensure the scenario numbering is strictly monotonic after append
  (Scenarios 1, 2, 3, 4, 5, 6, 7, 8).

## Files to create or update

- `docs/mcp_variant_calling_cluster_prompt_tests.md` (append only; do
  not touch existing scenarios).
- `CHANGELOG.md`.
- `docs/gatk_milestone_c/checklist.md` (mark Step 04 Complete).

## CHANGELOG

```
### GATK Milestone C Step 04 — Cluster lifecycle scenarios (YYYY-MM-DD)

- [x] YYYY-MM-DD added Scenario 6 (cancel idempotency) for haplotype_caller.
- [x] YYYY-MM-DD added Scenario 7 (NODE_FAIL retry).
- [x] YYYY-MM-DD added Scenario 8 (OUT_OF_MEMORY escalation retry).
```

## Verification

```bash
rg -n "^## Scenario [678] " docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "make_m18_retry_smoke_record.sh" docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "cancellation_requested" docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "NODE_FAIL|OUT_OF_MEMORY" docs/mcp_variant_calling_cluster_prompt_tests.md
rg -n "resource_overrides" docs/mcp_variant_calling_cluster_prompt_tests.md
rg "async def|await |asyncio\.gather|\.cid\b|IPFS|Pinata|TinyDB" docs/mcp_variant_calling_cluster_prompt_tests.md
# Scenario count must be exactly 8 and strictly monotonic
rg -n "^## Scenario " docs/mcp_variant_calling_cluster_prompt_tests.md | awk -F'Scenario ' '{print $2}' | awk '{print $1}'
```

First five must return matches; the Stargazer grep gate must return
zero hits; the final `awk` must emit `1 2 3 4 5 6 7 8`.

## Commit message

```
variant_calling: add cancel/retry/escalation cluster scenarios (Milestone C Step 04)
```

## Checklist

- [ ] Three scenarios appended (6, 7, 8) in order.
- [ ] Every `task_name` in the prompt blocks is `haplotype_caller`
  (not BUSCO).
- [ ] Smoke-record helper path is `scripts/rcc/make_m18_retry_smoke_record.sh`.
- [ ] Pass criteria match the reference doc exactly.
- [ ] Stargazer grep gate passes.
- [ ] Scenario numbering monotonic 1–8.
- [ ] CHANGELOG updated.
- [ ] Step 04 marked Complete in checklist.

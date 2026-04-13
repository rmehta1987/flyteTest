# Assessment: Current-State Response to `synchronous-twirling-panda.md`

## Context

You asked for a verbose agree / disagree / critique / expansion on
`synchronous-twirling-panda.md`, grounded in the current state of the project
after reading `DESIGN.md`, `CHANGELOG.md`, and `docs/capability_maturity.md`.

This is an analytical planning document. It does not propose code changes by
itself, and it should not be read as a replacement for the canonical tracker in
`docs/realtime_refactor_checklist.md`.

The important current-state correction is that `synchronous-twirling-panda.md`
was written across a moving target. Several of its conclusions are still useful,
but a few are now stale because the repository has since moved forward:

- `DESIGN.md` already uses the authenticated-session `sbatch` Slurm model.
- `CHANGELOG.md` records Milestone 19 Core Phase A as complete on 2026-04-12.
- `docs/capability_maturity.md` still marks caching / resumability as `Far`,
  which is directionally fair for resume and cache-key behavior but too coarse
  now that durable local run records exist.
- `docs/realtime_refactor_checklist.md` contains both an older "Status: Not
  started" line for Milestone 19 and completed Phase A checklist items, so the
  detailed bullets are more current than the summary status line.

---

## Summary Verdict

I mostly agree with the direction of `synchronous-twirling-panda.md`, but I
would revise its prioritization and status model.

The plan is strongest where it says the project should keep platform safety
ahead of broad biology expansion. The design documents support that view:
dynamic workflow composition is allowed, but only through typed, saved,
reviewable `WorkflowSpec` / `BindingPlan` artifacts and registered biological
stages. `CHANGELOG.md` also shows that the project has been moving exactly that
way: first Slurm run records, then retry and cancellation, then composition
approval gating, and now local durable run records.

Where I disagree is with the document's stale framing of the next unlock.
The next unlock is no longer "start M19" or "update DESIGN.md Section 7.4."
The next unlock is:

1. Finish Milestone 19 Phase B: local resume semantics from `LocalRunRecord`.
2. Finish Milestone 19 Phase C: deterministic cache identity, Slurm parity, and
   explicit approval acceptance for composed execution.
3. Update the maturity and checklist docs so they distinguish "durable record
   exists" from "resume / cache reuse is safe."

That is a sharper gate than the panda plan's original P1. It reflects where the
repo is now, not where it was before the 2026-04-12 design-alignment and Phase A
work landed.

---

## What's Working Well (Aligned With Design)

### 1. The Frozen Recipe Boundary Is Real

I strongly agree with the panda plan's praise here. The core invariant in
`DESIGN.md` is:

> Dynamic interpretation happens before execution.

The project now has a meaningful implementation of that idea. Planning produces
typed recipe artifacts, execution consumes saved artifacts, and Slurm submission
is tied to frozen records instead of ad hoc shell behavior. This is the right
architecture for a prompt-facing biology platform because it lets the interface
be conversational without making the executor improvisational.

### 2. The Slurm Topology Is Now a Design Decision, Not a Divergence

The panda plan correctly identified that raw `sbatch` from an authenticated
session is the right model for this environment. The stale part is that it still
says `DESIGN.md` needs to be updated.

Current `DESIGN.md` already says the supported topology is a local MCP/server
process running inside an already-authenticated scheduler-capable session. It
also explicitly says FLyteTest renders `sbatch` scripts and drives `sbatch`
directly instead of delegating to a separate Flyte Slurm plugin.

So I agree with the architectural critique, but disagree with the remaining
action item. That action is already complete according to `CHANGELOG.md`.

### 3. Slurm Lifecycle Handling Is a Real Capability

`docs/capability_maturity.md` marks Slurm/HPC execution integration as
`Current`, and that matches the changelog. The platform can submit, record job
IDs, reconcile with scheduler commands, cancel, and retry scheduler-classified
failures from frozen recipes.

The panda plan is also right to distinguish this from richer HPC ergonomics.
Current Slurm support is real, but it is not yet a polished operator console.
Log tailing, list-runs, resource-escalation retry, module customization, and
dependency chains are still valid follow-on items.

### 4. The Biological Annotation Baseline Is No Longer the Main Risk

The current annotation path is strong through AGAT, with `table2asn` remaining
the explicit deferred terminal submission-prep stage. The bigger risks now are
not "can the project represent an annotation pipeline?" They are:

- Can composed DAGs resume safely?
- Can users recover from HPC failures without reconstructing recipes manually?
- Can result manifests and run records be discovered and inspected through MCP?
- Can the platform add a second workflow family without blurring the current
  annotation pipeline boundaries?

This supports the panda plan's two-track model: platform first, biology
expansion second.

### 5. Deterministic Planning Is a Feature, Not Just a Limitation

I agree with the panda plan that the planner is not a broad LLM-backed natural
language reasoner. But I would not frame that as a defect right now.

`DESIGN.md` is explicit that the system must not invent unregistered biological
steps. The current deterministic, registry-constrained planning path is exactly
the conservative implementation one would want before adding more flexible
language interpretation. The architecture can later place an LLM in front of
the same typed planner boundary, but the repo should not add that until
workflow coverage, validation, and recipe replay are stronger.

---

## Gaps Between Current State and Design Goals

### Gap 1: Milestone 19 Is In Progress, Not Not Started

The panda plan says Milestone 19 is not started. That is stale.

`CHANGELOG.md` records that the repo now has:

- `LocalRunRecord(SpecSerializable)`
- a local run-record schema version
- persisted per-node completion state
- persisted node outputs and final outputs
- `created_at` / `completed_at`
- resolved planner inputs and assumptions
- save/load helpers
- optional `run_root` persistence in `LocalWorkflowSpecExecutor`
- four Phase A tests
- a full-suite result of 241 passing tests and one live-Slurm smoke skipped

That is not "caching/resumability complete," but it is a real architectural
slice. The right status is:

| Slice | Current read |
|---|---|
| Durable local run records | Complete |
| Local resume from record | Missing |
| Deterministic cache keys | Missing |
| Slurm parity with local run-state model | Missing |
| Approval acceptance for composed execution | Missing |
| Async Slurm monitoring | Later follow-on |

### Gap 2: Maturity Documentation Is Too Coarse Around Caching

`docs/capability_maturity.md` currently says caching / resumability is `Far`
because the code does not use cache keys, stage completion state, or replayable
resume rules in a meaningful way.

After Phase A, I would split that capability into finer entries instead of
changing the whole row to `Close` or `Current`:

| Capability | Better status |
|---|---|
| Durable local execution records | Current |
| Local resume semantics | Far or Close, depending on implementation start |
| Deterministic cache identity | Far |
| Slurm resumability parity | Far |
| Safe execution of composed DAGs | Blocked on M19 Phase B/C |

That avoids overstating Phase A while still acknowledging that meaningful
progress landed.

### Gap 3: The Checklist Summary Has Drifted

`docs/realtime_refactor_checklist.md` still says:

> Status: Not started; split into core resumability phases plus a separate async
> monitoring follow-on

But the Phase A checklist items under that heading are complete. The detailed
items are more current than the heading. The next docs cleanup should change
the summary to something like:

> Status: In progress; Core Phase A complete, Phase B/C remaining.

That is not a design problem, but it matters because this repo uses docs as
agent memory.

### Gap 4: The Flyte-Managed Execution Story Remains Ambiguous

I agree with the panda plan that Flyte-managed remote execution is still `Far`.
`docs/capability_maturity.md` says the repo mostly uses `flyte run --local` and
does not show a real backend deployment.

I would not rush to solve this. The authenticated-session Slurm path is a
better fit for the current HPC constraint than a remote Flyte backend that
cannot submit without unattended scheduler access. But `DESIGN.md` still keeps
Flyte-managed execution as a broad execution mode. Eventually, the repo should
decide whether that is:

- a real future execution target,
- a compatibility goal for local Flyte workflow semantics,
- or an aspirational note that should be narrowed.

My current recommendation is to keep it as a compatibility and type-boundary
goal, not a near-term deployment goal.

### Gap 5: MCP Discoverability Still Lags Behind Execution Capability

The panda plan is right that the MCP surface is narrower than the design
target. The highest-value missing pieces are not flashy:

- inspect a saved result manifest,
- list saved recipes and run records,
- describe required runtime bindings before recipe preparation,
- return better missing-input and schema mismatch diagnostics,
- summarize log tails on Slurm failures.

These are not execution engine changes. They are what turn a working system
into one a biologist can debug without knowing the internals.

### Gap 6: Storage-Native Asset Return Should Stay Later

I agree that storage-native durable asset return is `Far`, but I would be more
careful than the panda plan about importing Stargazer-style storage patterns too
early.

`DESIGN.md` and `docs/capability_maturity.md` both warn against making a
database or remote asset index a prerequisite for the current architecture. A
filesystem-backed run-record and manifest browser is the right first step. A
TinyDB / SQLite result index may be useful later, but it should be demand-led
after `list_runs`, `inspect_result`, and read-only MCP resources exist.

---

## Milestone Sequencing Assessment

### What I Agree With

- Platform gates biology expansion.
- `table2asn` is the only near-term biology feature small enough to run beside
  the remaining M19 work.
- GATK is the most valuable large new workflow family if Stargazer provides a
  credible source implementation.
- scRNA-seq and structural variants should not outrank core platform safety.
- HPC recovery and observability matter more than cosmetic MCP expansion.
- Stargazer should be treated as a reference, not a wholesale architecture
  donor.

### What I Disagree With

I disagree with keeping `DESIGN.md` Section 7.4 update in P1. It is done.

I disagree with saying M19 is not started. It is in progress, with Phase A
complete and Phase B/C remaining.

I disagree with treating natural-language intelligence as an urgent gap. The
current deterministic planner is safer for this stage of the project. More
flexible language interpretation should remain behind the frozen recipe and
registered-stage boundary.

I disagree with giving result indexing too much near-term weight. A durable
asset index is valuable, but first the project needs run-record listing and
manifest inspection through MCP.

I partially disagree with making Slurm job dependency chains a near-term
platform item. They are useful for GATK, but they can also fragment execution if
they become a user-managed chain of separate jobs instead of an execution-layer
representation of a frozen recipe graph. Add them when the GATK integration
requires them, and keep them subordinate to saved recipe semantics.

### What I Would Expand

The panda plan should distinguish three different kinds of "retry" and not let
them blur:

| Concept | Current state | Meaning |
|---|---|---|
| Slurm scheduler retry | Current | Resubmit scheduler-classified retryable failures from the frozen recipe. |
| Resource-escalation retry | Missing | Resubmit after OOM/TIMEOUT with explicit audited resource overrides. |
| Resume from completed stages | Missing | Skip completed nodes and rerun only missing or invalidated stages. |

Those are separate user stories, even though all three are failure-recovery
features.

---

## Recommendations

1. **Update the panda plan's P1 status.** Replace "M19 not started" with "M19
   Phase A complete; Phase B/C are the blocker." Remove the `DESIGN.md` Slurm
   update from the prerequisite list.

2. **Make M19 Phase B the next critical-path implementation target.** Local
   resume from `LocalRunRecord` is the next meaningful unlock because it proves
   the durable record can control execution, not just document it after success.

3. **Make M19 Phase C the composed-DAG execution gate.** Do not enable execution
   of registry-composed DAGs until deterministic cache identity, Slurm parity,
   and explicit approval acceptance are in place.

4. **Patch documentation drift after Phase B or as a tiny cleanup now.** At
   minimum, `docs/realtime_refactor_checklist.md` should stop saying M19 is not
   started. `docs/capability_maturity.md` should eventually split durable local
   records from true resume/cache reuse.

5. **Treat `table2asn` as the only biology item allowed to run near M19.** It
   completes the existing annotation path and should not require broad platform
   changes.

6. **Defer GATK integration until after Phase B and the HPC recovery bundle.**
   GATK is valuable, but it will stress Slurm resources, manifests, runtime
   bindings, and multi-stage execution. It should not be the feature that
   discovers resume semantics are incomplete.

7. **Prioritize user recovery before user convenience.** Resource-escalation
   retry, module loading, log tailing, and list-runs should outrank email
   notifications, guided mode, and storage indexing.

8. **Keep Stargazer imports pattern-compatible with FLyteTest.** Reuse task
   command knowledge where helpful, but wrap it in FLyteTest's `run_tool()`,
   manifest, registry, planner, and saved-recipe idioms.

---

---

## Biological Workflow Expansion Opportunities

### What I Agree With From the Panda Plan

`table2asn` is the obvious first biology expansion. It is not really an
expansion into a new family; it is the deferred terminal stage of the existing
annotation path.

GATK germline short variant calling is the highest-value new family because it
is common, resource-intensive enough to justify the Slurm work, and likely
well-covered by Stargazer patterns.

Genome assembly QC is a good companion because it sits before annotation and
can reuse some existing concepts, especially BUSCO, without forcing the project
into a new multi-omics domain.

Differential expression is a natural downstream of existing Salmon
quantification, but it introduces an R/Bioconductor runtime pattern and should
wait until container/module configuration is less brittle.

scRNA-seq is valuable but domain-divergent. It should be demand-driven rather
than placed near the top of the roadmap.

Structural variant calling should depend on the DNA alignment and variant
calling foundation. It is not a first-wave item.

### What I Would Change

I would move "genome assembly QC" closer to the annotation roadmap than the
panda plan does. If `table2asn` is B1 and GATK is B2, assembly QC can be B1.5:
small enough to be tractable, close enough to annotation to fit current
biological scope, and useful before researchers commit compute to a long
annotation run.

I would keep GATK tasks separate from GATK workflow integration. Additive task
files are low conflict, but planner and MCP integration touches shared surfaces
that should wait until P2 observability and recovery are stable.

I would not import Stargazer's content-addressable storage ideas as part of the
GATK work. FLyteTest's design is recipe-first and local-manifest-first; storage
can evolve later.

---

### Proposed Expansion TODOs (Reframed)

#### TODO B1: `table2asn` Submission Preparation

**Agree.** This is the cleanest biology item to keep near the critical path.

**Why:** It completes the current annotation story without redefining the
platform. It consumes the AGAT-cleaned GFF3 and genome FASTA boundary that the
project already understands.

**Condition:** Keep it as a small task/workflow/registry/docs/test slice. Do
not use it as a reason to widen generic submission or NCBI integration behavior
beyond the documented tool boundary.

#### TODO B1.5: Genome Assembly QC

**Expand.** I would give this a named near-term slot after `table2asn`.

**Why:** The current annotation path assumes a reference genome is acceptable.
QUAST and BUSCO genome mode fit naturally before annotation and help users
decide whether an expensive annotation run is worth starting.

**Condition:** Keep BUSCO genome mode distinct from the existing protein-mode
BUSCO QC boundary. Reusing infrastructure is good; conflating biological
meaning is not.

#### TODO B2: GATK Germline Short Variant Calling

**Agree, but gate harder.** This is the best large new family, but it should
start only after the platform can recover from interrupted and resource-failed
runs more cleanly.

**Recommended shape:**

- B2a: new task modules only, adapted from Stargazer patterns.
- B2b: workflows and planner types after local resume semantics land.
- B2c: registry, MCP, Slurm, and composition metadata after HPC observability
  and recovery are stable.

**Condition:** Do not let GATK become a storage rewrite, async orchestration
rewrite, or remote Flyte backend project.

#### TODO B3: Differential Expression

**Agree, but place after GATK task proof or demand signal.**

**Why:** It extends an existing RNA-seq quantification path and is likely useful
to users.

**Concern:** It introduces R/Bioconductor container management. That makes
configurable module loading and clearer runtime binding discovery more
important before implementation.

#### TODO B4: scRNA-seq

**Defer.** This should be collaborator-driven.

**Why:** It is a different biological domain and would require new planner
objects, result types, and likely a different result-inspection vocabulary.

**Condition:** Start only when the repo has a specific user story, not because
Stargazer has code that can be ported.

#### TODO B5: Structural Variants

**Defer behind GATK.**

**Why:** SV calling depends on a mature DNA alignment / variant analysis
foundation. It should not compete with the first short-variant pipeline.

---

## Engineering TODOs: Current-State Critique

### TODO 7: Configurable Module Loading

**Agree.** This is high value and low effort.

I would keep it near the front of P2 because it affects whether Slurm jobs can
run in real cluster environments. The design already treats offline compute
nodes and explicit runtime assumptions as first-class. Hardcoded module loads
are a weak point in that story.

**Caution:** Prefer a small Slurm-specific environment field over bloating
generic `ResourceSpec` if the module list is not meaningful outside Slurm.

### TODO 8: Job Output Log Fetching

**Agree.** This is an observability gap.

Returning stdout/stderr paths is useful for audit, but not sufficient for an
MCP user trying to debug a failed job from a conversational client. Add bounded
tail content and keep full logs on disk.

**Caution:** Never stuff large logs into MCP responses. Tail lines, byte limits,
and "file not readable yet" diagnostics should be explicit.

### TODO 9: Resource-Escalation Retry

**Strongly agree, but name the audit boundary clearly.**

The current Slurm retry policy handles scheduler-classified retryable failures.
Resource-escalation retry is different: it intentionally changes the resource
directives for a child attempt. That is acceptable only if the child record
clearly records the override and keeps the original frozen recipe unchanged.

This should be part of the first P2 bundle after core M19 resume work.

### TODO 10: Job Arrays

**Defer.**

Arrays are useful, but they force a harder question: is one recipe now many
executions, or is the array one execution with indexed child records? That
should wait until the run-record model is stable.

### TODO 11: Wait-for-Completion

**Partially agree, but keep it after core observability.**

A synchronous wait tool is useful, but async monitoring is already identified
as a follow-on in the checklist. Do log tailing, list-runs, and record
inspection first. Then add waiting as a convenience wrapper around those stable
primitives.

### TODO 12: Run Dashboard / Aggregation View

**Strongly agree.**

This should be sooner than the panda plan's more ambitious result index. A
read-only `list_runs` that scans `.runtime/runs/` is simple, local-first, and
aligned with the current design.

### TODO 13: Email / Webhook Notifications

**Defer.**

Slurm mail directives are easy, but this is not a platform blocker. Also, some
clusters disable or constrain mail behavior. Add it when a real user asks for
it.

### TODO 14: Job Dependency Chains

**Partially agree.**

Dependencies matter for GATK-scale multi-step HPC work, but they should not
become manual user choreography. If added, they should be represented as
execution-layer metadata derived from a frozen recipe graph or an explicit
follow-on submission record.

### TODO 15: Actionable Error Messages

**Strongly agree.**

This is one of the best low-risk improvements. It helps both users and future
agents. Missing manifest paths, schema mismatch details, and valid runtime
binding hints should be visible.

### TODO 16: Runtime Binding Discovery

**Agree.**

This should be part of a discoverability bundle with TODO 15, TODO 17, and TODO
19. The current recipe flow is powerful but too dependent on users knowing the
magic binding keys.

### TODO 17: Result Inspection Tool

**Strongly agree.**

This is a design-specified MCP gap and a natural complement to run records.
Implement it before a database-backed result index. The first version can be
manifest-first and stage-aware only for the existing stable stages.

### TODO 18: Guided Workflow Mode

**Defer.**

Guided mode is product-friendly, but it is large and depends on better missing
input diagnostics, runtime binding discovery, and result inspection. Build the
smaller pieces first.

### TODO 19: MCP Resources for Run Records and Recipes

**Agree.**

This is low effort and high discoverability, especially after local run records
exist. Add read-only resources before introducing writable or mutating MCP
flows.

### TODO 20: Stargazer-Style Storage Query

**Defer and narrow.**

The right first step is not TinyDB or SQLite. The right first step is:

1. `list_runs`
2. `inspect_result`
3. read-only `flytetest://run-records` and `flytetest://run-recipes`
4. only then a filesystem-backed index if manifest scanning becomes too slow

That keeps the repo aligned with the "not database-first" design constraint.

---

## TODO Implementation Status Audit, Revised

This is based on the docs snapshot, not a fresh line-by-line code audit of every
TODO implementation.

| TODO | Panda status | Current-state adjustment |
|---|---|---|
| DESIGN.md Section 7.4 update | Not started | Complete in `DESIGN.md` and `CHANGELOG.md` |
| Milestone 19 | Not started | In progress; Phase A complete, Phase B/C missing |
| TODO 7: Configurable module loading | Missing | Still valid |
| TODO 8: Job log fetching | Partial | Still valid |
| TODO 9: Resource-escalation retry | Missing | Still valid; distinct from current Slurm retry |
| TODO 10: Job arrays | Missing | Still valid, later |
| TODO 11: Job polling / wait | Missing | Still valid, after observability |
| TODO 12: Run dashboard / list_runs | Missing | Still valid, should move earlier |
| TODO 13: Email notifications | Missing | Valid but low priority |
| TODO 14: Job dependency chains | Missing | Valid, GATK-driven later |
| TODO 15: Actionable error messages | Partial | Still valid, high value |
| TODO 16: Runtime binding discovery | Missing | Still valid |
| TODO 17: Result inspection tool | Missing | Still valid |
| TODO 18: Guided workflow mode | Missing | Valid but defer |
| TODO 19: MCP resources for runs/recipes | Missing | Still valid and now more valuable |
| TODO 20: Result index | Missing | Valid later; do not make database-first |

---

## Final Prioritization (Revised Again)

### Platform Track

Platform work still gates biology expansion, but P1 should be updated for the
current repo state.

#### Step P1: Finish M19 Core Semantics

| Item | Status | Notes |
|---|---|---|
| M19 Phase A: durable local run records | Complete | Recorded in `CHANGELOG.md` on 2026-04-12 |
| M19 Phase B: local resume semantics | Next critical path | Load records, skip completed nodes, record reuse/rerun reasons |
| M19 Phase C: cache keys and Slurm parity | Critical path after Phase B | Deterministic identity, Slurm alignment, composed execution approval acceptance |
| Checklist / maturity cleanup | Small docs cleanup | Align summary status with Phase A completion |

#### Step P2a: HPC Recovery

| Item | Why |
|---|---|
| Resource-escalation retry | Lets users recover from OOM/TIMEOUT without recipe reconstruction |
| Configurable module loading | Makes generated sbatch scripts usable across real cluster module environments |

#### Step P2b: Observability

| Item | Why |
|---|---|
| Job log tailing | Makes failed Slurm jobs debuggable through MCP |
| `list_runs` | Makes run records discoverable without pointer-file archaeology |
| Wait-for-completion | Useful once monitor/list/log primitives are stable |

#### Step P2c: MCP Discoverability

| Item | Why |
|---|---|
| Better missing-input errors | Reduces trial and error |
| Runtime binding discovery | Explains required values before recipe creation |
| Result inspection | Turns manifests into usable MCP summaries |
| Read-only run/recipe resources | Makes saved records browseable |

#### Step P3: Demand-Driven Platform

| Item | Trigger |
|---|---|
| Job dependencies | GATK or another multi-step HPC workflow needs scheduler chaining |
| Job arrays | Batch-scale use cases such as many genomes or chunks |
| Email notifications | User demand on a cluster where Slurm mail works |
| Result index | Manifest scanning becomes inadequate |
| Guided workflow mode | Collaborator onboarding becomes the bottleneck |

---

### Biology Track

Biology work should remain gated by the platform step it depends on.

```
M19 Phase B/C
    -> safe composed execution
    -> table2asn can remain a small side branch
    -> assembly QC can follow as annotation-adjacent scope
    -> GATK tasks can start only after record semantics are stable
    -> GATK integration waits for HPC recovery and observability
```

#### Step B1: Complete Current Annotation Path

| Item | Gate | Notes |
|---|---|---|
| `table2asn` | Can run near P1 | Small, terminal, notes-faithful |

#### Step B1.5: Add Annotation-Adjacent QC

| Item | Gate | Notes |
|---|---|---|
| Genome assembly QC | After P1 or alongside stable P2 work | QUAST and BUSCO genome mode; keep distinct from protein BUSCO |

#### Step B2: Add GATK as First Large New Family

| Substep | Gate | Notes |
|---|---|---|
| B2a: task wrappers | After M19 record semantics are stable | Prefer new files and isolated tests |
| B2b: workflows and planner types | After local resume semantics | New biological types and result bundles |
| B2c: registry/MCP/Slurm integration | After HPC recovery and observability | Shared files, higher conflict risk |

#### Step B3: Demand-Driven Extensions

| Item | Gate |
|---|---|
| Differential expression | After R/Bioconductor runtime handling is explicit |
| scRNA-seq | After specific collaborator demand |
| Structural variants | After short-variant pipeline is mature |

---

## Execution Notes

### Branch Strategy

I mostly agree with the panda plan's branch separation.

- Keep M19 Phase B/C on the realtime architecture track.
- Keep `table2asn` as a small branch that can merge after normal tests.
- Keep GATK on a feature branch with sub-milestones.
- Delay GATK shared-file integration until P2 recovery and observability are
  stable.

### Docs Strategy

This repo treats docs as agent memory, so docs drift matters.

Recommended docs cleanup:

- Update the Milestone 19 summary status in
  `docs/realtime_refactor_checklist.md`.
- Split the `Caching / resumability` capability in
  `docs/capability_maturity.md` after the next implementation slice, or
  immediately if the team wants Phase A reflected now.
- Leave `DESIGN.md` Section 7.4 alone unless new Slurm behavior changes; it is
  already aligned with the authenticated-session `sbatch` model.

### Test Strategy

Do not add broad biology pipelines without corresponding fixture-backed tests.
For the next platform slice, the most important tests are:

- resume from a complete local run record,
- resume from a partial local run record,
- rerun when a node is missing or invalidated,
- reject stale schema or mismatched frozen recipe identity,
- preserve existing no-`run_root` backward compatibility,
- keep composed DAG execution gated until approval acceptance and resume safety
  are both explicit.

---

## Bottom Line

The panda plan is directionally right but status-stale.

The project is in better shape than the plan assumes: Slurm design alignment is
done, Slurm lifecycle is real, registry composition is current, and M19 Phase A
has landed durable local run records.

The project is not yet ready to execute composed DAGs freely or launch a large
new workflow family. The remaining critical path is narrower and more concrete:
local resume semantics, deterministic cache identity, Slurm parity, and explicit
approval acceptance. After that, the platform should prioritize HPC recovery and
MCP observability before ambitious result indexing or broad natural-language
intelligence.

My final position: agree with the panda plan's architecture instincts, disagree
with its stale P1 status, and expand the roadmap by making "durable record,"
"resume," "cache reuse," and "resource-escalation retry" separate milestones
rather than one broad recovery bucket.

# Assessment: Current Milestones vs. Design Goals

## Context

You asked for an honest evaluation of how the current milestones track against
the design goals in `DESIGN.md`. This is an analytical assessment, not a code
change plan.

---

## Summary Verdict

The project has made **remarkably strong progress** on its core architecture
pillars. Out of 25+ milestones defined, the vast majority are complete. The
biological pipeline is implemented end-to-end through AGAT post-processing. The
architecture layers (planner types, resolver, registry, specs, executor, MCP
surface) are all in place. Slurm lifecycle is functional with submit, monitor,
retry, and cancel.

However, there are **structural gaps** between the current implementation and
the full design vision that are worth acknowledging honestly.

---

## What's Working Well (Aligned With Design)

### 1. Frozen Recipe Boundary (Design Pillar: "Dynamic interpretation before execution")
- **Strong alignment.** The `prepare_run_recipe` -> `run_local_recipe` / `run_slurm_recipe` flow is exactly what DESIGN.md prescribes. Planning is dynamic; execution consumes frozen artifacts. This is the project's strongest architectural achievement.

### 2. Biological Pipeline Completeness
- The pipeline from transcript evidence through AGAT cleanup is fully implemented -- 14 workflows covering the entire annotation path described in `docs/braker3_evm_notes.md`, minus only `table2asn` (intentionally deferred).
- Stage ordering is notes-faithful. The pre-EVM contract is correctly maintained.

### 3. Registry-Constrained Composition (Milestone 15)
- The graph-traversal-based composition discovery with approval gating is a solid design choice. It prevents the planner from inventing unsupported biology while still allowing multi-stage workflow assembly from registered building blocks.

### 4. Strong Typed Planning Layer
- The `planner_types.py` -> `planning.py` -> `specs.py` -> `spec_artifacts.py` -> `spec_executor.py` chain is clean and well-separated. Each layer has a clear responsibility.

### 5. Slurm Lifecycle (Milestones 13, 16, 18)
- Submit via `sbatch`, monitor via `squeue`/`sacct`, retry with failure classification, cancel via `scancel` -- all from frozen recipes with durable run records under `.runtime/runs/`. This is a solid HPC foundation.

### 6. Test Coverage
- 237 passing tests with synthetic coverage for every major subsystem. The project avoids requiring real bioinformatics tools for its test suite.

---

## Gaps Between Current State and Design Goals

### Gap 1: Flyte Slurm Plugin vs. Raw `sbatch` (DESIGN.md needs updating, NOT a real gap)

**DESIGN.md says:** "FLyteTest should support Slurm through the Flyte Slurm plugin so that scheduling, monitoring, and cancellation are handled as part of the Flyte execution model" (Section 7.4). It shows `SlurmFunction` and `SlurmTask` examples with SSH config.

**Reality:** The current implementation uses raw `subprocess.run(["sbatch", ...])` and manual `squeue`/`sacct` polling from inside an already-authenticated login-node session.

**Why the design is wrong, not the implementation:** The target HPC environment
requires 2FA and does not allow SSH key pairing. The Flyte Slurm plugin
(`flytekitplugins-slurm`) requires unattended SSH access to the scheduler node,
which is simply not possible under the HPC's security policy. The current
approach -- running an MCP server process inside an already-authenticated
session (login node, tmux, screen) and issuing `sbatch` directly -- is the
**correct architecture** for this deployment, not a workaround.

**Action needed:** DESIGN.md Section 7.4 and the `SlurmFunction`/`SlurmTask`
examples should be updated to reflect this constraint. The design should
describe the authenticated-session-local `sbatch` approach as the chosen Slurm
integration model, document the 2FA/SSH constraint as the reason, and remove
the Flyte Slurm plugin examples that cannot work in this environment.

**My read:** This was likely a pragmatic choice -- the Flyte Slurm plugin (`flytekitplugins-slurm`) may not have been mature enough or may require a Flyte backend deployment that the project doesn't use (given it runs `flyte run --local`). But the design should acknowledge this divergence explicitly rather than leaving it as an implicit gap.

### Gap 2: Caching/Resumability (Milestone 19 -- NOT STARTED)

**DESIGN.md says:** Reproducible result delivery and stage-completion tracking are core to the execution model.

**Reality:** Milestone 19 is the only remaining "Not started" milestone on the critical path. Without it:
- Composed DAG execution via Milestone 15 compositions can't safely run (acknowledged in the stop rules)
- Interrupted Slurm jobs can't resume from where they left off
- There's no cache-key-based stage reuse

**Impact:** This blocks the full value of the composition system. Users can *preview* compositions but can't *execute* them safely. This is the critical next step.

### Gap 3: Managed/Remote Execution (FAR)

**DESIGN.md says:** Flyte-managed execution should "preserve typed task and workflow boundaries" and "allow task-level resource and runtime settings" (Section 7.3).

**Capability maturity says:** "Far -- the repo mostly uses `flyte run --local` and does not yet show a real backend deployment."

**Impact:** The project has never targeted a real Flyte backend. Everything runs locally or through raw Slurm scripts. This means Flyte is effectively used as a typed task/workflow framework, not as a distributed execution engine. The design describes Flyte-managed execution as a goal, but the milestones don't include a path to get there.

### Gap 4: Storage-Native Asset Return (Milestone 20 -- Design Intent Only)

**DESIGN.md says:** Result bundles should be traceable and reusable. The capability maturity doc calls this "Far."

**Reality:** All artifacts are local filesystem paths. There's no content-addressed store, no remote asset index, no durable asset references beyond `run_manifest.json` files on disk.

**Impact:** This limits the system to single-machine or shared-filesystem (NFS/Lustre) deployments. For a university HPC cluster this is fine, but it constrains growth.

### Gap 5: MCP Tool Surface Gaps

**DESIGN.md proposes these tools that don't exist yet:**
- `run_task` -- bounded ad hoc task execution (Milestone 21 planned but not started)
- `validate_run_recipe` -- pre-execution validation
- `inspect_result` -- result manifest inspection
- `prepare_slurm_recipe` / `submit_slurm_recipe` (partially covered by `run_slurm_recipe`)

**DESIGN.md proposes these resources that don't exist yet:**
- `flytetest://execution-profiles`
- `flytetest://slurm-profile`
- `flytetest://run-recipes/<recipe_id>`
- `flytetest://result-manifests/<run_id>`

**Impact:** The current MCP surface is functional but narrower than the design target. The missing tools would make the system more self-documenting and inspectable for MCP clients.

### Gap 6: No Real Natural-Language Intelligence

**DESIGN.md says:** "Enable natural-language planning for supported bioinformatics workflow families."

**Reality:** The "prompt planning" is pattern-matching and keyword extraction in `planning.py`, not LLM-backed interpretation. This works for the current scope but doesn't scale to the "describe an analysis in natural language" vision in the README.

**My read:** This is probably intentional for now -- keeping the planner deterministic avoids the "AI invents unsupported biology" risk. But the design document's vision of natural-language planning implies an LLM-in-the-loop at some point. The architecture is ready for it (the separation between planning and execution is clean), but no milestone addresses this.

---

## Milestone Sequencing Assessment

### What's been sequenced well:
- Building the type system before the executor (M1-M2 before M7)
- Registry compatibility metadata before composition (M4 before M15)
- Resource-aware planning before Slurm submission (M12 before M13)
- Individual workflow MCP targets before composition (M10-M11 before M15)
- Slurm submission before monitoring before retry (M13 -> M16 -> M18)

### What could be questioned:
- **25 milestones for a single-developer project is a lot of overhead.** The milestone docs, submission prompts, checklists, and handoff materials are extensive. This is valuable for agent-driven development (where each session needs context), but it creates a documentation burden that could slow human contributors.
- **Milestones 22-25 (asset surface cleanup)** are family-scoped follow-ups that could arguably be consolidated into one milestone with subtasks rather than four separate milestones.
- **The gap between Milestone 15 (composition preview) and Milestone 19 (caching/resumability)** means the composition system exists but can't be used for execution. This is honest but might frustrate users who see compositions previewed but can't run them.

---

## Recommendations

1. **Milestone 19 (caching/resumability) should be the top priority.** It unblocks composed DAG execution and makes the Slurm path more robust. Everything else is enhancement.

2. **Update DESIGN.md Section 7.4 to match reality.** The Flyte Slurm plugin requires SSH key pairing, which the HPC's 2FA policy prohibits. The current authenticated-session `sbatch` approach is the correct design for this environment. Remove the `SlurmFunction`/`SlurmTask` examples and document the 2FA constraint as the architectural reason. This turns a "design divergence" into a "design decision."

3. **Consider whether Flyte backend deployment is still a project goal.** If the system will always run `flyte run --local` + authenticated-session Slurm, the design document's Flyte-managed execution sections are aspirational noise. The 2FA constraint that prevents the Slurm plugin likely also prevents a remote Flyte backend from submitting jobs. Either commit to a backend deployment milestone or reframe the design to acknowledge Flyte as a local typed-workflow framework rather than a distributed execution engine.

4. **The MCP resource gaps (`run-recipes/<id>`, `result-manifests/<id>`) would be high-value, low-effort additions** that make the system more introspectable without changing execution behavior.

5. **Consider consolidating the remaining milestones.** The project has 4 asset-cleanup milestones (22-25), a deferred ad-hoc task milestone (21), and the storage milestone (20). Some of these could be combined or explicitly deprioritized to focus effort.

---

---

## Biological Workflow Expansion Opportunities

Based on cross-referencing FLyteTest's current coverage with the Stargazer
project (`/Projects/stargazer/`) and identifying natural extensions of the
genome annotation pipeline:

### What FLyteTest Has Today
- **17 bioinformatics tools** wrapped as tasks (Trinity, STAR, samtools,
  StringTie, PASA, TransDecoder, Exonerate, BRAKER3, EVM, RepeatMasker,
  gffread, funannotate, BUSCO, EggNOG-mapper, AGAT, FastQC, Salmon)
- **15 workflows** covering RNA-seq QC through AGAT post-processing
- Only `table2asn` remains explicitly deferred from the original pipeline

### What Stargazer Has That FLyteTest Doesn't

| Tool / Capability | Stargazer Status | FLyteTest Status |
|---|---|---|
| BWA / BWA-MEM2 (DNA alignment) | Fully implemented | Not present |
| GATK4 (variant calling) | 14 tasks, full pipeline | Not present |
| GATK BQSR (base recalibration) | Implemented | Not present |
| GATK HaplotypeCaller | Implemented | Not present |
| GATK joint genotyping (GenomicsDB) | Implemented | Not present |
| GATK VQSR (variant quality recalibration) | Implemented | Not present |
| scanpy (single-cell RNA-seq) | 6 tasks, full pipeline | Not present |
| Content-addressable storage (IPFS) | Core feature | Local filesystem only |

---

### Proposed Expansion TODOs

#### TODO 1: `table2asn` Submission Preparation (LOW EFFORT -- already designed)

**What:** Wrap NCBI's `table2asn` tool to convert the AGAT-cleaned GFF3 +
genome FASTA into an ASN.1 submission file for GenBank/NCBI.

**Why:** This is the natural terminal step of the annotation pipeline that's
already been explicitly deferred. The upstream contracts (AGAT cleanup output)
are fully defined.

**Scope:**
- 1 task: `table2asn_prepare_submission`
- 1 workflow: `annotation_submission_table2asn`
- Consumes AGAT cleanup results
- Produces `.sqn` file + validation report
- Tool ref already exists at `docs/tool_refs/table2asn.md`

**Effort:** Small -- the input contract is already specified, just needs the
task wrapper, workflow, registry entry, and MCP handler.

---

#### TODO 2: DNA Variant Calling Pipeline (GATK Best Practices) (HIGH VALUE)

**What:** Port Stargazer's GATK germline short variant discovery pipeline into
FLyteTest's architecture, adapting it for the recipe-backed, manifest-driven
execution model.

**Why:** Variant calling is the most common companion analysis to genome
annotation. Researchers annotating a genome often also want to call variants
against it. Stargazer already has mature GATK4 tasks that could be adapted.

**Scope (from Stargazer's implementation):**

New tasks (~14):
- `bwa_mem2_index` / `bwa_mem2_align` (DNA read alignment)
- `samtools_faidx` / `create_sequence_dictionary` (reference prep)
- `sort_sam` / `mark_duplicates` / `merge_bam_alignment` (BAM processing)
- `base_recalibrator` / `apply_bqsr` (base quality recalibration)
- `haplotype_caller` (per-sample GVCF)
- `genomics_db_import` / `joint_call_gvcfs` (joint genotyping)
- `variant_recalibrator` / `apply_vqsr` (variant quality filtering)
- `index_feature_file` (VCF indexing)

New workflows (~3):
- `prepare_reference` (index + dict + BWA index)
- `preprocess_sample` (align + sort + dedup + BQSR)
- `germline_short_variant_discovery` (full end-to-end)

**Integration points with FLyteTest:**
- Shares the same reference genome input as the annotation pipeline
- Could reuse existing `samtools` task patterns
- Would need new planner types: `DnaReadSet`, `VariantCallSet`, `KnownSitesBundle`
- Natural composition: run annotation pipeline, then call variants against the
  annotated genome
- Slurm execution is critical -- GATK joint genotyping is very resource-intensive

**Effort:** Large -- this is a new pipeline family, not an extension of the
existing annotation path. But Stargazer's implementation provides a tested
reference.

---

#### TODO 3: Single-Cell RNA-seq Analysis Pipeline (HIGH VALUE, DIFFERENT DOMAIN)

**What:** Port Stargazer's scanpy-based scRNA-seq clustering pipeline into
FLyteTest.

**Why:** scRNA-seq analysis is increasingly paired with genome annotation work,
especially for organisms with new reference genomes. The pipeline is pure
Python (scanpy/AnnData), so it doesn't need external bioinformatics binaries.

**Scope (from Stargazer's implementation):**

New tasks (~6):
- `qc_filter` (cell/gene filtering, doublet detection)
- `normalize` (total count normalization, log transformation)
- `select_features` (highly variable gene selection)
- `reduce_dimensions` (PCA, kNN graph, UMAP)
- `cluster` (Leiden community detection)
- `find_markers` (differential expression per cluster)

New workflow (~1):
- `scrna_clustering_pipeline` (end-to-end)

**Integration points with FLyteTest:**
- New planner types: `AnnDataAsset`, `SingleCellExperiment`
- New asset type for `.h5ad` files
- Could compose with annotation pipeline: annotate genome -> align scRNA reads
  -> cluster cells -> annotate cell types using the annotation
- Python-only tasks mean no container dependencies for basic runs

**Effort:** Medium -- scanpy tasks are simpler than GATK (no shell subprocess
wrappers), but it's a genuinely new biological domain.

---

#### TODO 4: Differential Expression Analysis (RNA-seq Downstream)

**What:** Add DESeq2/edgeR-style differential expression analysis downstream
of the existing RNA-seq quantification (Salmon) workflow.

**Why:** FLyteTest already has `salmon_quant` producing transcript-level
quantification. The natural next question is "which genes are differentially
expressed between conditions?" This is the most-requested RNA-seq downstream
analysis.

**Scope:**

New tasks (~4):
- `tximport_salmon` (import Salmon quant into gene-level counts)
- `deseq2_analysis` (differential expression with DESeq2)
- `collect_de_results` (gather significant genes, volcano plots, MA plots)
- `go_enrichment` (Gene Ontology enrichment on DE gene lists) -- optional

New workflow (~1):
- `differential_expression_deseq2`

**Integration points:**
- Consumes Salmon quant output from existing `rnaseq_qc_quant` workflow
- Would need new planner types: `ExpressionMatrix`, `DifferentialExpressionResult`
- Natural composition: RNA-seq QC/quant -> DE analysis -> GO enrichment
- R-based tasks (DESeq2) would need an R container image

**Effort:** Medium -- requires R/Bioconductor container support, which is a new
runtime pattern for FLyteTest.

---

#### TODO 5: Structural Variant Calling (Extending GATK Pipeline)

**What:** Add structural variant (SV) detection using tools like Manta, Delly,
or GATK's SV caller on top of the DNA alignment from TODO 2.

**Why:** Once you have aligned DNA reads (from the GATK pipeline), structural
variant detection is a natural extension that catches larger genomic events
(deletions, duplications, inversions, translocations).

**Scope:**

New tasks (~3-4):
- `manta_sv_call` or `delly_call` (SV detection)
- `survivor_merge` (merge calls from multiple SV callers)
- `annotate_sv` (annotate SVs against the gene annotation)

**Effort:** Medium -- depends on TODO 2 being complete first.

---

#### TODO 6: Genome Assembly QC and Completeness

**What:** Add genome assembly QC tools that run *before* the annotation
pipeline starts, validating the reference genome itself.

**Why:** The current pipeline assumes a good reference genome as input. Adding
pre-annotation QC catches problems early.

**Scope:**

New tasks (~3):
- `quast_genome_assessment` (assembly statistics, N50, misassemblies)
- `busco_genome_mode` (genome-mode BUSCO, distinct from protein-mode BUSCO
  already implemented)
- `merqury_kmer_assessment` (k-mer based assembly QC) -- optional

New workflow (~1):
- `genome_assembly_qc`

**Effort:** Small-medium -- BUSCO genome mode reuses the existing BUSCO
infrastructure with different parameters.

---

### Recommended Prioritization

| Priority | TODO | Rationale |
|---|---|---|
| 1 | table2asn (TODO 1) | Completes the existing pipeline, minimal effort |
| 2 | GATK variant calling (TODO 2) | Highest-value new pipeline, Stargazer reference exists |
| 3 | Genome assembly QC (TODO 6) | Pre-annotation QC, reuses existing BUSCO infra |
| 4 | Differential expression (TODO 4) | Extends existing Salmon workflow |
| 5 | scRNA-seq (TODO 3) | High value but different domain |
| 6 | Structural variants (TODO 5) | Depends on TODO 2 |

### Cross-Project Considerations

Stargazer and FLyteTest share the same Flyte foundation but differ in
architecture:
- **Stargazer**: async-first, content-addressable IPFS storage, auto-discovery
  MCP server
- **FLyteTest**: recipe-first, local filesystem manifests, typed
  planning/approval MCP server

When porting Stargazer tools to FLyteTest, the tasks themselves can largely be
reused, but they need to be wrapped in FLyteTest's patterns: `run_tool()` with
optional SIF paths, `run_manifest.json` emission, typed planner integration,
registry entries with compatibility metadata, and MCP recipe-backed execution.

---

## Engineering TODOs: HPC Job Submission & Monitoring

### TODO 7: Configurable Module Loading in sbatch Scripts (HIGH IMPACT, LOW EFFORT)

**Problem:** `render_slurm_script()` in `spec_executor.py:1208-1209` hardcodes
`module load python/3.11.9` and `module load apptainer/1.4.1`. Users cannot
load custom modules (CUDA, tool-specific versions, different Python builds).

**Fix:**
- Add `module_loads: list[str]` to `ResourceSpec` or a new `SlurmEnvironmentSpec`
- Let recipes freeze required modules: `["python/3.11.9", "apptainer/1.4.1", "cuda/12.0"]`
- Render them into the generated sbatch script
- Accept via MCP `runtime_bindings` or `resource_request`
- Default to current behavior when not specified

**Files:** `src/flytetest/specs.py` (ResourceSpec), `src/flytetest/spec_executor.py` (render_slurm_script)

---

### TODO 8: Job Output Log Fetching (HIGH IMPACT, MEDIUM EFFORT)

**Problem:** `monitor_slurm_job` returns stdout/stderr *paths* on the compute
node but never fetches the content. Users must SSH to compute nodes and
`tail -f` manually to debug failures.

**Fix:**
- When `monitor_slurm_job` reconciles a terminal state, read the last N lines
  of stdout/stderr from the shared filesystem paths (they're typically on NFS)
- Add `stdout_tail` and `stderr_tail` fields to the lifecycle result
- Add an optional `tail_lines` parameter (default 50)
- For running jobs, show the current tail (not just the path)

**Files:** `src/flytetest/spec_executor.py` (reconcile method), `src/flytetest/server.py` (monitor_slurm_job_impl)

---

### TODO 9: Resource-Escalation Retry (HIGH IMPACT, MEDIUM EFFORT)

**Problem:** OOM and TIMEOUT failures are classified as terminal
(`spec_executor.py:863-872`). Users must manually create a new recipe with more
resources and resubmit. This is the #1 bioinformatician pain point on HPC.

**Fix:**
- Add a `retry_with_resources` MCP tool or extend `retry_slurm_job` with
  optional `resource_overrides`
- When an OOM/TIMEOUT is detected, allow retry with scaled resources:
  `{"memory": "64Gi"}` overrides the frozen recipe's `32Gi`
- Record the override in the child run record for audit
- Keep the original recipe frozen; only the sbatch directives change

**Files:** `src/flytetest/spec_executor.py` (retry method, classify_slurm_failure), `src/flytetest/server.py`

---

### TODO 10: Job Array Support for Embarrassingly Parallel Tasks (HIGH VALUE)

**Problem:** Running BUSCO on 100 genomes or Exonerate on 500 protein chunks
requires 100/500 separate recipe submissions. No `--array` support exists.

**Fix:**
- Add `array_size: int | None` to `ResourceSpec`
- When set, render `#SBATCH --array=1-{array_size}` and parameterize the
  inline Python with `$SLURM_ARRAY_TASK_ID`
- Track array job IDs in run records (e.g., `12345_1`, `12345_2`, ...)
- Add `monitor_slurm_array` that aggregates per-element status

**Files:** `src/flytetest/specs.py`, `src/flytetest/spec_executor.py`

**Effort:** Medium-large -- requires rethinking how recipes map to multiple
parallel executions.

---

### TODO 11: Automatic Job Polling / Wait-for-Completion (MEDIUM IMPACT)

**Problem:** After `run_slurm_recipe`, users must manually call
`monitor_slurm_job` repeatedly. No built-in polling loop.

**Fix:**
- Add a `wait_for_slurm_job` MCP tool that polls at intervals until terminal
  state
- Return the final lifecycle result (same as monitor) when complete
- Accept a `poll_interval_seconds` parameter (default 30)
- Include progress updates in the response for long-running jobs
- Time out after a configurable maximum wait

**Files:** `src/flytetest/server.py`

---

### TODO 12: Run Dashboard / Aggregation View (MEDIUM IMPACT)

**Problem:** No way to see "all my recent runs." Users must track
`run_record_path` files manually. The `.runtime/runs/latest_*.txt` pointer
files are not thread-safe and only track one run.

**Fix:**
- Add a `list_runs` MCP tool that scans `.runtime/runs/` and returns a summary
  table: run_id, workflow_name, job_id, state, submitted_at, completed_at
- Add optional filters: `state=RUNNING`, `workflow_name=annotation_qc_busco`
- Sort by recency
- Include retry lineage (parent/child links) in the summary

**Files:** `src/flytetest/server.py`, `src/flytetest/spec_executor.py`

---

### TODO 13: Email/Webhook Notifications on Job Completion (LOW PRIORITY)

**Problem:** No notification when a job finishes. Users must actively poll.

**Fix:**
- Add `--mail-type=END,FAIL` and `--mail-user={email}` to sbatch scripts
- Accept `notification_email` in resource_request or runtime_bindings
- Slurm handles the notification natively -- zero server-side complexity

**Files:** `src/flytetest/spec_executor.py` (render_slurm_script)

---

### TODO 14: Job Dependency Chains (MEDIUM PRIORITY)

**Problem:** Cannot express "run BUSCO after repeat filtering finishes" as a
single submission. Users must manually wait and resubmit.

**Fix:**
- Add `depends_on_job_id: str | None` to the Slurm submission path
- Render `#SBATCH --dependency=afterok:{job_id}` in the generated script
- Allow MCP callers to chain: submit repeat_filtering, get job_id, submit BUSCO
  with `depends_on_job_id=that_id`

**Files:** `src/flytetest/specs.py`, `src/flytetest/spec_executor.py`

---

## Engineering TODOs: MCP Integration for Bioinformaticians

### TODO 15: Actionable Error Messages (HIGH IMPACT, LOW EFFORT)

**Problem:** When manifest resolution fails, errors say
"Could not resolve QualityAssessmentTarget from supplied manifest sources" --
no path tried, no schema mismatch detail, no suggestion.

**Fix:**
- Include the attempted manifest paths in decline responses
- Include the specific parse/schema error when a manifest exists but doesn't match
- Suggest the expected manifest shape or a known-good example path
- For missing runtime bindings, list valid values (e.g., BUSCO lineages)

**Files:** `src/flytetest/planning.py`, `src/flytetest/server.py`

---

### TODO 16: Runtime Binding Discovery and Validation (HIGH IMPACT, MEDIUM EFFORT)

**Problem:** Users don't know what `runtime_bindings` are required or what
values are valid. Trial-and-error is the current discovery method.

**Fix:**
- Add a `describe_recipe_requirements` MCP tool (or extend `plan_request`)
  that, given a workflow name, returns:
  - Required runtime bindings with descriptions and valid values
  - Optional runtime bindings with defaults
  - Required manifest inputs with expected schema
  - Resource defaults and recommendations
- Example response for BUSCO:
  ```json
  {
    "required": {
      "busco_lineages_text": {
        "description": "Comma-separated BUSCO lineage names",
        "examples": ["eukaryota_odb10", "bacteria_odb10", "fungi_odb10"],
        "note": "Use _odb10 or _odb12 suffix depending on installed datasets"
      }
    },
    "optional": {
      "busco_cpu": {"default": 8, "description": "CPU cores for BUSCO"},
      "busco_sif": {"default": null, "description": "Apptainer image path"}
    }
  }
  ```

**Files:** `src/flytetest/server.py`, `src/flytetest/mcp_contract.py`

---

### TODO 17: Result Inspection Tool (MEDIUM IMPACT, LOW EFFORT)

**Problem:** After execution, users get output paths but no way to inspect
results through MCP. DESIGN.md specifies an `inspect_result` tool that doesn't
exist.

**Fix:**
- Add `inspect_result` MCP tool that reads a `run_manifest.json` and returns:
  - Stage name, assumptions, input/output summary
  - Key output file paths with sizes
  - For BUSCO: completeness scores (C/S/D/F/M percentages)
  - For EggNOG: annotation counts, GO term summary
  - For AGAT: gene/mRNA/exon counts from statistics output

**Files:** `src/flytetest/server.py`

---

### TODO 18: Guided Workflow Mode (HIGH IMPACT, LARGE EFFORT)

**Problem:** The current flow requires users to know the right tool call
sequence: list_entries -> prepare_run_recipe (with correct bindings) ->
run_local_recipe. Bioinformaticians who don't know the system bounce between
declined requests and opaque errors.

**Fix:**
- Add a `guided_run` MCP tool that walks through the workflow interactively:
  1. Accept a natural-language prompt
  2. Return a structured "next step" with what's needed
  3. Accept incremental inputs (manifest path, runtime bindings)
  4. Show a preview before execution
  5. Execute on confirmation
- This is essentially `prompt_and_run` but with intermediate validation steps
  that explain what's missing instead of just declining

**Alternative (simpler):** Enrich `prepare_run_recipe` decline responses with
a `next_steps` field that tells the user exactly what to supply.

**Files:** `src/flytetest/server.py`, `src/flytetest/planning.py`

---

### TODO 19: MCP Resources for Run Records and Recipes (LOW EFFORT, HIGH DISCOVERABILITY)

**Problem:** DESIGN.md specifies resources like `flytetest://run-recipes/<id>`
and `flytetest://result-manifests/<run_id>` that don't exist. Users can't
browse saved recipes or past results through MCP.

**Fix:**
- Add `flytetest://run-recipes` -- list saved recipes under `.runtime/specs/`
- Add `flytetest://run-records` -- list run records under `.runtime/runs/`
- Add `flytetest://execution-profiles` -- describe available profiles (local, slurm)
  with their requirements and defaults
- These are read-only resources, minimal implementation effort

**Files:** `src/flytetest/server.py`

---

### TODO 20: Stargazer-Style Storage Query for Asset Discovery (LARGE EFFORT, HIGH VALUE)

**Problem:** FLyteTest's resolver requires exact manifest paths or result
directory paths. There's no way to query "find all BUSCO results for organism
X" across past runs.

**Inspiration from Stargazer:** `query_files(filters={"organism": "drosophila",
"stage": "busco"})` searches a metadata index (TinyDB) and returns matching
assets with paths.

**Fix:**
- Add a lightweight metadata index (TinyDB or SQLite) that indexes
  `run_manifest.json` records as they're created
- Add a `query_results` MCP tool that searches by stage, organism, date range,
  workflow name
- Feed query results into `manifest_sources` for downstream recipe preparation
- This is the bridge between "local filesystem manifests" and
  "discoverable asset catalog" without going full database-first

**Files:** New module `src/flytetest/result_index.py`, `src/flytetest/server.py`

---

## TODO Implementation Status Audit

Audited 2026-04-12 against spec_executor.py, server.py, specs.py, planning.py,
mcp_contract.py. Status labels: **Done**, **Partial**, **Missing**, **Someday**.

| TODO | Status | Finding |
|---|---|---|
| TODO 7: Configurable module loading | **Missing** | `render_slurm_script` hardcodes `python/3.11.9` + `apptainer/1.4.1`; no user override |
| TODO 8: Job log fetching | **Partial** | Monitor returns stdout/stderr paths but never reads content |
| TODO 9: Resource-escalation retry | **Missing** | `retry_slurm_job` has no `resource_overrides`; resubmits identical recipe only |
| TODO 10: Job arrays | **Missing** | No `--array` in ResourceSpec or sbatch generation |
| TODO 11: Job polling / wait | **Missing** | No polling loop; manual `monitor_slurm_job` only |
| TODO 12: Run dashboard / list_runs | **Missing** | No tool scans `.runtime/runs/`; pointer files are single-entry |
| TODO 13: Email notifications | **Missing** | No `--mail-type` in sbatch generation |
| TODO 14: Job dependency chains | **Missing** | No `--dependency=afterok` in sbatch generation |
| TODO 15: Actionable error messages | **Partial** | Has `rationale` + `missing_requirements` but no attempted paths, parse detail, or valid value hints |
| TODO 16: Runtime binding discovery | **Missing** | No `describe_recipe_requirements` tool; no per-workflow binding schema exposed |
| TODO 17: Result inspection tool | **Missing** | No `inspect_result` MCP tool; no manifest summary parsing |
| TODO 18: Guided workflow mode | **Missing** | No `guided_run` tool; `prompt_and_run` is one-shot only |
| TODO 19: MCP resources for runs/recipes | **Missing** | Only 4 resources exist; no `run-recipes`, `run-records`, `execution-profiles` |
| TODO 20: Result index | **Missing** | No TinyDB/SQLite index; capability maturity marks this "Far" |

**Summary:** 0 Done, 2 Partial (TODO 8, 15), 11 Missing, 1 Someday (TODO 20).
The critique's concern that some gaps were already closed is **not borne out by
the audit** -- the gaps are real and the TODOs are still valid.

---

## Final Prioritization (Revised)

**Key decisions from critique discussion:**
- Ordering by blocking risk, not ease of implementation
- Two explicit tracks: Platform and Biology, with platform gating biology
- All ergonomics move after M19; only `table2asn` is near-term alongside M19

---

### Platform Track

Platform work gates biology expansion. No new biology pipeline should start
until the platform step it depends on is complete.

#### Step P1: Architecture Unlock (Start now)

**Gate:** Nothing in the biology track starts until P1 is complete.

| Item | Status | Effort | Notes |
|---|---|---|---|
| **M19: Caching/Resumability** | Not started | Large | Unblocks composed DAG execution; only open critical-path milestone |
| DESIGN.md Section 7.4 update | Not started | Trivial | Remove Flyte Slurm plugin; document 2FA/authenticated-session model |

#### Step P2: Platform Ergonomics (After P1)

All ergonomics land after M19, not alongside it. Ordering within P2 is by
blocking risk: items that affect whether users can recover from failures first,
discoverability second, convenience third.

| Item | Status | Effort | Blocking risk |
|---|---|---|---|
| TODO 9: Resource-escalation retry | Missing | Medium | Users cannot recover from OOM/TIMEOUT without manual recipe reconstruction |
| TODO 7: Configurable module loading | Missing | Low | Users cannot run pipelines requiring custom HPC modules |
| TODO 8: Job log fetching (partial→complete) | Partial | Medium | Users must SSH to debug; the path is returned but not the content |
| TODO 15: Actionable error messages (partial→complete) | Partial | Low | Declined requests give no actionable path to resolution |
| TODO 12: Run dashboard / list_runs | Missing | Medium | Users have no view of past runs; pointer files are not thread-safe |
| TODO 16: Runtime binding discovery | Missing | Medium | Trial-and-error is the only way to learn required bindings |
| TODO 17: Result inspection tool | Missing | Low | Results exist but are not interpretable through MCP |
| TODO 19: MCP resources for runs/recipes | Missing | Low | Saved recipes and run records are not browsable |
| TODO 11: Job polling / wait | Missing | Medium | Quality-of-life; not blocking but avoids repetitive manual calls |
| TODO 14: Job dependency chains | Missing | Medium | Needed for GATK multi-step Slurm (pairs with GATK Phase 3c) |

**Bundling suggestion:**
- **P2a (HPC recovery):** TODO 9 + TODO 7 -- both touch `specs.py` and
  `spec_executor.py`; fix the two hardest HPC failure modes together
- **P2b (observability):** TODO 8 + TODO 12 + TODO 11 -- all touch
  `spec_executor.py` reconcile and `server.py` Slurm tools
- **P2c (MCP discoverability):** TODO 15 + TODO 16 + TODO 17 + TODO 19 --
  all touch `server.py` and `planning.py`; no HPC code changes
- **P2d (advanced HPC):** TODO 14 (job dependencies) -- defer until GATK
  Phase 3c needs it; not blocking current workflows

#### Step P3: Extended Platform (Later, demand-driven)

| Item | Status | Effort | Trigger |
|---|---|---|---|
| TODO 10: Job arrays | Missing | Med-large | When batch parallel runs are needed (100 genomes) |
| TODO 18: Guided workflow mode | Missing | Large | When collaborator adoption becomes the bottleneck |
| TODO 13: Email notifications | Missing | Low | Trivial when users ask for it |
| TODO 20: Result index | Missing | Large | When filesystem manifest lookup becomes a bottleneck |

---

### Biology Track

Biology work is gated on platform readiness. The dependency model is explicit:

```
P1 (M19) complete
    └── table2asn (standalone, no platform deps beyond what already exists)
    └── GATK Phase 3a (tasks only, no shared files)
            └── P2a complete (HPC recovery) -- needed before GATK runs Slurm jobs
                └── GATK Phase 3b (workflows + new planner types)
                        └── P2b complete (observability) -- log fetch, dashboard
                            └── GATK Phase 3c (registry, MCP integration)
                                    └── P2d complete (job dependencies)
                                        └── GATK full Slurm pipeline
```

#### Step B1: Complete the Annotation Pipeline (Alongside P1)

| Item | Status | Effort | Notes |
|---|---|---|---|
| TODO 1: table2asn | Not started | Small | No platform deps beyond existing; can start now on its own branch |

#### Step B2: GATK Variant Calling (After P1 + P2a)

Three sub-milestones on a `gatk-pipeline` branch:

| Sub-milestone | Gate | Effort | Files touched |
|---|---|---|---|
| **B2a: GATK tasks** -- 14 tasks ported from Stargazer with `run_tool()`, SIF support, `run_manifest.json` | P1 complete | Medium | New files only: `src/flytetest/tasks/gatk/` |
| **B2b: GATK workflows** -- `prepare_reference`, `preprocess_sample`, `germline_short_variant_discovery`; new planner types `DnaReadSet`, `VariantCallSet`, `KnownSitesBundle` | P2a complete | Medium | New files + `src/flytetest/types/` |
| **B2c: GATK integration** -- registry entries, MCP handlers, composition metadata, Slurm submission for joint genotyping | P2b + P2d complete | Medium | Shared files: `registry.py`, `server.py`, `planning.py` |

#### Step B3: Extended Biology (After GATK proves multi-pipeline model)

Items are independent; pick by demand.

| Item | Status | Effort | Gate |
|---|---|---|---|
| TODO 6: Genome assembly QC (QUAST, BUSCO genome mode) | Not started | Small-med | P1 |
| TODO 4: Differential expression (DESeq2 + tximport) | Not started | Medium | P1 + R container support |
| TODO 3: scRNA-seq clustering (scanpy, from Stargazer) | Not started | Medium | When collaborator requests it |
| TODO 5: Structural variants (Manta/Delly) | Not started | Medium | GATK B2 complete |

---

## Execution Notes

**Branch strategy:**
- Platform (P1, P2): `realtime` branch directly, following existing milestone
  conventions. Each bundle (P2a/b/c/d) gets its own checklist entry.
- table2asn (B1): standalone branch, merge into `realtime` after P1.
- GATK (B2a/b/c): `gatk-pipeline` branch. Sub-milestones merge into `realtime`
  sequentially. B2a can start immediately after P1 since it's additive-only.
- Extended biology (B3): feature branches, picked by demand.

**Conflict risk is low:**
- B2a (GATK tasks) is entirely new files -- zero conflict with P2 changes.
- B2b introduces new types and new workflow files -- low conflict.
- B2c (registry, server.py, planning.py) intentionally waits until P2b/d are
  stable to avoid merge conflicts in the most-edited files.

**Milestone doc convention:** Each step/bundle gets a plan doc under
`docs/realtime_refactor_plans/` and a checklist entry in
`docs/realtime_refactor_checklist.md`, following the existing pattern.

**Assumptions (explicit):**
- Remote Flyte backend deployment is not a near-term goal; Flyte is used as a
  local typed-workflow framework only.
- Container and module handling remain user-supplied (SIF paths, module names)
  rather than centrally managed.
- The authenticated-session `sbatch` model is the permanent HPC execution
  architecture, not a temporary workaround.
- Composition via registry graph traversal (M15) is the planner model; there is
  no LLM-backed prompt interpretation planned in any near-term milestone.

---

## Bottom Line

The project has achieved ~90% of its core design goals. The architecture is
clean, the biological pipeline is complete through AGAT, and the Slurm path
works correctly for the 2FA-constrained HPC environment.

The revised critique agrees with the direction but pushes back on the ordering.
The response to that critique:

1. **Status audit confirms gaps are real** -- 0 items are "Already Done," 2 are
   "Partial," 11 are genuinely missing. The plan is not stale.
2. **Two explicit tracks** with a dependency model replace the single ranked
   list. Platform gates biology. No GATK work starts until M19 is done.
3. **All ergonomics move after M19** -- only `table2asn` runs alongside M19
   since it has no platform dependencies. Quick wins are real wins but they
   don't outrank composition safety.
4. **Ordering within P2 is by blocking risk:** HPC recovery (OOM retry, module
   loading) before observability (log fetch, dashboard) before discoverability
   (error messages, binding discovery, MCP resources).
5. **DESIGN.md update is a trivial prerequisite** -- remove the Flyte Slurm
   plugin framing, document the 2FA/authenticated-session model as the chosen
   architecture before any implementation starts.

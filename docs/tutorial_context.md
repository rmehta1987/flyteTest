# Tutorial Context

Use this document as the canonical prompt-planning reference for Galaxy-backed
tutorial context in FLyteTest.

Scope note:

- the executable MCP showcase in this milestone exposes only `ab_initio_annotation_braker3`, `protein_evidence_alignment`, and `exonerate_align_chunk`
- the broader stage references below are implementation context for future work, not the current server-exposed planning surface

## Purpose

This file explains how to use Galaxy tutorials and the local stage-specific
fixture files as reference context when:

- prompting Codex to implement or refine tasks
- prompting Codex to assemble local or Apptainer-backed commands
- designing smoke tests for a workflow or task family
- deciding which local fixture set should validate a given stage

This file is intentionally prompt-oriented. It complements:

- `README.md` for the user-facing stage and fixture summary
- `src/flytetest/registry.py` for exact task and workflow names
- `docs/tool_refs/*.md` for concise stage notes
- `docs/braker3_evm_notes.md` for the biological source of truth

Human-readable role:

- explain why specific tutorial datasets or local fixtures are useful
- show which biological stage a tutorial supports
- make clear when a tutorial is only context rather than implemented behavior

Coding-agent role:

- choose fixture paths and smoke-test scope before editing tasks or workflows
- avoid inventing unsupported tool steps from tutorial material alone
- keep prompt-driven workflow generation tied to explicit local inputs, typed
  plans, and saved replayable artifacts when a new workflow shape is needed

## Core Rule

Use tutorials as reference context for:

- expected biological stage boundaries
- realistic input and output shapes
- fixture selection for smoke testing
- command-line intent and stage ordering

Do not use tutorials as the source of truth for:

- exact FLyteTest task names
- exact FLyteTest workflow names
- manifest field names
- implemented-vs-deferred repo scope

For those repo-specific details, use:

- `src/flytetest/registry.py`
- the touched task and workflow modules
- `README.md`

## Local Fixture Roots

Prefer the local stage-specific fixture files under `data/` instead of
re-downloading tutorial assets during ordinary implementation or test work.

Current canonical roots:

- `data/transcriptomics/ref-based/`
- `data/braker3/reference/`
- `data/braker3/rnaseq/`
- `data/braker3/protein_data/fastas/`
- `data/pasa/`
- `data/images/`

Use the stage-specific subdirectories for lightweight smoke tests and clearer
provenance. Prefer the stage-local paths listed below unless a prompt
explicitly needs another stage-local tutorial asset from the same stage
family.

## Typed Binding Templates

Use this section when you want a copy-paste starting point for the
`bindings={...}` argument to `run_task` / `run_workflow`.  One entry per
supported planner type.  Each template shows the raw-path form and
points to the `$manifest` and `$ref` alternatives documented in
[docs/mcp_showcase.md → Binding Grammar](mcp_showcase.md#binding-grammar).

All three forms are accepted anywhere a binding value appears:

- raw path — literal paths on local disk
- `$manifest` — point at a result folder's `run_manifest.json` and let
  the resolver pick the output matching the planner type (`output_name`
  required when more than one output matches)
- `$ref` — name a prior run's output by `recipe_id`, chaining two runs
  without touching any paths

### ReferenceGenome

The main genome description used during planning.

```text
bindings:
  ReferenceGenome:
    fasta_path: "data/braker3/reference/genome.fa"
    # Optional: organism_name, assembly_name, taxonomy_id,
    # softmasked_fasta_path, annotation_gff3_path
```

Alternatives:

```text
# Reuse a reference emitted by a prior repeat-filtering run.
bindings:
  ReferenceGenome:
    $manifest: "results/repeat_filter_results_20260420/run_manifest.json"
    output_name: "softmasked_genome"
```

```text
# Reuse the reference locked into an earlier BRAKER3 run.
bindings:
  ReferenceGenome:
    $ref:
      run_id:      "20260420T101500.000Z-ab_initio_annotation_braker3"
      output_name: "reference_genome"
```

### ReadSet

Paired-end RNA-seq reads for transcript-evidence generation.

```text
bindings:
  ReadSet:
    sample_id:         "demo"
    left_reads_path:   "data/braker3/rnaseq/reads_1.fq.gz"
    right_reads_path:  "data/braker3/rnaseq/reads_2.fq.gz"
    # Optional: platform, strandedness, condition, replicate_label
```

`$manifest` and `$ref` forms are available when a prior run recorded
the read set — e.g., reusing the same RNA-seq sample across BRAKER3
and transcript-evidence workflows.

### TranscriptEvidenceSet

The transcript-evidence boundary spanning reads, BAMs, and assemblies.

```text
bindings:
  TranscriptEvidenceSet:
    reference_genome:
      fasta_path: "data/braker3/reference/genome.fa"
    # Optional: read_sets, de_novo_transcripts_path,
    # genome_guided_transcripts_path, stringtie_gtf_path,
    # merged_bam_path, pasa_assemblies_gff3_path
```

Typical `$ref` use: pull the merged BAM and StringTie GTF from an
earlier transcript-evidence run into BRAKER3 without re-running STAR.

### ProteinEvidenceSet

Protein evidence — raw FASTA, aligned evidence, or both.

```text
bindings:
  ProteinEvidenceSet:
    source_protein_fastas:
      - "data/braker3/protein_data/fastas/proteins.fa"
    # Optional: reference_genome, evm_ready_gff3_path,
    # raw_alignment_path
```

Use `$ref` to pick up `evm_ready_gff3_path` from a prior
`protein_evidence_alignment` run when feeding EVM.

### AnnotationEvidenceSet

The evidence bundle for consensus-annotation (EVM) steps.

```text
bindings:
  AnnotationEvidenceSet:
    reference_genome:
      fasta_path: "data/braker3/reference/genome.fa"
    # Optional: transcript_evidence, protein_evidence,
    # transcript_alignments_gff3_path, protein_alignments_gff3_path,
    # ab_initio_predictions_gff3_path, combined_predictions_gff3_path
```

Canonical chain: `ab_initio_annotation_braker3` →
`consensus_annotation_evm_prep` via
`$ref` bindings on `ab_initio_predictions_gff3_path` and
`protein_alignments_gff3_path`.

### ConsensusAnnotation

The consensus annotation boundary for downstream refinement and QC.

```text
bindings:
  ConsensusAnnotation:
    reference_genome:
      fasta_path: "data/braker3/reference/genome.fa"
    annotation_gff3_path: "results/evm_results_20260420/annotation.gff3"
    # Optional: weights_path, supporting_evidence,
    # protein_fasta_path
```

`$ref` into `ConsensusAnnotation` is the common pattern for PASA
refinement, BUSCO QC, and AGAT post-processing.

### QualityAssessmentTarget

The QC target used by BUSCO, functional annotation, and review stages.

```text
bindings:
  QualityAssessmentTarget:
    proteins_fasta_path: "data/busco/fixtures/proteins.fa"
    # Optional: reference_genome, consensus_annotation,
    # annotation_gff3_path
```

### `$ref` cross-run reuse — the conversation

The continuity between replies is the point of `recipe_id`.  Here is
the exact conversation that chains a BRAKER3 run into BUSCO QC without
re-specifying any paths.

**Turn 1 — run BRAKER3:**

```text
Call run_workflow with:
  workflow_name: "ab_initio_annotation_braker3"
  bindings:       <bundle.bindings from load_bundle("braker3_small_eukaryote")>
  inputs:         <bundle.inputs>
  runtime_images: <bundle.runtime_images>
  source_prompt:  "Annotate the small-eukaryote starter kit."
```

**Reply — the `recipe_id` is the durable handle:**

```text
supported:    true
recipe_id:    "20260421T090000.000Z-ab_initio_annotation_braker3"
outputs:      {"annotation_gff": "results/braker3_results_20260421/braker.gff3",
               "reference_genome": "data/braker3/reference/genome.fa"}
run_record_path: "…"
```

**Turn 2 — feed that `recipe_id` straight into the next call's `$ref`:**

```text
Call run_workflow with:
  workflow_name: "annotation_qc_busco"
  bindings:
    QualityAssessmentTarget:
      $ref:
        run_id:      "20260421T090000.000Z-ab_initio_annotation_braker3"
        output_name: "annotation_gff"
  inputs:
    lineage_dataset: "eukaryota_odb10"
    busco_mode:      "proteins"
  source_prompt: "QC the BRAKER3 annotation against eukaryota_odb10."
```

The resolver reads `.runtime/durable_asset_index.json`, looks up
`annotation_gff` under the cited `run_id`, type-checks it against
`QualityAssessmentTarget`, and materializes the path.  Unknown run IDs,
unknown output names, and type mismatches all return a structured
`PlanDecline` with populated `suggested_bundles`, `suggested_prior_runs`,
and `next_steps`.

## Stage Mapping

Use the Galaxy Tutorial Test Matrix in `README.md` as the high-level map from
repo stage to tutorial source.

Before writing testing expectations for a future milestone prompt, first check
whether that stage already has a documented tutorial-backed dataset or local
fixture set in `README.md`, this file, or `data/`. Prefer those
real-data fixtures for bounded smoke tests when they exist; fall back to
synthetic tests only when no suitable tutorial-backed fixture is available or
the required binaries are missing.

In practice:

- use the Braker3 tutorial for protein-evidence and BRAKER3 prompts
- use the reference-based RNA-seq tutorial for the older QC and quant baseline
- use the de novo transcriptomics tutorial for transcript-evidence prompts
- use the RepeatMasker tutorial for repeat-filtering prompts, especially when planning how to generate a local `.out` file for the implemented downstream cleanup workflow
- use the functional-annotation tutorial for EggNOG or protein-annotation prompts

Additional GTN references that are useful at the tool level:

- `STAR`: https://training.galaxyproject.org/training-material/by-tool/iuc/rgrnastar/rna_star.html
- `StringTie`: https://training.galaxyproject.org/training-material/by-tool/iuc/stringtie/stringtie.html
- `StringTie merge`: https://training.galaxyproject.org/training-material/by-tool/iuc/stringtie/stringtie_merge.html
- `Trinity`: https://training.galaxyproject.org/training-material/by-tool/iuc/trinity/trinity.html
- `TransDecoder`: https://training.galaxyproject.org/training-material/by-tool/iuc/transdecoder/transdecoder.html
- full de novo `Trinity` + `TransDecoder` tutorial: https://training.galaxyproject.org/training-material/topics/transcriptomics/tutorials/full-de-novo/tutorial.html
- `eggNOG-mapper`: https://training.galaxyproject.org/training-material/by-tool/galaxyp/eggnog_mapper/eggnog_mapper.html

Tools in the current notes that do not appear to have strong GTN coverage as standalone references:

- `PASA`
- `Exonerate`
- `EVidenceModeler`
- `AGAT`
- `table2asn`

For those tools, prefer the repo-local notes, tool refs, and implementation docs over tutorial-style GTN guidance.

If a stage is still deferred in the repo, keep the prompt scoped to contract
definition, task design, or smoke-test planning rather than implying full support
already exists. For implemented repeat-filtering work, prompts should name the
actual workflow and task boundaries now present in the repo rather than
describing repeat filtering as future-only.

## Prompting Rules

When prompting future work, include all of the following:

- the biological stage
- the FLyteTest task or workflow name
- the local fixture paths to use
- the expected outputs or result bundle
- any milestone stop rule that constrains scope

Good prompts name one stage and one contract. Avoid prompts that mix:

- upstream download logic
- tool installation
- task implementation
- workflow wiring
- post-processing outside the active milestone

## Apptainer Guidance

When a task or workflow exposes a `*_sif` input, prefer asking for:

- an Apptainer-backed local command plan
- explicit input paths
- explicit output paths
- explicit bind-mount reasoning
- the expected output files or result directory

Prefer prompts like:

```text
Use the FLyteTest Braker3 tutorial context.

Task:
- assemble the local Apptainer command plan for `ab_initio_annotation_braker3`

Inputs:
- data/braker3/reference/genome.fa
- data/braker3/rnaseq/RNAseq.bam
- data/braker3/protein_data/fastas/proteins.fa
- a local `braker3_sif`

Output:
- expected `braker.gff3`
- normalized downstream-ready GFF3
- result bundle contents

Constraints:
- local-first
- no extra network fetching
- keep behavior faithful to `docs/braker3_evm_notes.md`
- be explicit about inferred BRAKER3 details
```

Avoid prompts that only say:

- "run the Galaxy tutorial"
- "make the container command"
- "use Apptainer for this stage"

Those are too underspecified for reproducible results.

## Task-Implementation Guidance

When asking Codex to create or refine a task, structure the prompt around:

- the registry entry name
- the tutorial stage it maps to
- the exact fixture files for smoke tests
- the expected inputs and outputs
- what is inferred versus directly stated in the notes

Prefer prompts like:

```text
Implement or refine `exonerate_align_chunk`.

Reference context:
- README Galaxy Tutorial Test Matrix
- docs/tool_refs/exonerate.md
- Braker3 tutorial-derived fixtures under `data/`

Smoke-test inputs:
- data/braker3/reference/genome.fa
- data/braker3/protein_data/fastas/proteins.fa

Requirements:
- preserve deterministic chunk behavior
- keep manifest output stable
- support optional `exonerate_sif`
- do not expand into EVM or downstream stages
```

## Smoke-Test Guidance

Use tutorial-backed data for smoke tests when:

- the relevant binary is available locally
- the fixture size is small enough to keep the suite practical
- the goal is to validate command wiring, path resolution, and collector logic

Keep synthetic tests as the primary fallback when:

- binaries are unavailable
- a stage is partially implemented
- a tutorial dataset is too large or too slow for routine runs
- the behavior being checked is deterministic path shaping rather than real tool execution

## Testing With Existing Local Data

Use this section when you want prompt templates specifically for the fixture files
already present under `data/`.

Current directly usable local files:

- `data/transcriptomics/ref-based/reads_1.fq.gz`
- `data/transcriptomics/ref-based/reads_2.fq.gz`
- `data/transcriptomics/ref-based/transcriptome.fa`
- `data/braker3/reference/genome.fa`
- `data/braker3/rnaseq/RNAseq.bam`
- `data/braker3/protein_data/fastas/proteins.fa`
- `data/braker3/protein_data/fastas/proteins_extra.fa`

The extra protein FASTA is a tiny synthetic helper used to keep
multi-input protein-evidence and planner tests realistic.

Practical rule:

- use stage-local read, genome, BAM, and protein files under `data/` for direct tool smoke tests
- use `data/images/*.sif` when you want a local Apptainer-backed smoke run without relying on the RCC `/project` image paths
- use the RCC `/project/rcc/hyadav/genomes` image paths for the standard Trinity and STAR cluster wrappers, and the shared StringTie binary at `/project/rcc/hyadav/genomes/software/stringtie/stringtie`
- use `data/images/pasa_2.5.3.sif` for the local PASA Apptainer image smoke, or scp the PASA image to the cluster and point `PASA_SIF` at that cluster path
- the PASA Apptainer image smoke does not currently support the legacy
  `seqclean` path; see
  https://github.com/PASApipeline/PASApipeline/issues/73
- use stage result bundles or synthetic fixtures for PASA, TransDecoder, and EVM work
- use the Trinity FASTA emitted under `results/minimal_transcriptomics_smoke/
  trinity/` as the source for the wiki-shaped PASA host smoke; the host-based
  helper stages that FASTA under its original basename and runs
  `Launch_PASA_pipeline.pl` directly against the genome FASTA, and the
  selected basename is often `trinity_out_dir.Trinity.fasta` or
  `Trinity.tmp.fasta`
- use the same Trinity FASTA and genome FASTA with `data/images/pasa_2.5.3.sif`
  when you want the Apptainer-backed PASA image smoke
- use the checked-in cleaned Trinity fixture from
  `results/pasa_update_results_20260402_120000/finalized/transcripts/`
  when you want to study the older align/assemble staging shape in the result
  bundles, not as the current smoke path
- prefer the stage-specific subdirectories unless a prompt explicitly needs
  another stage-local tutorial asset

### Direct `data/` Smoke-Test Prompt Templates

#### FastQC

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/fastqc.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `fastqc`

Fixture inputs:
- data/transcriptomics/ref-based/reads_1.fq.gz
- data/transcriptomics/ref-based/reads_2.fq.gz

Requirements:
- treat this as descriptive read QC only
- support optional `fastqc_sif`
- preserve separate HTML and ZIP outputs per mate
- keep the output layout deterministic and local-first

Validation:
- check for HTML and ZIP outputs for each input FASTQ
- keep this scoped to the legacy `rnaseq_qc_quant` baseline
```

#### Salmon

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/salmon.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `salmon_index` and `salmon_quant`

Fixture inputs:
- data/transcriptomics/ref-based/transcriptome.fa
- data/transcriptomics/ref-based/reads_1.fq.gz
- data/transcriptomics/ref-based/reads_2.fq.gz

Requirements:
- keep index creation and quantification as separate boundaries
- support optional `salmon_sif`
- preserve `quant.sf` as the main output contract
- keep this stage inside the legacy `rnaseq_qc_quant` baseline

Validation:
- check for a stable index directory plus `quant.sf`
- do not expand scope into genome-annotation workflows
```

#### STAR

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/star.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `star_genome_index` and `star_align_sample`

Fixture inputs:
- data/braker3/reference/genome.fa
- data/transcriptomics/ref-based/reads_1.fq.gz
- data/transcriptomics/ref-based/reads_2.fq.gz

Requirements:
- keep indexing and alignment as separate stages
- support optional `star_sif`
- preserve BAM and log outputs for downstream transcript-evidence tasks
- stay honest about the current single-sample transcript-evidence scope

Validation:
- check for a STAR index directory and an alignment directory with BAM outputs
- keep this as command-wiring smoke coverage, not a claim of full notes-faithful transcript evidence
```

#### samtools

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/samtools.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `samtools_merge_bams`

Fixture inputs:
- data/braker3/rnaseq/RNAseq.bam

Requirements:
- keep the merge boundary explicit even if the smoke test uses one BAM
- support optional `samtools_sif`
- preserve deterministic output naming
- do not silently add sort or index unless the task contract changes

Validation:
- check for a merged BAM stage output
- keep the test focused on BAM-path and collector behavior
```

#### Trinity Genome-Guided

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/trinity.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `trinity_genome_guided_assemble`

Fixture inputs:
- data/braker3/rnaseq/RNAseq.bam

Requirements:
- keep this scoped to genome-guided Trinity only
- support optional `trinity_sif`
- preserve a deterministic Trinity output directory
- do not collapse this into the separate de novo Trinity boundary upstream

Validation:
- check for the expected genome-guided Trinity output directory and transcript FASTA
- keep this as a stage-boundary smoke test
```

#### StringTie

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/stringtie.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `stringtie_assemble`

Fixture inputs:
- data/braker3/rnaseq/RNAseq.bam

Requirements:
- support optional `stringtie_sif`
- preserve `transcripts.gtf` and `gene_abund.tab`
- keep the fixed note-aligned StringTie parameters explicit
- keep this as a standalone assembly boundary

Validation:
- check for `transcripts.gtf` and `gene_abund.tab`
- keep the test focused on command wiring and output collection
```

#### Exonerate

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/exonerate.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- run or refine `exonerate_align_chunk` and `exonerate_to_evm_gff3`

Fixture inputs:
- data/braker3/reference/genome.fa
- data/braker3/protein_data/fastas/proteins.fa

Requirements:
- keep chunked alignment and GFF3 conversion explicit
- support optional `exonerate_sif`
- preserve deterministic chunk behavior when chunking is included
- keep all protein inputs local and explicit

Validation:
- check for raw Exonerate output plus EVM-ready GFF3
- do not expand into BRAKER3, EVM, or downstream stages
```

#### BRAKER3

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/braker3.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- run or refine `ab_initio_annotation_braker3`

Fixture inputs:
- data/braker3/reference/genome.fa
- data/braker3/rnaseq/RNAseq.bam
- data/braker3/protein_data/fastas/proteins.fa

Requirements:
- preserve the current tutorial-backed BRAKER3 boundary
- support optional `braker3_sif`
- emit stable `braker.gff3` output plus normalized downstream-ready GFF3
- keep inferred BRAKER3 behavior clearly labeled as inferred

Validation:
- check for `braker.gff3`, normalized GFF3 output, and a stable result bundle
- keep manifest language explicit about tutorial-backed runtime versus repo policy
```

### Upstream-Bundle Or Synthetic Prompt Templates

Use these when a stage cannot be tested directly from the raw `data/` files
alone.

#### PASA

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/pasa.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `pasa_transcript_alignment`

Fixture inputs:
- transcript-evidence results bundle or equivalent synthetic transcript fixtures
- explicit PASA config template

Requirements:
- keep the internally staged de novo Trinity, Trinity-GG, and StringTie inputs explicit
- preserve separate PASA setup and align/assemble boundaries
- support optional `pasa_sif`

Validation:
- prefer synthetic tests or prebuilt upstream bundles when raw `data/` files are not enough
- keep manifest language explicit about the remaining single-sample upstream simplification
```

#### TransDecoder

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/transdecoder.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py

Task:
- run or refine `transdecoder_train_from_pasa` or `transdecoder_from_pasa`

Fixture inputs:
- PASA results bundle or equivalent synthetic PASA transcript outputs

Requirements:
- keep this stage downstream of PASA outputs
- support optional `transdecoder_sif`
- preserve transcript-level and genome-level ORF evidence outputs
- label inferred command behavior clearly

Validation:
- prefer synthetic tests or prebuilt PASA outputs rather than raw `data/` files alone
- keep the scope limited to coding-prediction outputs
```

#### EVM Prep And Execution

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/evidencemodeler.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- run or refine `consensus_annotation_evm_prep` or `consensus_annotation_evm`

Fixture inputs:
- staged PASA outputs resolving to `transcripts.gff3`
- staged TransDecoder and BRAKER3 outputs resolving to `predictions.gff3`
- staged protein-evidence outputs resolving to `proteins.gff3`
- synthetic or staged genome reference bundle

Requirements:
- preserve explicit pre-EVM assembly, partitioning, execution, and recombination boundaries
- keep inferred EVM weights or other repo-default policy visible
- do not describe the stage as directly testable from raw `data/` files alone

Validation:
- prefer synthetic tests and staged upstream result bundles
- focus on contract assembly, command generation, execution order, and result collection
```

## Scope Guardrails

When using tutorials as context, keep these repo rules visible:

- `docs/braker3_evm_notes.md` remains the biological source of truth
- `README.md` remains the user-facing scope summary
- `src/flytetest/registry.py` remains the naming contract
- task and workflow prompts should stay deterministic and local-first
- network fetching should happen only for explicit fixture-refresh work
- inferred behavior must be labeled as inferred behavior

## Stage Prompt Templates

Copy and adapt the blocks below when you want a stage-specific starting prompt.

### Exonerate Protein Evidence

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/exonerate.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- implement, refine, or run `protein_evidence_alignment`
- if task-level work is needed, focus on `exonerate_align_chunk`

Fixture inputs:
- data/braker3/reference/genome.fa
- data/braker3/protein_data/fastas/proteins.fa

Requirements:
- keep protein staging and chunking deterministic
- preserve manifest stability
- support optional `exonerate_sif`
- keep outputs EVM-ready and local-first
- do not expand into BRAKER3, EVM, or downstream stages unless explicitly requested

Validation:
- use the Braker3 tutorial-derived local fixtures for smoke coverage
- keep synthetic tests as the fallback when `exonerate` is unavailable
```

### BRAKER3 Workflow

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/braker3.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- implement, refine, or run `ab_initio_annotation_braker3`

Fixture inputs:
- data/braker3/reference/genome.fa
- data/braker3/rnaseq/RNAseq.bam
- data/braker3/protein_data/fastas/proteins.fa

Requirements:
- preserve the current local-first BRAKER3 boundary
- support optional `braker3_sif`
- emit stable `braker.gff3` resolution plus normalized downstream-ready GFF3
- be explicit about inferred BRAKER3 details from the notes
- do not broaden scope into repeat filtering or post-BRAKER3 stages unless requested

Validation:
- prefer tutorial-backed smoke coverage with the local stage-specific Braker3
  fixtures
- keep deterministic collector and manifest tests in place even when BRAKER3 is unavailable
```

### PASA And TransDecoder

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/pasa.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/transdecoder.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- implement, refine, or run `pasa_transcript_alignment` or `transdecoder_from_pasa`
- if task-level work is needed, focus on `pasa_align_assemble` or `transdecoder_train_from_pasa`

Fixture inputs:
- transcript-evidence results bundle or tutorial-backed transcript fixtures
- explicit PASA config template when required

Requirements:
- keep PASA setup, align/assemble, and TransDecoder stages explicit
- support optional `pasa_sif` and `transdecoder_sif`
- preserve stable result bundles and manifest fields
- label inferred TransDecoder behavior clearly where the notes do not spell out commands
- do not collapse PASA and TransDecoder into one opaque stage

Validation:
- use synthetic tests for path shaping and manifest logic when binaries are unavailable
- add tutorial-backed smoke tests when fixture size and tool availability make that practical
```

### EVM Prep And Execution

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/evidencemodeler.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- implement, refine, or run `consensus_annotation_evm_prep` or `consensus_annotation_evm`
- if task-level work is needed, focus on `evm_partition_inputs` and the other explicit EVM execution tasks

Fixture inputs:
- staged upstream outputs resolving to `transcripts.gff3`, `predictions.gff3`, `proteins.gff3`
- authoritative genome FASTA from the staged upstream boundary

Requirements:
- keep EVM prep separate from EVM execution
- preserve deterministic weights staging, partitioning, command generation, execution order, and recombination
- support optional container-backed execution where the workflow exposes it
- keep repo scope honest about what is synthetic versus tool-backed
- do not mix EVM work with BUSCO, EggNOG, AGAT, or submission-prep unless explicitly requested

Validation:
- use synthetic contract bundles for deterministic EVM execution tests when the EVM binary is unavailable
- verify exact filename-level assembly for the pre-EVM contract
```

### PASA Post-EVM Refinement

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/docs/tool_refs/pasa.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Task:
- implement, refine, or run `annotation_refinement_pasa`
- if task-level work is needed, focus on `pasa_update_gene_models`

Fixture inputs:
- PASA results bundle
- EVM results bundle resolving to the current annotation GFF3
- explicit annotCompare config template when required

Requirements:
- keep the PASA update rounds explicit and reviewable
- preserve deterministic staging and final promoted outputs
- support optional `pasa_sif`
- clearly distinguish implemented update behavior from later repeat filtering and annotation steps
- do not broaden into BUSCO, EggNOG, AGAT, or submission-prep unless explicitly requested

Validation:
- prefer synthetic staged bundles for deterministic round-by-round testing
- use tool-backed smoke coverage only when PASA and its dependencies are available locally
```

## Slurm Execution

Running stages on the RCC cluster goes through the MCP Slurm path. The
full lifecycle — prepare, submit, monitor, retry, cancel — is documented in
`docs/mcp_showcase.md` under **Validated Slurm Walkthrough**.

Key points for tutorial-oriented work:

- All Slurm tools require the MCP server to run inside an already-authenticated
  HPC login session; the cluster's 2FA policy prevents unattended SSH access.
- Resource settings (`cpu`, `memory`, `queue`, `account`, `walltime`) are
  frozen into the saved recipe at prepare time via `resource_request` and
  cannot be changed without preparing a new recipe.
- `TIMEOUT` and `OUT_OF_MEMORY` failures are terminal — recovering requires a
  new `prepare_run_recipe` call with a larger `resource_request`, not a retry
  of the same artifact.
- For smoke-test sized runs, the BUSCO fixture is the validated reference: 2
  CPUs, 8 Gi memory, `caslake` queue, 10-minute walltime.

## Short Reusable Prompt Block

Copy this block when you want a compact tutorial-aware prompt prefix:

```text
Use FLyteTest tutorial context from:

- /home/rmeht/Projects/flyteTest/docs/tutorial_context.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/src/flytetest/registry.py
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md

Treat the tutorial docs as stage reference only.
Treat the registry and current code as the source of truth for task names,
workflow names, and implemented scope.
Prefer local stage-specific fixtures under `data/`.
Be explicit about inferred behavior and do not broaden scope past the active milestone.
```

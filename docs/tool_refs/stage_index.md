# Stage Index

This page groups FLyteTest tool references by biological stage so future prompts can start from intent instead of hunting through tool files one by one.

Scope note:

- the current executable MCP showcase still exposes a narrow surface, but the repo now implements and documents broader stage families for PASA, TransDecoder, repeat filtering, BUSCO, EggNOG, AGAT, and EVM prep/execution
- the stage refs below are planning aids that stay anchored to implemented task and workflow boundaries rather than to an incomplete showcase catalog

Use this page when:

- you know the pipeline stage you want to work on
- you want the right tool refs for that stage
- you want a copy-paste prompt starter that names the real FLyteTest workflow or task boundary

For tutorial-backed fixture context and stage-to-dataset mapping, see [tutorial_context.md](/home/rmeht/Projects/flyteTest/.codex/agent/tutorial_context.md). For current repo scope and milestone status, see [README.md](/home/rmeht/Projects/flyteTest/README.md).

## Transcript Evidence

Stage status:

- implemented with documented simplifications
- the current workflow now includes both Trinity branches required upstream of PASA
- the remaining simplification is the single-sample STAR alignment and BAM merge path rather than the full notes-backed all-sample contract

Primary workflow:

- `transcript_evidence_generation`

Primary tasks:

- `trinity_denovo_assemble`
- `star_genome_index`
- `star_align_sample`
- `samtools_merge_bams`
- `trinity_genome_guided_assemble`
- `stringtie_assemble`

Tool refs:

- [STAR](./star.md)
- [samtools](./samtools.md)
- [Trinity](./trinity.md)
- [StringTie](./stringtie.md)

Use this stage when you need to:

- create or refine STAR indexing and alignment commands
- work on the de novo Trinity boundary upstream of PASA
- keep the BAM merge boundary explicit
- work on genome-guided Trinity or StringTie outputs
- check whether a transcript-evidence prompt is still honest about current repo scope

Prompt starter:

```text
Use the transcript-evidence stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `transcript_evidence_generation` using the STAR, samtools, Trinity, and StringTie stage refs.

Context:
- keep the current workflow honest about its single-sample scope
- preserve explicit stage boundaries for de novo Trinity, index, alignment, BAM merge, Trinity-GG, and StringTie
- use local fixture data and Apptainer command patterns when relevant

Deliver:
- the command plan or task/workflow change
- expected intermediate outputs
- any assumptions that are still inferred or intentionally deferred
```

## PASA And Coding Support

Stage status:

- PASA align/assemble is implemented with documented simplifications
- PASA now consumes the internally produced de novo Trinity FASTA from the transcript-evidence bundle
- TransDecoder is implemented but remains inference-heavy relative to the notes

Primary workflows:

- `pasa_transcript_alignment`
- `annotation_refinement_pasa`
- `transdecoder_from_pasa`

Primary tasks:

- `pasa_accession_extract`
- `combine_trinity_fastas`
- `pasa_seqclean`
- `pasa_create_sqlite_db`
- `pasa_align_assemble`
- `pasa_load_current_annotations`
- `pasa_update_gene_models`
- `transdecoder_train_from_pasa`

Tool refs:

- [PASA](./pasa.md)
- [TransDecoder](./transdecoder.md)

Use this stage when you need to:

- refine PASA align/assemble inputs and config handling
- keep the internally staged Trinity inputs explicit
- work on PASA post-EVM update rounds
- refine coding-prediction handoffs from PASA assemblies

Prompt starter:

```text
Use the PASA and coding-support stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `pasa_transcript_alignment`, `annotation_refinement_pasa`, or `transdecoder_from_pasa` using the PASA and TransDecoder refs.

Context:
- keep the internally staged de novo Trinity, Trinity-GG, and StringTie inputs explicit
- preserve separate align/assemble, post-EVM update, and coding-prediction boundaries
- use local config, template, and result-bundle paths instead of generic examples

Deliver:
- the command plan or task/workflow change
- expected PASA or TransDecoder outputs
- any assumptions that remain inferred from notes or upstream docs
```

## Protein Evidence

Stage status:

- implemented with documented simplifications
- local protein FASTAs are explicit inputs and remote protein-database acquisition is intentionally out of scope

Primary workflow:

- `protein_evidence_alignment`

Primary tasks:

- `stage_protein_fastas`
- `chunk_protein_fastas`
- `exonerate_align_chunk`
- `exonerate_to_evm_gff3`
- `exonerate_concat_results`

Tool refs:

- [Exonerate](./exonerate.md)

Use this stage when you need to:

- generate Exonerate commands against local protein FASTA inputs
- preserve deterministic chunking and recombination
- refine the EVM-ready protein-evidence GFF3 handoff

Prompt starter:

```text
Use the protein-evidence stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `protein_evidence_alignment` using the Exonerate stage ref.

Context:
- keep protein staging, chunk alignment, GFF3 conversion, and final collection explicit
- preserve local-input behavior and deterministic chunk outputs
- use the repo-local fixture and result-bundle layout

Deliver:
- the command plan or task/workflow change
- expected raw and EVM-ready protein-evidence outputs
- any assumptions that remain inferred
```

## Ab Initio Annotation

Stage status:

- implemented with tutorial-backed runtime and explicit repo policy
- still intentionally narrower than a full hand-written BRAKER3 manual workflow

Primary workflow:

- `ab_initio_annotation_braker3`

Primary tasks:

- `stage_braker3_inputs`
- `braker3_predict`
- `normalize_braker3_for_evm`
- `collect_braker3_results`

Tool refs:

- [BRAKER3](./braker3.md)

Use this stage when you need to:

- generate or refine BRAKER3 commands
- check the boundary between tutorial-backed runtime and repo-local policy
- review how `braker.gff3` is normalized before EVM

Prompt starter:

```text
Use the ab initio annotation stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `ab_initio_annotation_braker3` using the BRAKER3 stage ref.

Context:
- keep the key handoff focused on `braker.gff3`
- distinguish tutorial-backed runtime choices from repo policy
- preserve source-aware normalization behavior for later EVM use

Deliver:
- the command plan or task/workflow change
- expected BRAKER3 outputs and normalization handoff
- any assumptions that remain intentionally inferred
```

## Consensus Annotation And EVM

Stage status:

- implemented with documented simplifications
- EVM prep and execution are now explicit workflow boundaries

Primary workflows:

- `consensus_annotation_evm_prep`
- `consensus_annotation_evm`

Primary tasks:

- `prepare_evm_transcript_inputs`
- `prepare_evm_protein_inputs`
- `prepare_evm_prediction_inputs`
- `prepare_evm_execution_inputs`
- `evm_partition_inputs`
- `evm_write_commands`
- `evm_execute_commands`
- `evm_recombine_outputs`

Tool refs:

- [EVidenceModeler](./evidencemodeler.md)

Use this stage when you need to:

- validate the exact pre-EVM contract
- review EVM partitioning, command generation, and recombination
- keep inferred repo-default weights explicit instead of hidden

Prompt starter:

```text
Use the consensus-annotation stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `consensus_annotation_evm_prep` or `consensus_annotation_evm` using the EVidenceModeler stage ref.

Context:
- preserve explicit pre-EVM assembly, partitioning, execution, and recombination boundaries
- keep weights inference and other repo policy visible
- validate the final contract against the notes and local manifests

Deliver:
- the command plan or task/workflow change
- expected pre-EVM and final EVM outputs
- any assumptions that still need review
```

## Repeat Filtering And Cleanup

Stage status:

- implemented with documented simplifications
- starts from the PASA-updated sorted GFF3 plus an external RepeatMasker `.out` file
- keeps RepeatMasker conversion, gffread extraction, funannotate overlap filtering, repeat blasting, and the two deterministic removal transforms explicit

Primary workflow:

- `annotation_repeat_filtering`

Primary tasks:

- `repeatmasker_out_to_bed`
- `gffread_proteins`
- `funannotate_remove_bad_models`
- `remove_overlap_repeat_models`
- `funannotate_repeat_blast`
- `remove_repeat_blast_hits`
- `collect_repeat_filter_results`

Tool refs:

- [RepeatMasker](./repeatmasker.md)
- [gffread](./gffread.md)
- [funannotate](./funannotate.md)

Use this stage when you need to:

- keep the PASA-updated GFF3 boundary explicit before functional annotation
- review how an external RepeatMasker `.out` file is normalized into the overlap-filter inputs
- refine the gffread and funannotate cleanup stages without hiding the intermediate filtered GFF3 files
- keep EggNOG, AGAT, and submission-prep work deferred while preserving the BUSCO-ready protein boundary

Prompt starter:

```text
Use the repeat-filtering stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `annotation_repeat_filtering` or one of its explicit repeat-filter tasks.

Context:
- consume the PASA-updated sorted GFF3 boundary, not an earlier EVM shortcut
- keep RepeatMasker conversion, gffread protein extraction, overlap cleanup, repeat blasting, and final GFF3/protein collection explicit
- use synthetic tests or an external RepeatMasker `.out` file for smoke-test planning; this repo does not currently ship a checked-in `data/repeatmasker/` fixture directory
- state any inferred funannotate wrapper behavior explicitly

Deliver:
- the command plan or task/workflow change
- expected intermediate and final repeat-filter outputs
- any assumptions that remain inferred from notes or local runtime constraints
```

## QC, Functional Annotation, And Post-Processing

Stage status:

- FastQC and Salmon are implemented as part of the older RNA-seq baseline
- BUSCO is now implemented as the first post-repeat-filtering QC milestone
- EggNOG-mapper is implemented as the next post-BUSCO functional-annotation milestone
- AGAT statistics, conversion, and cleanup are implemented as post-EggNOG slices
- `table2asn` submission-prep remains deferred after AGAT

Primary workflows:

- `rnaseq_qc_quant`
- `annotation_qc_busco`
- `annotation_functional_eggnog`
- `annotation_postprocess_agat`
- `annotation_postprocess_agat_conversion`
- `annotation_postprocess_agat_cleanup`

Primary tasks:

- `fastqc`
- `salmon_index`
- `salmon_quant`
- `busco_assess_proteins`
- `agat_statistics`
- `agat_convert_sp_gxf2gxf`
- `agat_cleanup_gff3`
- `collect_eggnog_results`
- `eggnog_map`

Tool refs:

- [FastQC](./fastqc.md)
- [Salmon](./salmon.md)
- [BUSCO](./busco.md)
- [EggNOG-mapper](./eggnog-mapper.md)
- [AGAT](./agat.md)

Use this stage when you need to:

- work on the legacy RNA-seq QC and quant baseline
- refine the implemented BUSCO QC boundary
- work on EggNOG functional annotation of repeat-filtered proteins
- work on AGAT statistics, conversion, or cleanup after EggNOG functional annotation while keeping `table2asn` deferred

Prompt starter:

```text
Use the QC and downstream annotation stage refs in docs/tool_refs/stage_index.md.

Goal:
Refine `annotation_qc_busco`, `annotation_functional_eggnog`, `annotation_postprocess_agat`, `annotation_postprocess_agat_conversion`, `annotation_postprocess_agat_cleanup`, `busco_assess_proteins`, or the legacy `rnaseq_qc_quant` baseline using the listed tool refs.

Context:
- keep FastQC and Salmon separate from the active genome-annotation milestone
- keep BUSCO strictly downstream of repeat filtering and keep EggNOG-mapper implemented as the next functional-annotation boundary
- preserve tool-specific input and output contracts
- keep AGAT scoped to post-EggNOG statistics, conversion, and deterministic cleanup until a later slice opens `table2asn`

Deliver:
- the command plan or task/workflow change
- expected reports or annotation-enrichment outputs
- any assumptions about deferred stages that need to remain explicit
```

Prompt starter for AGAT planning:

```text
Use the AGAT tool ref in docs/tool_refs/stage_index.md.

Goal:
Plan or implement the AGAT cleanup slice after AGAT conversion.

Context:
- keep AGAT scoped to post-processing and reporting after EggNOG
- preserve the repeat-filtered and EggNOG-annotated GFF3 boundary explicitly
- keep `table2asn` deferred until a later slice is explicitly opened

Deliver:
- the task/workflow change
- expected cleaned GFF3 output and cleanup summary
- any assumptions that remain inferred from notes or runtime constraints
```

## Submission Prep

Stage status:

- deferred future work

Primary task family:

- future `table2asn_prepare`

Tool refs:

- [table2asn](./table2asn.md)

Use this stage when you need to:

- plan NCBI submission packaging
- keep submission-prep work clearly separated from annotation generation
- document version-sensitive command behavior before implementing the stage

Prompt starter:

```text
Use the submission-prep stage refs in docs/tool_refs/stage_index.md.

Goal:
Plan the future `table2asn_prepare` stage using the table2asn tool ref.

Context:
- treat this as deferred submission-prep work
- rely on NCBI documentation rather than repo-invented defaults
- preserve version-specific validation outputs

Deliver:
- the command plan or implementation notes
- expected submission artifacts
- any assumptions that still require confirmation from NCBI docs
```

## Germline Variant Calling

Stage status:

- Milestone A complete: all seven GATK4 tasks implemented, tested, and registered
- BAM-in, VCF-out; alignment and duplicate-marking are Milestone B scope
- VQSR is deferred

Primary task family:

- `variant_calling` (pipeline_family)

Primary tasks:

- `create_sequence_dictionary`
- `index_feature_file`
- `base_recalibrator`
- `apply_bqsr`
- `haplotype_caller`
- `combine_gvcfs`
- `joint_call_gvcfs`

Tool ref:

- [GATK4](./gatk4.md)

Use this stage when you need to:

- run BQSR recalibration on a coordinate-sorted, duplicate-marked BAM
- produce per-sample GVCFs from recalibrated BAMs
- merge per-sample GVCFs into a cohort-level combined GVCF
- perform joint genotyping via GenomicsDBImport + GenotypeGVCFs

Prompt starter:

```text
Use the germline variant calling stage ref in docs/tool_refs/stage_index.md.

Goal:
Run the GATK4 germline variant calling pipeline on <sample_id>.bam.

Context:
- coordinate-sorted, duplicate-marked BAM at <path>
- reference FASTA at <ref.fa> (with .fai and .dict)
- known-sites VCFs: <dbsnp.vcf>, <mills.vcf> (must be indexed)
- cohort: <cohort_id>
- intervals for joint calling: ["<chr>"]

Deliver:
- registry entries for the seven variant_calling tasks
- expected output artifacts (BQSR table, recalibrated BAM, per-sample GVCF, cohort combined GVCF, joint-called VCF)
- any pre-flight checks needed before BaseRecalibrator
```

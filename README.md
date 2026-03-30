# FLyteTest

This repository currently implements several deterministic Flyte v2 workflows and is being refactored toward a prompt-driven genome annotation system.

Current implemented scope:

- `rnaseq_qc_quant`
- `transcript_evidence_generation`
- `pasa_transcript_alignment`
- `transdecoder_from_pasa`
- `salmon index` on a transcriptome FASTA
- `fastqc` on paired-end reads
- `salmon quant` on paired-end reads
- STAR indexing and alignment for one paired-end sample
- BAM merge stage using samtools
- genome-guided Trinity assembly
- StringTie assembly
- PASA accession extraction, transcript combination, `seqclean`, SQLite config preparation, and align/assemble
- TransDecoder coding-region prediction from PASA assemblies, including genome-coordinate GFF3 lifting for downstream annotation

The code now lives in a small package layout under `src/flytetest/`, while the original `flyte_rnaseq_workflow.py` remains as a compatibility entrypoint for `flyte run`.

## Module Layout

```text
src/flytetest/
  config.py
  registry.py
  types/
    assets.py
  tasks/
    qc.py
    quant.py
    pasa.py
    transdecoder.py
    transcript_evidence.py
  workflows/
    pasa.py
    rnaseq_qc_quant.py
    transdecoder.py
    transcript_evidence.py
flyte_rnaseq_workflow.py
docs/tool_refs/
```

- `src/flytetest/config.py`: shared Flyte environment, runtime constants, and local/HPC execution helpers
- `src/flytetest/types/assets.py`: local-first typed bioinformatics assets for future task signatures
- `src/flytetest/tasks/qc.py`: `fastqc`
- `src/flytetest/tasks/quant.py`: `salmon_index`, `salmon_quant`, `collect_results`
- `src/flytetest/tasks/pasa.py`: PASA transcript preparation, SQLite config preparation, PASA align/assemble, and PASA result collection
- `src/flytetest/tasks/transdecoder.py`: TransDecoder coding-region prediction from PASA assemblies and TransDecoder result collection
- `src/flytetest/tasks/transcript_evidence.py`: STAR, BAM merge, genome-guided Trinity, StringTie, and transcript-evidence result collection
- `src/flytetest/workflows/pasa.py`: composed PASA transcript preparation and align/assemble entrypoint
- `src/flytetest/workflows/rnaseq_qc_quant.py`: composed RNA-seq QC + quant entrypoint
- `src/flytetest/workflows/transdecoder.py`: composed TransDecoder-from-PASA entrypoint
- `src/flytetest/workflows/transcript_evidence.py`: composed transcript evidence generation entrypoint
- `src/flytetest/registry.py`: minimal static registry describing supported tasks and workflows
- `flyte_rnaseq_workflow.py`: compatibility wrapper that re-exports the runnable entrypoint and task components
- `docs/tool_refs/`: local tool references for planning and future task authoring

## Typed Asset Layer

This repo now includes a small typed asset layer in `src/flytetest/types/`:

- `ReferenceGenome`
- `TranscriptomeReference`
- `ReadPair`
- `QcReport`
- `SalmonIndexAsset`
- `SalmonQuantResult`
- `StarGenomeIndexAsset`
- `StarAlignmentResult`
- `MergedBamAsset`
- `TrinityGenomeGuidedAssemblyResult`
- `StringTieAssemblyResult`
- `TrinityDeNovoTranscriptAsset`
- `CombinedTrinityTranscriptAsset`
- `PasaCleanedTranscriptAsset`
- `PasaSqliteConfigAsset`
- `PasaAlignmentAssemblyResult`
- `TransDecoderPredictionResult`

These dataclasses are intentionally lightweight and local-first:

- they wrap local filesystem paths and basic biological metadata
- they do not add remote storage behavior
- they do not implement content addressing, CIDs, or fetch/update/query APIs
- they do not replace the current Flyte `File` and `Dir` task signatures yet

This is a staged adoption, not a full reimplementation of a Stargazer-style asset system.

## Migration Path

The intended migration path from raw `File`/`Dir` usage to typed assets is:

1. Keep existing working tasks and workflows unchanged.
2. Use typed assets in planning, binding, docs, and future task design.
3. Introduce conversion helpers or wrapper layers that map dataclass path fields onto Flyte `File` and `Dir` inputs.
4. Move new task families to richer typed signatures only when the boundary is clear and behavior remains deterministic.

For this milestone, the working FastQC + Salmon pipeline remains exactly as before.

## Supported Registry Entries

The minimal registry currently describes these entities:

- tasks: `star_genome_index`, `star_align_sample`, `samtools_merge_bams`, `trinity_genome_guided_assemble`, `stringtie_assemble`, `collect_transcript_evidence_results`, `pasa_accession_extract`, `combine_trinity_fastas`, `pasa_seqclean`, `pasa_create_sqlite_db`, `pasa_align_assemble`, `collect_pasa_results`, `transdecoder_train_from_pasa`, `collect_transdecoder_results`, `salmon_index`, `fastqc`, `salmon_quant`, `collect_results`
- workflows: `transcript_evidence_generation`, `pasa_transcript_alignment`, `transdecoder_from_pasa`, `rnaseq_qc_quant`

Each registry entry includes:

- `name`
- `category`
- `description`
- `inputs`
- `outputs`
- `tags`

Example inspection:

```bash
./flytetest/bin/python - <<'PY'
import sys
sys.path.insert(0, "src")
from flytetest.registry import list_entries

for entry in list_entries():
    print(entry.to_dict())
PY
```

## Local Run

1. Create or activate a Python environment and install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the existing workflow entrypoint locally:

```bash
flyte run --local flyte_rnaseq_workflow.py rnaseq_qc_quant \
  --ref data/transcriptome.fa \
  --left data/reads_1.fq.gz \
  --right data/reads_2.fq.gz
```

This preserves the current runnable behavior while the implementation lives under `src/flytetest/`.

## Transcript Evidence Workflow

The repo now includes a first transcript-evidence workflow:

```bash
flyte run --local flyte_rnaseq_workflow.py transcript_evidence_generation \
  --genome /path/to/genome.fa \
  --left /path/to/reads_1.fq.gz \
  --right /path/to/reads_2.fq.gz \
  --sample-id sampleA
```

The task graph is:

1. `star_genome_index`
2. `star_align_sample`
3. `samtools_merge_bams`
4. `trinity_genome_guided_assemble`
5. `stringtie_assemble`
6. `collect_transcript_evidence_results`

Expected results bundle contents:

- `star_index/`: STAR genome index directory
- `star_alignment/`: STAR alignment directory with sorted BAM and logs
- `merged_bam/`: merged BAM stage output
- `trinity_gg/`: genome-guided Trinity output directory, including the assembled transcript FASTA
- `stringtie/`: StringTie output directory, including `transcripts.gtf` and `gene_abund.tab`
- `run_manifest.json`: structured manifest including typed transcript-evidence asset summaries

Current simplifications from the original notes:

- this first implementation accepts one paired-end read set
- the BAM merge stage currently merges a single STAR-produced BAM so the stage boundary remains explicit for future multi-sample support
- the workflow always builds a fresh STAR index instead of reusing a prebuilt one
- gzip-compressed FASTQs are handled by adding `--readFilesCommand zcat` when both mates end in `.gz`
- genome-guided Trinity output FASTA discovery is based on common Trinity output filenames inside the Trinity output directory

Runtime/tooling notes:

- native local execution requires `STAR`, `samtools`, `Trinity`, and `stringtie` to be installed
- optional container paths are supported through `star_sif`, `samtools_sif`, `trinity_sif`, and `stringtie_sif`
- the included Dockerfile is still oriented around the existing FastQC + Salmon workflow and does not yet provision the full transcript-evidence toolchain

## PASA Transcript Alignment Workflow

The repo now includes a PASA transcript-preparation and align/assemble workflow:

```bash
flyte run --local flyte_rnaseq_workflow.py pasa_transcript_alignment \
  --genome /path/to/genome.fa \
  --transcript-evidence-results /path/to/results/transcript_evidence_results_YYYYMMDD_HHMMSS \
  --univec-fasta /path/to/UniVec.txt \
  --pasa-config-template /path/to/pasa.alignAssembly.TEMPLATE.txt
```

Transcript evidence inputs consumed by this workflow:

- `trinity_gg/Trinity-GG.fasta` from the transcript-evidence results bundle
- `stringtie/transcripts.gtf` from the transcript-evidence results bundle
- optionally, an external de novo Trinity FASTA via `--trinity-denovo-fasta-path`

The task graph is:

1. `combine_trinity_fastas`
2. `pasa_accession_extract` when a de novo Trinity FASTA is provided
3. `pasa_seqclean`
4. `pasa_create_sqlite_db`
5. `pasa_align_assemble`
6. `collect_pasa_results`

Expected results bundle contents:

- `combined_trinity/`: concatenated Trinity transcript FASTA used as PASA input
- `accessions/`: `tdn.accs` when a de novo Trinity FASTA is supplied
- `seqclean/`: PASA `seqclean` outputs, including `trinity_transcripts.fa.clean`
- `config/`: SQLite database plus the rewritten `pasa.alignAssembly.config`
- `pasa/`: PASA align/assemble outputs such as assemblies and alignment products
- `run_manifest.json`: structured manifest including typed PASA asset summaries

Pipeline-faithful notes from the attached document:

- the notes describe PASA preparation as accession extraction, concatenation of de novo and genome-guided Trinity FASTAs, `seqclean`, SQLite-backed config editing, and `Launch_PASA_pipeline.pl`
- the PASA invocation in this repo mirrors the note flags for aligners, max intron length, `--create`, `--run`, `--ALT_SPLICE`, `--CPU`, `--stringent_alignment_overlap 30.0`, and `-T`
- `StringTie` evidence is passed through `--trans_gtf`
- the PASA template config must be supplied from a PASA installation because the full config content is environment-specific in the notes

Current simplifications and assumptions:

- FLyteTest does not yet generate de novo Trinity transcripts, so `--trinity-denovo-fasta-path` is optional and external for now
- when no de novo Trinity FASTA is provided, the workflow combines only the Trinity-GG FASTA and omits `--TDN`; this is a documented simplification, not a claim that the notes omit de novo Trinity
- the SQLite file is created locally with Python's `sqlite3` library, but the workflow still expects PASA to use a SQLite-backed config as described in the notes
- this milestone stops at PASA align/assemble; downstream TransDecoder is now implemented separately, while Exonerate, BRAKER3, and EVM remain future milestones

Runtime/tooling notes:

- native local execution requires `seqclean`, `accession_extractor.pl`, and `Launch_PASA_pipeline.pl`, plus PASA's external aligner/runtime dependencies
- optional container execution is supported through `pasa_sif`
- the PASA notes explicitly call out SQLite or MySQL, samtools, BioPerl, minimap2, BLAT, and gmap as real external dependencies

## TransDecoder Workflow

The repo now includes a TransDecoder coding-prediction workflow that consumes the PASA results bundle:

```bash
flyte run --local flyte_rnaseq_workflow.py transdecoder_from_pasa \
  --pasa-results /path/to/results/pasa_results_YYYYMMDD_HHMMSS
```

Inputs consumed by this workflow:

- `pasa/<db>.assemblies.fasta` from the PASA results bundle
- `pasa/<db>.pasa_assemblies.gff3` or `pasa/<db>.assemblies.gff3` from the PASA results bundle
- `config/<db>.sqlite` or equivalent SQLite filename to recover the PASA database stem

The task graph is:

1. `transdecoder_train_from_pasa`
2. `collect_transdecoder_results`

Expected results bundle contents:

- `transdecoder/`: staged PASA assemblies plus TransDecoder outputs
- `run_manifest.json`: structured manifest including a typed TransDecoder asset summary and the resolved PASA source inputs

Expected TransDecoder outputs inside `transdecoder/` include:

- `<assemblies>.transdecoder_dir/`: intermediate directory created by `TransDecoder.LongOrfs`
- `<assemblies>.transdecoder.gff3`: transcript-level coding predictions
- `<assemblies>.transdecoder.genome.gff3`: genome-coordinate coding predictions for later EVM input
- `<assemblies>.transdecoder.cds`: predicted coding sequences
- `<assemblies>.transdecoder.pep`: predicted peptide sequences
- `<assemblies>.transdecoder.mRNA`: predicted transcript sequences
- `<assemblies>.transdecoder.bed`: transcript-coordinate BED output when emitted by TransDecoder

Current simplifications and assumptions:

- the design notes specify the desired PASA-derived TransDecoder genome GFF3, but they do not spell out the exact TransDecoder command sequence
- this implementation therefore infers a standard `TransDecoder.LongOrfs` followed by `TransDecoder.Predict`
- genome-coordinate ORF lifting is performed with `cdna_alignment_orf_to_genome_orf.pl` by default; if your environment uses a different script location, pass `--transdecoder-genome-orf-script`
- this milestone stops at coding-region prediction and does not yet implement Exonerate, BRAKER3 normalization/integration, EVM, PASA update rounds, repeat filtering, BUSCO, EggNOG, AGAT, or submission-prep

Runtime/tooling notes:

- native local execution requires `TransDecoder.LongOrfs`, `TransDecoder.Predict`, and the genome-lift helper script to be installed and callable
- optional container execution is supported through `transdecoder_sif`

## Outputs

The workflow still materializes a timestamped `results/rnaseq_results_<timestamp>/` directory containing:

- `qc/`
- `quant/`
- `run_manifest.json`

The manifest format is preserved:

- `workflow`
- `outputs.qc_dir`
- `outputs.quant_dir`
- `outputs.salmon_quant_file`
- `qc_files`
- `quant_files`

## HPC + Container Support

Implemented workflows support optional Apptainer/Singularity execution through stage-specific image arguments:

- `fastqc_sif`
- `salmon_sif`
- `star_sif`
- `samtools_sif`
- `trinity_sif`
- `stringtie_sif`
- `pasa_sif`
- `transdecoder_sif`

If these are empty, native binaries are used. If provided, tasks use either `apptainer exec` or `singularity exec`, with deterministic bind mounts for the relevant input and output parent directories.

Example:

```bash
flyte run --local flyte_rnaseq_workflow.py rnaseq_qc_quant \
  --ref /path/to/project/data/transcriptome.fa \
  --left /path/to/project/data/reads_1.fq.gz \
  --right /path/to/project/data/reads_2.fq.gz \
  --salmon_sif /path/to/containers/salmon.sif \
  --fastqc_sif /path/to/containers/fastqc.sif
```

## Assumptions

- The current SDK in this repo is `flyte==2.0.10`, and `TaskEnvironment` exposes `@env.task` but not `@env.workflow`.
- To preserve runnable behavior without introducing packaging metadata changes, `flyte_rnaseq_workflow.py` is kept as a thin compatibility module that imports the code from `src/flytetest/`.
- The new `types/` package is a local modeling layer for staged adoption and is not a full Stargazer asset platform.
- The `docs/tool_refs/` files are concise repo-local planning references, not a replacement for official tool manuals.
- Transcript evidence generation is now implemented through STAR, samtools merge, genome-guided Trinity, and StringTie for one paired-end sample.
- PASA transcript preparation and align/assemble plus downstream TransDecoder coding prediction are now implemented as separate task families and workflows, but PASA-based annotation updates, Exonerate, BRAKER3, EVM, repeat filtering, BUSCO, EggNOG, AGAT, and submission-prep remain future milestones.

# RCC Wrapper Scripts

This directory contains small, path-explicit wrappers for the RCC cluster
environment. They are intentionally thin: each script defaults to the local
repo checkout, bind-mounts it into the container at `/workspace`, and runs one
tool boundary with the same command shape used in FLyteTest.

## Assumptions

- Host project root: the repository checkout root
- Container mount path: `/workspace`
- Temporary work directory: `$PWD/temp`
- An Apptainer or Singularity runtime is available on `PATH`

The minimal smoke wrappers default their input files to the repo-local `data/`
tree, while their SIF images continue to use the shared RCC image paths unless
you override the `*_SIF` environment variables.

## Scripts

- `common.sh`: shared helper functions for runtime detection, file checks, and
  `apptainer exec`
- `trinity.sh`: Trinity de novo or genome-guided assembly
- `star.sh`: STAR genome index or alignment
- `stringtie.sh`: StringTie transcript assembly
- `pasa.sh`: PASA `seqclean` or align/assemble
- `hello_from_slurm.sbatch`: minimal Slurm submission that prints
  `hello from slurm`
- `run_hello_from_slurm.sh`: convenience launcher that creates the output
  directory and submits the hello-world Slurm job
- `check_minimal_fixtures.sh`: verifies the lightweight tutorial-backed
  fixture set is present under `data/`
- `minimal_transcriptomics_smoke.sh`: runs Trinity, STAR, and StringTie against
  the minimal local fixtures
- `minimal_transcriptomics_smoke.sbatch`: Slurm wrapper for the transcriptomics
  smoke runner
- `run_minimal_transcriptomics_smoke.sh`: convenience launcher that creates the
  output directory and submits the transcriptomics smoke job
- `minimal_pasa_smoke.sh`: reuses the Trinity smoke FASTA and runs PASA
  `seqclean` plus `accession_extract`
- `check_minimal_pasa_smoke.sh`: verifies the Trinity-to-PASA smoke artifacts
  are present
- `minimal_pasa_smoke.sbatch`: Slurm wrapper for the PASA prep smoke runner
- `run_minimal_pasa_smoke.sh`: convenience launcher that creates the output
  directory and submits the PASA prep smoke job
- `download_minimal_fixtures.sh`: restores the small tutorial-backed smoke
  fixtures into `data/`

## Examples

Run Trinity de novo:

```bash
bash scripts/rcc/trinity.sh
```

The Trinity wrapper defaults to the repo-local minimal fixture layout:

- image: `/project/rcc/hyadav/genomes/software/trinityrnaseq.v2.15.2.simg`
- host fastq directory: `data/transcriptomics/ref-based/`
- container fastq mount: `/workspace/data/transcriptomics/ref-based`
- host output directory: `temp/trinity_out_dir`
- container output mount: `/tmp/trinity_out_dir`
- mode: `denovo`

The wrapper auto-discovers `*1.fastq.gz` and `*2.fastq.gz` files from the host
fastq directory when `LEFT_FASTQ` and `RIGHT_FASTQ` are not provided.

For genome-guided Trinity, the wrapper defaults to:

- merged BAM: `data/braker3/rnaseq/RNAseq.bam`
- output directory: `temp/trinity_gg`
- container output directory: `/tmp/trinity_gg`
- CPU count: `4`
- memory: `8G`
- max intron: `100000`

If you override `OUT_DIR`, also override `CONTAINER_OUT_DIR` so the host mount
and container output path stay aligned.

Run STAR indexing:

```bash
bash scripts/rcc/star.sh
```

The STAR wrapper defaults to the repo-local minimal fixture layout:

- image: `/project/rcc/hyadav/genomes/software/STAR.sif`
- genome FASTA: `data/braker3/reference/genome.fa`
- genome index: `temp/star_index` on the host, `/tmp/star_index` inside the container
- default read pair for alignment: `data/transcriptomics/ref-based/reads_1.fq.gz`
  and `data/transcriptomics/ref-based/reads_2.fq.gz`
- CPU count: `4`

Run StringTie:

```bash
bash scripts/rcc/stringtie.sh
```

The StringTie wrapper defaults to the repo-local minimal fixture layout:

- image: `/project/rcc/hyadav/genomes/software/StringTie.sif`
- input BAM: `data/braker3/rnaseq/RNAseq.bam`
- output GTF: `temp/stringtie/stringtie_yeast.gtf`
- abundance table:
  `temp/stringtie/stringtie_yeast_abundances.txt`

Run PASA seqclean:

```bash
PASA_SIF=/project/rcc/hyadav/genomes/software/PASA.sif \
bash scripts/rcc/pasa.sh
```

The PASA wrapper defaults to the RCC script layout:

- image: `/project/rcc/hyadav/genomes/software/PASA.sif`
- work directory: `/project/rcc/hyadav/genomes/transcript_data/pasa`
- untrimmed transcripts: `/project/rcc/hyadav/genomes/transcript_data/pasa/trinity_transcripts.fa`
- cleaned transcripts: `/project/rcc/hyadav/genomes/transcript_data/pasa/trinity_transcripts.fa.clean`
- UniVec path: `/project/rcc/hyadav/genomes/scripts/RCC/PASA/UniVec`
- PASA config: `/project/rcc/hyadav/genomes/transcript_data/pasa/sqlite.confs/alignAssembly.config`
- genome FASTA: `/project/rcc/hyadav/genomes/transcript_data/yeast_genome/Scer_genome.fa`
- StringTie GTF: `/project/rcc/hyadav/genomes/transcript_data/stringtie/stringtie_yeast.gtf`
- TDN accession file: `/project/rcc/hyadav/genomes/transcript_data/pasa/tdn.accs`

The wrapper supports:

- `MODE=seqclean`
- `MODE=accession_extract`
- `MODE=align_assemble`

Submit the hello-world Slurm smoke job:

```bash
bash scripts/rcc/run_hello_from_slurm.sh
```

Run the transcriptomics smoke suite:

```bash
bash scripts/rcc/run_minimal_transcriptomics_smoke.sh
```

Run the PASA prep smoke suite:

```bash
bash scripts/rcc/check_minimal_pasa_smoke.sh
bash scripts/rcc/run_minimal_pasa_smoke.sh
```

Restore the minimal tutorial-backed fixtures:

```bash
bash scripts/rcc/download_minimal_fixtures.sh
```

That helper downloads the current lightweight inputs used for local smoke
tests and cluster validation:

- Trinity / STAR reads:
  - `data/transcriptomics/ref-based/reads_1.fq.gz`
  - `data/transcriptomics/ref-based/reads_2.fq.gz`
- legacy transcriptome example:
  - `data/transcriptomics/ref-based/transcriptome.fa`
- Braker3-derived genome / RNA-seq / proteins:
  - `data/braker3/reference/genome.fa`
  - `data/braker3/rnaseq/RNAseq.bam`
  - `data/braker3/protein_data/fastas/proteins.fa`
  - `data/braker3/protein_data/fastas/proteins_extra.fa`

The PASA prep smoke is intentionally left out of the download helper because it
reuses the Trinity FASTA emitted by the transcriptomics smoke and the existing
cluster PASA `UniVec` path.

## Notes

- The Slurm smoke job writes stdout and stderr under
  `/scratch/midway3/mehta5/flyteTest/FlyteTest/`.
- If your checkout stores the SIF files somewhere else, override the
  corresponding `*_SIF` environment variable before running the wrapper.
- The PASA wrapper treats the script-defined host files as the source of truth.
  It does not guess container paths beyond the documented bind mount.
- The PASA prep smoke stages `temp/minimal_transcriptomics_smoke/trinity/
  trinity_out_dir/Trinity.fasta` into its own smoke workspace before running
  `seqclean` and `accession_extract`. When present, it also copies the matching
  `Trinity.fasta.gene_trans_map` provenance file into the PASA workspace.
- The PASA smoke checker verifies the Trinity FASTA, the seqclean `.clean`
  output, the extracted `tdn.accs` file, and the staged gene-transcript map
  when one exists.

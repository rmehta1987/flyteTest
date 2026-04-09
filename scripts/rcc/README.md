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
tree. For images, the cluster wrappers keep using the shared RCC
`/project/rcc/hyadav/genomes` paths for Trinity and STAR, use the shared
StringTie binary at `/project/rcc/hyadav/genomes/software/stringtie/stringtie`,
and scp the PASA image to the cluster and point `PASA_SIF` at it explicitly.
The local smoke scripts can still use `data/images/*.sif`.

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
- `run_protein_evidence_slurm.sh`: prepares and submits the protein-evidence
  FLyteTest recipe with cluster defaults for the Slurm account, partition,
  walltime, CPU, and memory
- `monitor_protein_evidence_slurm.sh`: reconciles the latest protein-evidence
  Slurm run record, or a run record path that you pass explicitly
- `cancel_protein_evidence_slurm.sh`: requests cancellation for the latest
  protein-evidence Slurm run record, or a run record path that you pass
  explicitly
- `check_minimal_fixtures.sh`: verifies the lightweight tutorial-backed
  fixture set is present under `data/`
- `minimal_transcriptomics_smoke.sh`: runs Trinity, STAR, and StringTie against
  the minimal local fixtures
- `minimal_transcriptomics_smoke.sbatch`: Slurm wrapper for the transcriptomics
  smoke runner
- `run_minimal_transcriptomics_smoke.sh`: convenience launcher that creates the
  output directory and submits the transcriptomics smoke job
- `minimal_pasa_align_smoke.sh`: wiki-shaped PASA align/assemble smoke that
  reuses the Trinity smoke FASTA and the genome fixture on the host-installed
  PASA pipeline
- `check_minimal_pasa_align_smoke.sh`: verifies the wiki-shaped PASA
  align/assemble smoke artifacts are present
- `minimal_pasa_align_smoke.sbatch`: Slurm wrapper for the PASA align/assemble
  smoke runner
- `run_minimal_pasa_align_smoke.sh`: convenience launcher that creates the
  output directory and submits the PASA align/assemble smoke job
- `minimal_pasa_image_smoke.sh`: Apptainer-backed PASA image smoke that
  exercises the local `data/images/pasa_2.5.3.sif` image
- `check_minimal_pasa_image_smoke.sh`: verifies the PASA image smoke artifacts
  are present
- `minimal_pasa_image_smoke.sbatch`: Slurm wrapper for the PASA image smoke
  runner
- `run_minimal_pasa_image_smoke.sh`: convenience launcher that creates the
  output directory and submits the PASA image smoke job
- `download_minimal_fixtures.sh`: restores the small tutorial-backed smoke
  fixtures into `data/`
- `download_minimal_images.sh`: restores the small smoke images into
  `data/images/`
- `check_minimal_images.sh`: verifies the smoke images are present under
  `data/images/` and also checks the shared cluster Trinity/STAR defaults plus
  the StringTie binary under `/project/rcc/hyadav/genomes/software` when
  available
- `build_pasa_image.sh`: builds a PASA image that adds legacy BLAST support
  from the local
  [containers/pasa/Dockerfile](/home/rmeht/Projects/flyteTest/containers/pasa/Dockerfile),
  then exports it to a SIF with Apptainer when available

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

- binary: `/project/rcc/hyadav/genomes/software/stringtie/stringtie`
- input BAM: `data/braker3/rnaseq/RNAseq.bam`
- output GTF: `temp/stringtie/stringtie_yeast.gtf`
- abundance table:
  `temp/stringtie/stringtie_yeast_abundances.txt`

Run the wiki-shaped PASA align/assemble smoke:

```bash
bash scripts/rcc/check_minimal_pasa_align_smoke.sh
bash scripts/rcc/run_minimal_pasa_align_smoke.sh
```

The wiki-shaped PASA smoke defaults to the repo-local fixture layout:

- work directory: `temp/minimal_pasa_align_smoke/pasa`
- Trinity FASTA: `temp/minimal_transcriptomics_smoke/trinity/trinity_out_dir.Trinity.fasta`
- genome FASTA: `data/braker3/reference/genome.fa`
- PASA config: `temp/minimal_pasa_align_smoke/pasa/config/pasa.alignAssembly.config`
- host PASA entrypoint: `Launch_PASA_pipeline.pl`
- host aligners: `blat,gmap` when `pblat` is available, otherwise `gmap`

Run the Apptainer-backed PASA image smoke:

```bash
bash scripts/rcc/check_minimal_pasa_image_smoke.sh
bash scripts/rcc/run_minimal_pasa_image_smoke.sh
```

The Apptainer-backed PASA smoke uses the same Trinity FASTA and genome
fixture pair as the host smoke, but runs inside the repo-local image-backed
fixture layout:

- image: `data/images/pasa_2.5.3.sif`
- work directory: `temp/minimal_pasa_image_smoke/pasa`
- Trinity FASTA: `temp/minimal_transcriptomics_smoke/trinity/trinity_out_dir.Trinity.fasta`
- genome FASTA: `data/braker3/reference/genome.fa`
- PASA config: `temp/minimal_pasa_image_smoke/pasa/config/alignAssembly.conf`
- container PASA entrypoint: `/usr/local/src/PASApipeline/Launch_PASA_pipeline.pl`
- The PASA Apptainer image smoke does not currently support the legacy
  `seqclean` path; see
  https://github.com/PASApipeline/PASApipeline/issues/73.

Submit the hello-world Slurm smoke job:

```bash
bash scripts/rcc/run_hello_from_slurm.sh
```

Run the protein-evidence Slurm lifecycle smoke from the top:

```bash
bash scripts/rcc/run_protein_evidence_slurm.sh
bash scripts/rcc/monitor_protein_evidence_slurm.sh
```

The protein-evidence launcher freezes the Slurm recipe with the cluster
defaults used by this repo:

- account: `rcc-staff` unless `FLYTETEST_SLURM_ACCOUNT` is already set
- partition: `caslake` unless `FLYTETEST_SLURM_QUEUE` is already set
- walltime: `02:00:00` unless `FLYTETEST_SLURM_WALLTIME` is already set
- CPU count: `8` unless `FLYTETEST_SLURM_CPU` is already set
- memory: `32Gi` unless `FLYTETEST_SLURM_MEMORY` is already set

The submit helper writes the latest durable run-record path to
`.runtime/runs/latest_protein_evidence_slurm_run_record.txt` and the matching
saved recipe artifact path to
`.runtime/runs/latest_protein_evidence_slurm_artifact.txt` so the monitor and
cancel helpers can follow the run without manual copy/paste.
When the cluster module system is available, the helper loads
`python/3.11.9` and then activates `.venv/` if it exists in the checkout.
The generated Slurm payload does the same bootstrap on the compute node before
invoking the frozen recipe.

Run the transcriptomics smoke suite:

```bash
bash scripts/rcc/run_minimal_transcriptomics_smoke.sh
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

The wiki-shaped align/assemble smoke reuses the Trinity FASTA emitted by the
transcriptomics smoke, stages it under its original basename, and runs the
host-installed `Launch_PASA_pipeline.pl` directly with the genome FASTA and a
minimal SQLite config.

Restore the minimal smoke images:

```bash
bash scripts/rcc/download_minimal_images.sh
```

That helper downloads:

- `data/images/trinity_2.13.2.sif`
- `data/images/star_2.7.10b.sif`
- `data/images/stringtie_2.2.3.sif`
- `data/images/pasa_2.5.3.sif`

The repo-local `data/images/braker3.sif` and `data/images/busco_v6.0.0_cv1.sif`
images are managed separately when those stages are needed.

Image provenance:

- `data/images/trinity_2.13.2.sif` was pulled from `docker://quay.io/biocontainers/trinity:2.13.2--h15cb65e_2`
- `data/images/star_2.7.10b.sif` was pulled from `docker://quay.io/biocontainers/star:2.7.10b--h9ee0642_0`
- `data/images/stringtie_2.2.3.sif` was pulled from `docker://quay.io/biocontainers/stringtie:2.2.3--h43eeafb_0`
- `data/images/pasa_2.5.3.sif` was pulled from `docker://pasapipeline/pasapipeline:2.5.3`
- `data/images/braker3.sif` was built from `teambraker/braker3:latest`
- `data/images/busco_v6.0.0_cv1.sif` was built from `ezlabgva/busco:v6.0.0_cv1`

## Notes

- The Slurm smoke job writes stdout and stderr under
  `/scratch/midway3/mehta5/flyteTest/FlyteTest/` using filenames that include
  the job name and job id, such as `minimal-transcriptomics-smoke.<jobid>.out`.
- If your checkout stores the SIF files somewhere else, override the
  corresponding `*_SIF` environment variable before running the wrapper.
- The wiki-shaped PASA host smoke stages the Trinity FASTA emitted by the
  transcriptomics smoke under its original basename, writes a minimal SQLite
  config, and runs `Launch_PASA_pipeline.pl` directly with the genome FASTA.
- The Apptainer-backed PASA image smoke uses the same Trinity FASTA, writes a
  matching config, and runs `Launch_PASA_pipeline.pl` from
  `data/images/pasa_2.5.3.sif`.
- The `run_minimal_*_smoke.sh` launchers submit with `sbatch` when it is
  available and fall back to running the local smoke script directly when they
  are on a machine without Slurm.
- The Slurm smoke wrappers load `gcc/13.2.0` and `apptainer/1.4.1` before
  running the corresponding smoke scripts.
- The wiki-shaped smoke checker verifies the staged Trinity FASTA, the staged
  genome FASTA, the config, and the PASA assemblies GFF3, FASTA, and GTF
  outputs produced by the align run.
- For upstream PASA context, the repo also links the generated PASA docs index
  at `https://raw.githubusercontent.com/PASApipeline/PASApipeline/refs/heads/master/docs/index.asciidoc`.

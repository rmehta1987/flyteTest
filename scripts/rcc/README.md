# RCC Wrapper Scripts

This directory contains small, path-explicit wrappers for the RCC cluster
environment. They are intentionally thin: each script defaults to the local
repo checkout, bind-mounts it into the container at `/workspace`, and runs one
tool boundary with the same command shape used in FLyteTest.

## Assumptions

- Host project root: the repository checkout root
- Container mount path: `/workspace`
- Smoke output root: repo-local `results/`
- Container scratch mount: `/tmp` inside the image, backed by a repo-local
  `results/.../runtime` or stage-specific output directory on the host
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
- `run_protein_evidence_slurm.py`: Python helper called by the submit wrapper;
  it freezes the recipe, submits it, updates the latest pointer files, and
  prints the structured JSON submission summary
- `monitor_protein_evidence_slurm.sh`: reconciles the latest protein-evidence
  Slurm run record, or a run record path that you pass explicitly
- `monitor_protein_evidence_slurm.py`: Python helper called by the monitor
  wrapper; it loads one durable run record, reconciles scheduler state, and
  prints the structured JSON monitor summary
- `cancel_protein_evidence_slurm.sh`: requests cancellation for the latest
  protein-evidence Slurm run record, or a run record path that you pass
  explicitly
- `cancel_protein_evidence_slurm.py`: Python helper called by the cancel
  wrapper; it loads one durable run record, requests cancellation, and prints
  the structured JSON cancellation summary
- `run_m18_slurm_recipe.sh`: prepares and submits the Milestone 18 BUSCO
  fixture Slurm recipe with RCC defaults for account, `caslake` partition,
  walltime, CPU, memory, genome fixture, lineage, mode, and image discovery
- `run_m18_hpc_smoke.sh`: one-command Milestone 18 HPC smoke; stages the BUSCO
  GitLab eukaryota fixture, optionally submits the BUSCO image smoke, submits
  the M18 Slurm recipe, creates the synthetic retryable record, and submits the
  retry child
- `m18_prepare_slurm_recipe.py`: prepares a small Slurm-profile BUSCO
  genome-fixture recipe from `data/busco/test_data/eukaryota/genome.fna` for
  Milestone 18 retry testing
- `m18_submit_slurm_recipe.py`: submits the frozen Milestone 18 smoke recipe
  and updates `.runtime/runs/latest_m18_slurm_run_record.txt`
- `monitor_m18_slurm_job.sh`: reconciles the latest Milestone 18 Slurm run
  record, or a run record path that you pass explicitly
- `m18_monitor_slurm_job.py`: reconciles a Milestone 18 Slurm run record path
  passed explicitly
- `make_m18_retry_smoke_record.sh`: creates a synthetic retryable copy of the
  latest Milestone 18 Slurm run record, or a run record path passed explicitly
- `m18_make_retry_smoke_record.py`: copies a Slurm run-record directory and
  marks the copy as a retryable synthetic scheduler failure so the real
  original record is not mutated for retry testing
- `retry_m18_slurm_job.sh`: retries the latest synthetic Milestone 18 run
  record, or a retryable run record path that you pass explicitly
- `m18_retry_slurm_job.py`: retries the synthetic Milestone 18 run record and
  updates `.runtime/runs/latest_m18_retry_child_run_record.txt`
- `debug_protein_evidence_workflow.sbatch`: runs the protein-evidence workflow
  probe directly under Slurm and prints a full JSON traceback if the workflow
  fails
- `debug_protein_evidence_chunk_align.sbatch`: stages and chunks the protein
  FASTA, then calls the underlying Exonerate chunk-alignment Python callable
  directly so the real exception is visible in the Slurm output; set
  `EXONERATE_SIF` if the cluster does not provide a native `exonerate`
  binary
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
- `download_minimal_busco_fixture.sh`: stages the upstream BUSCO eukaryota
  `genome.fna` test fixture from GitLab under `data/busco/test_data/eukaryota/`
- `download_minimal_repeatmasker_fixture.sh`: stages the GTN RepeatMasker
  tutorial genome and Mucor mucedo repeat-library fixtures from Zenodo under
  `data/repeatmasker/`
- `minimal_busco_image_smoke.sh`: Apptainer-backed BUSCO image smoke that runs
  the upstream eukaryota genome test command against the BUSCO image
- `check_minimal_busco_image_smoke.sh`: verifies the BUSCO image smoke emitted
  a short summary with BUSCO completeness notation
- `minimal_busco_image_smoke.sbatch`: Slurm wrapper for the BUSCO image smoke
  runner
- `run_minimal_busco_image_smoke.sh`: convenience launcher that stages the
  upstream BUSCO test FASTA, creates the Slurm output directory, and submits
  the BUSCO image smoke job
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
- host output directory: `results/rcc_trinity/trinity_out_dir`
- container output mount: `/tmp/trinity_out_dir`
- mode: `denovo`

The wrapper auto-discovers `*1.fastq.gz` and `*2.fastq.gz` files from the host
fastq directory when `LEFT_FASTQ` and `RIGHT_FASTQ` are not provided.

For genome-guided Trinity, the wrapper defaults to:

- merged BAM: `data/braker3/rnaseq/RNAseq.bam`
- output directory: `results/rcc_trinity/trinity_gg`
- container output directory: `/tmp/trinity_gg`
- CPU count: `4`
- memory: `8G`
- max intron: `100000`

If you override `OUT_DIR`, prefer a repo-local path under `results/`. Also
override `CONTAINER_OUT_DIR` so the host mount and container output path stay
aligned.

Run STAR indexing:

```bash
bash scripts/rcc/star.sh
```

The STAR wrapper defaults to the repo-local minimal fixture layout:

- image: `/project/rcc/hyadav/genomes/software/STAR.sif`
- genome FASTA: `data/braker3/reference/genome.fa`
- genome index: `results/rcc_star/star_index` on the host, `/tmp/star_index`
  inside the container
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
- output GTF: `results/rcc_stringtie/stringtie/stringtie_yeast.gtf`
- abundance table:
  `results/rcc_stringtie/stringtie/stringtie_yeast_abundances.txt`

Run the wiki-shaped PASA align/assemble smoke:

```bash
bash scripts/rcc/check_minimal_pasa_align_smoke.sh
bash scripts/rcc/run_minimal_pasa_align_smoke.sh
```

The wiki-shaped PASA smoke defaults to the repo-local fixture layout:

- work directory: `results/minimal_pasa_align_smoke/pasa`
- Trinity FASTA:
  `results/minimal_transcriptomics_smoke/trinity/trinity_out_dir.Trinity.fasta`
- genome FASTA: `data/braker3/reference/genome.fa`
- PASA config:
  `results/minimal_pasa_align_smoke/pasa/config/pasa.alignAssembly.config`
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
- work directory: `results/minimal_pasa_image_smoke/pasa`
- Trinity FASTA:
  `results/minimal_transcriptomics_smoke/trinity/trinity_out_dir.Trinity.fasta`
- genome FASTA: `data/braker3/reference/genome.fa`
- PASA config:
  `results/minimal_pasa_image_smoke/pasa/config/alignAssembly.conf`
- container PASA entrypoint: `/usr/local/src/PASApipeline/Launch_PASA_pipeline.pl`
- The PASA Apptainer image smoke does not currently support the legacy
  `seqclean` path; see
  https://github.com/PASApipeline/PASApipeline/issues/73.

Run the upstream BUSCO eukaryota image smoke:

```bash
export BUSCO_SIF="/scratch/midway3/mehta5/flyteTest/data/images/busco_v6.0.0_cv1.sif"
bash scripts/rcc/run_minimal_busco_image_smoke.sh
```

The launcher stages the upstream BUSCO eukaryota test genome from
`https://gitlab.com/ezlab/busco/-/raw/master/test_data/eukaryota/genome.fna?ref_type=heads`
under `data/busco/test_data/eukaryota/genome.fna` before submitting the Slurm
job, then the image smoke runs the command shape recommended by the upstream
test-data note:

```bash
busco -i genome.fna -c 8 -m geno -f --out test_eukaryota
```

The wrapper uses `BUSCO_CPU=2` by default for the RCC smoke and preserves the
same genome-mode, force-overwrite, auto-lineage, and output-name behavior. Set
`BUSCO_EXTRA_ARGS` before launching when the cluster needs additional BUSCO
flags such as a pre-staged download path or offline mode.

BUSCO smoke outputs are written under `results/minimal_busco_image_smoke/`.
The Apptainer helper still binds a container-visible `/tmp`, but that path is
backed by `results/minimal_busco_image_smoke/runtime` on the host rather than
cluster `/tmp`.

Submit the hello-world Slurm smoke job:

```bash
bash scripts/rcc/run_hello_from_slurm.sh
```

Run the protein-evidence Slurm lifecycle smoke from the top:

```bash
bash scripts/rcc/run_protein_evidence_slurm.sh
bash scripts/rcc/monitor_protein_evidence_slurm.sh
```

Both wrappers print small machine-readable JSON summaries:

- submit JSON: the saved recipe artifact path, durable run-record path, Slurm
  job ID, and the scheduler submission stdout/stderr captured by the server
- monitor JSON: the current lifecycle reconciliation result, including observed
  scheduler state, run-record updates, log paths when known, and any
  reconciliation limitations

The cancel wrapper also prints a small machine-readable JSON summary:

- cancel JSON: whether the cancellation request was accepted, which durable
  run record and scheduler job were targeted, and any cancellation limits or
  scheduler-side errors reported by the server

Run the Milestone 18 HPC smoke without pasting Python or pointer paths into the
shell:

```bash
export BUSCO_SIF="/scratch/midway3/mehta5/flyteTest/data/images/busco_v6.0.0_cv1.sif"
bash scripts/rcc/run_m18_hpc_smoke.sh
```

The wrapper sets RCC-shaped defaults, including
`FLYTETEST_SLURM_ACCOUNT=rcc-staff`, `FLYTETEST_SLURM_QUEUE=caslake`,
`FLYTETEST_SLURM_CPU=2`, `FLYTETEST_SLURM_MEMORY=8Gi`,
`FLYTETEST_SLURM_WALLTIME=00:10:00`, and
`FLYTETEST_BUSCO_GENOME_FASTA=data/busco/test_data/eukaryota/genome.fna`.
The fixture recipe also defaults to `FLYTETEST_BUSCO_MODE=geno` and
`FLYTETEST_BUSCO_LINEAGE_DATASET=auto-lineage`, which omits the BUSCO `-l`
flag to stay close to the upstream test-data command.
Override any of those environment variables before running the wrapper when
the cluster allocation, BUSCO image, or fixture path differs.

The top-level smoke does two related checks:

- It stages the upstream BUSCO eukaryota test genome under
  `data/busco/test_data/eukaryota/` and submits the BUSCO image smoke with the
  configured `BUSCO_SIF`, unless `M18_RUN_BUSCO_IMAGE_SMOKE=0`.
- It validates the Milestone 18 retry/resubmission path by submitting a frozen
  FLyteTest Slurm recipe that runs BUSCO genome mode on
  `data/busco/test_data/eukaryota/genome.fna`, copying the accepted run
  record, marking the copy with synthetic `NODE_FAIL` scheduler state, and
  submitting a retry child. This avoids waiting for a real node failure and
  does not mutate the original submission record.

Run the protein-evidence workflow probe directly on Slurm:

```bash
sbatch scripts/rcc/debug_protein_evidence_workflow.sbatch
```

Run the chunk-alignment debug probe directly on Slurm:

```bash
sbatch scripts/rcc/debug_protein_evidence_chunk_align.sbatch
```

If the cluster login or compute node does not have a native `exonerate`
binary, set `EXONERATE_SIF` to a container image that provides it before
submitting the debug job. A current BioContainers reference is
`docker://quay.io/biocontainers/exonerate:2.2.0--1`.
The helper also prefers the repo-local
`data/images/exonerate_2.2.0--1.sif` when it is present.

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
When the repo-local Exonerate image is present, the helper also freezes
`exonerate_sif=data/images/exonerate_2.2.0--1.sif` into the recipe so the
submitted workflow can use the same containerized Exonerate path proven by the
chunk-alignment debug probe.
When the cluster module system is available, the helper loads
`python/3.11.9` and then activates `.venv/` if it exists in the checkout.
The generated Slurm payload does the same bootstrap on the compute node before
invoking the frozen recipe. The wrapper and generated Slurm payload also set
`FLYTETEST_TMPDIR` and `TMPDIR` to `results/.tmp` under the checkout so Python
task tempdirs stay in the project tree.

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
- BUSCO upstream eukaryota image-smoke fixture:
  - `data/busco/test_data/eukaryota/genome.fna`
  - `data/busco/test_data/eukaryota/info.txt`
- RepeatMasker GTN tutorial fixtures:
  - `data/repeatmasker/genome_raw.fasta`
  - `data/repeatmasker/Muco_library_RM2.fasta`
  - `data/repeatmasker/Muco_library_EDTA.fasta`

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
- `data/images/exonerate_2.2.0--1.sif`

The repo-local `data/images/braker3.sif` and `data/images/busco_v6.0.0_cv1.sif`
images are managed separately when those stages are needed.

Image provenance:

- `data/images/trinity_2.13.2.sif` was pulled from `docker://quay.io/biocontainers/trinity:2.13.2--h15cb65e_2`
- `data/images/star_2.7.10b.sif` was pulled from `docker://quay.io/biocontainers/star:2.7.10b--h9ee0642_0`
- `data/images/stringtie_2.2.3.sif` was pulled from `docker://quay.io/biocontainers/stringtie:2.2.3--h43eeafb_0`
- `data/images/pasa_2.5.3.sif` was pulled from `docker://pasapipeline/pasapipeline:2.5.3`
- `data/images/exonerate_2.2.0--1.sif` was pulled from `docker://quay.io/biocontainers/exonerate:2.2.0--1`
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

# PASA

## Purpose

Align transcript assemblies to the genome, refine transcript structures, and later update gene models.

## Key Inputs

- transcript assemblies such as Trinity de novo and Trinity genome-guided outputs
- reference genome
- PASA database configuration
- host-installed PASA pipeline with `Launch_PASA_pipeline.pl` on `PATH`

## Key Outputs

- PASA transcript alignment and assembly products
- refined transcript structures
- SQLite-backed PASA database and config state for the run
- updated gene models in later refinement rounds

## Pipeline Fit

- transcript preparation and alignment after transcript evidence generation
- later used again to update consensus gene models with UTRs and alternative transcripts

## Official Documentation

- PASA wiki home: https://github.com/PASApipeline/PASApipeline/wiki
- PASA installation instructions: https://github.com/PASApipeline/PASApipeline/wiki/Pasa_installation_instructions
- PASA alignment/assembly pipeline: https://github.com/PASApipeline/PASApipeline/wiki/PASA_alignment_assembly
- PASA RNA-seq / genome-guided input notes: https://github.com/PASApipeline/PASApipeline/wiki/PASA_RNAseq
- PASA Docker and Singularity runtime notes: https://github.com/PASApipeline/PASApipeline/wiki/PASA_Docker
- Comprehensive transcriptome database notes: https://github.com/PASApipeline/PASApipeline/wiki/PASA_comprehensive_db
- Upstream PASA documentation index: https://raw.githubusercontent.com/PASApipeline/PASApipeline/refs/heads/master/docs/index.asciidoc

## Tutorial And Training References

- GTN genome annotation topic: https://training.galaxyproject.org/training-material/topics/genome-annotation/
- GTN genome annotation tutorial: https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/genome-annotation/tutorial.html
- GTN coverage is useful for the broader annotation context, but it is weak on PASA-specific align/assemble and update-round details; treat it as adjacent training, not a complete PASA guide.

## Native Command Context

- The main entrypoint is `Launch_PASA_pipeline.pl`.
- Alignment/assembly runs typically use a config file such as `alignAssembly.config`, plus genome and transcript FASTA inputs.
- Common shape: `Launch_PASA_pipeline.pl -c alignAssembly.config -C -R -g genome.fa -t transcripts.fasta --ALIGNERS gmap,minimap2`
- Transcript inputs can be Trinity de novo assemblies, genome-guided Trinity assemblies, or other transcript FASTA bundles; this repo currently stages the Trinity-derived inputs internally from the transcript-evidence bundle.
- PASA update rounds use a separate annotated-comparison config/template and an existing gene model GFF3 boundary; those config files are external inputs, not repo-internal defaults.
- The wiki-shaped PASA host smoke now runs `Launch_PASA_pipeline.pl` directly
  from the Trinity smoke FASTA and the genome FASTA. It is the best fit when
  you want to mirror the official RNA-seq / Trinity examples from the PASA
  wiki.
- The Apptainer-backed PASA image smoke uses the local
  `data/images/pasa_2.5.3.sif` image against the same Trinity FASTA and
  genome fixture pair, and follows the official Docker/Singularity command
  shape from `PASA_Docker.md`.
- The PASA Apptainer image smoke does not currently support the legacy
  `seqclean` path; see
  https://github.com/PASApipeline/PASApipeline/issues/73 for the upstream
  tracking issue.

## Apptainer Command Context

- PASA's upstream container docs are written for Docker and Singularity; Apptainer uses the same execution model, so the Singularity-style invocation is the closest local equivalent.
- Inferred shape: `apptainer exec -B /workdir:/workdir pasapipeline.sif Launch_PASA_pipeline.pl -c /workdir/alignAssembly.config -C -R -g /workdir/genome.fa -t /workdir/transcripts.fasta`
- Keep all transcript FASTA, genome FASTA, config, and database paths host-mounted and absolute so the container can read and write repo-local artifacts.
- If the runtime uses SQLite or an external MySQL service, provision that outside the container and bind the resulting database files or connection config explicitly.

## Prompt Template

```text
Use docs/tool_refs/pasa.md as the reference for the PASA stage.

Goal:
Run or refine `pasa_align_assemble` or `pasa_update_gene_models` in FLyteTest.

Inputs:
- reference genome
- Trinity transcript FASTA inputs
- StringTie transcript evidence when relevant
- PASA config/template files
- optional `pasa_sif` container image

Constraints:
- keep align/assemble and post-EVM update rounds as separate stage boundaries
- do not claim the transcript branch is fully notes-faithful if the upstream all-sample STAR/BAM path is still simplified
- record database/runtime dependencies explicitly

Deliver:
- the PASA command pattern or task/workflow change
- expected database, transcript, and updated-annotation outputs
- any assumptions inferred from the current notes-alignment state
```

## Notes And Caveats

- FLyteTest currently implements PASA as a task family with explicit setup, align/assemble, and post-EVM update stages rather than one opaque step.
- The current workflow consumes `trinity_denovo/`, `trinity_gg/`, and `stringtie/` outputs from the transcript evidence stage.
- The wiki-shaped smoke helper reuses the Trinity FASTA emitted by
  `temp/minimal_transcriptomics_smoke/trinity/`, stages it under its original
  basename, and runs `Launch_PASA_pipeline.pl` directly with the genome FASTA
  and a minimal SQLite config. The staged basename is often
  `trinity_out_dir.Trinity.fasta` or `Trinity.tmp.fasta`.
- The PASA align/assemble template config and the PASA annotCompare template/config are external, environment-specific inputs in this repo.
- The design notes explicitly mention substantial external dependencies such as SQLite or MySQL, samtools, BioPerl, minimap2, BLAT, and gmap.
- This tool reference covers the implemented PASA scope only; repeat filtering, BUSCO, EggNOG, AGAT, and `table2asn` remain downstream stages elsewhere in the annotation graph.

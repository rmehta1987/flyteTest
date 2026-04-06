# funannotate

## Purpose

Use the funannotate repeat-cleanup helpers described in the notes to identify overlap-based repeat models and repeat-blast hits that should be removed from the current annotation.

## Key Inputs

- current annotation GFF3
- current protein FASTA, typically with periods already removed
- RepeatMasker BED for overlap filtering
- local funannotate database root for repeat blasting

## Key Outputs

- clean GFF3 from the overlap-filter stage
- overlap-removal list such as `genome.repeats.to.remove.gff` or `.gff3`
- `repeat.dmnd.blast.txt`
- final repeat-filtered GFF3 after deterministic removal transforms

## Pipeline Fit

- repeat-filtering cleanup after PASA refinement and before BUSCO or functional annotation

## Official Documentation

- funannotate repository and docs: https://github.com/nextgenusfs/funannotate
- issue discussing periods in protein FASTA sequences and diamond parsing: https://github.com/nextgenusfs/funannotate/issues/459

## Tutorial References

- GTN Funannotate tutorial: https://training.galaxyproject.org/training-material/topics/genome-annotation/tutorials/funannotate/tutorial.html
- the repo-local notes remain the concrete source for the `RemoveBadModels` and `RepeatBlast` wrapper usage in this milestone

## Native Command Context

- the notes do not show a standalone funannotate CLI here; they show Python wrappers around `funannotate.library.RemoveBadModels` and `funannotate.library.RepeatBlast`
- FLyteTest therefore treats those library calls as the concrete documented boundary for this milestone and records that wrapper choice as inferred behavior
- the two downstream removal helpers stay explicit and deterministic instead of being hidden inside a larger opaque task

## Apptainer Command Context

- if funannotate is containerized locally, bind the annotation, protein, RepeatMasker BED, and database directories into the container and run the same Python-wrapper boundary there
- exact image content is environment-specific and is not defined by the notes

## Prompt Template

```text
Use docs/tool_refs/funannotate.md as the reference for the repeat-filter cleanup stage.

Goal:
Refine `funannotate_remove_bad_models`, `funannotate_repeat_blast`, or the deterministic removal transforms in `annotation_repeat_filtering`.

Inputs:
- current annotation GFF3
- current protein FASTA
- RepeatMasker BED when working on overlap filtering
- local `funannotate_db_path` when working on repeat blasting
- optional `funannotate_python`
- optional `repeat_filter_sif`

Constraints:
- keep overlap filtering, blast filtering, and final GFF3 cleanup as separate visible boundaries
- treat the Python-wrapper invocation as inferred from the notes, not as a guaranteed official CLI contract
- do not broaden into BUSCO, EggNOG, AGAT, or submission-prep

Deliver:
- the funannotate command or wrapper plan, or the task/workflow change
- expected intermediate outputs such as the overlap-removal list or `repeat.dmnd.blast.txt`
- any assumptions that still need confirmation
```

## Notes And Caveats

- The notes show inconsistent overlap-removal-list suffixes (`.gff` and `.gff3`), so FLyteTest resolves whichever file the funannotate overlap step actually emits and records that exact path.
- The final blast-hit-removal logic in this repo is a deterministic rewrite of the notes' shell helper that filters `Parent=` and `ID=` attributes and then repeats the `ID=` filter after translating `evm.model` identifiers to `evm.TU`.

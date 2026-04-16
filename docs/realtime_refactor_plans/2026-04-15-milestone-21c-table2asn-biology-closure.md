# Milestone 21c: Table2asn Biology Closure

Date: 2026-04-15
Status: Ready to implement

Related checklist milestone:
- `docs/realtime_refactor_checklist.md` Milestone 21c

Bundled items:
- TODO 1 — `table2asn`: add task, workflow, MCP handler, and ShowcaseTarget

---

## Current State

The annotation pipeline currently ends at `annotation_postprocess_agat_cleanup`
(AGAT statistics + cleanup GFF3). The AGAT tasks explicitly note that
"`table2asn` remains deferred after this cleanup slice." Table2asn is the NCBI
GenBank submission step that converts the cleaned GFF3 + masked genome FASTA
into a validated `.sqn` sequence file for submission.

The three AGAT slices in `src/flytetest/tasks/agat.py` and
`src/flytetest/workflows/agat.py` provide the direct precedent for how to add
this step.

---

## Biological Context

`table2asn` (NCBI) converts:
- A repeat-masked genome FASTA (`-i`)  
- A cleaned annotation GFF3 (`-f`)  
- An NCBI submission template (`.sbt` file) (`-t`)  
into:
- A `.sqn` sequence file for GenBank submission (`-o`)
- Optionally a validation report (`-Z`, `-V b`)

Key flags used in the reference run (`docs/braker3_evm_notes.md` line ~920):
```
table2asn -M n -J -c w -euk -t template.sbt \
  -gaps-min 10 -l proximity-ligation \
  -locus-tag-prefix ACFI09 \
  -j "[organism=...][isolate=...]" \
  -i genome.repeatmasked.fa \
  -f annotation.gff3 \
  -o output.sqn -Z -V b
```

The step runs after AGAT cleanup. It is a single-node, single-output stage.

---

## TODO 1 — table2asn Task, Workflow, and MCP Surface

### Scope

- One new task: `table2asn_submission` in `src/flytetest/tasks/agat.py`
  (natural home alongside the other AGAT/post-processing tasks).
- One new workflow: `annotation_postprocess_table2asn` in
  `src/flytetest/workflows/agat.py`.
- One new `ShowcaseTarget(category="workflow")` in `mcp_contract.py`.
- One new local node handler entry in `server.py`.
- Tests, docs, CHANGELOG.

### Constraints

- The task accepts `agat_cleanup_results: Dir` (output of `agat_cleanup_gff3`)
  plus mandatory `genome_fasta: File` and `submission_template: File` (the
  `.sbt` template), plus optional string overrides for locus tag prefix,
  organism annotation (`-j`), and `table2asn_binary: str = "table2asn"`.
- The task reads `agat_cleanup_gff3`'s output directory to locate the cleaned
  GFF3; it does not accept a raw GFF3 path directly — the stage boundary is
  the AGAT cleanup result bundle.
- The task runs `table2asn` directly (not via Apptainer/SIF) consistent with
  the notes showing Conda installation. An optional `table2asn_sif: str = ""`
  follows the same pattern as other tasks if containerisation is needed later.
- Output directory follows `TABLE2ASN_RESULTS_PREFIX` naming under `RESULTS_ROOT`.
- A `run_manifest.json` is written with standard workflow/inputs/outputs shape.
- Do NOT add `table2asn_submission` to `SUPPORTED_TASK_NAMES` (task eligibility
  list) — it runs only through the workflow surface, not the ad hoc task tool.

### New Constants Required

In `src/flytetest/config.py`:
- `TABLE2ASN_RESULTS_PREFIX = "table2asn_results"`
- `TABLE2ASN_WORKFLOW_NAME = "annotation_postprocess_table2asn"`

In `src/flytetest/mcp_contract.py`:
- `SUPPORTED_TABLE2ASN_WORKFLOW_NAME = TABLE2ASN_WORKFLOW_NAME`
- New `ShowcaseTarget(name=SUPPORTED_TABLE2ASN_WORKFLOW_NAME, category="workflow", ...)`
  appended to `SHOWCASE_TARGETS`.

### Task Signature

```python
@task(...)
def table2asn_submission(
    agat_cleanup_results: Dir,
    genome_fasta: File,
    submission_template: File,
    locus_tag_prefix: str = "",
    organism_annotation: str = "",
    table2asn_binary: str = "table2asn",
    table2asn_sif: str = "",
) -> Dir:
```

### Manifest Shape

```json
{
  "workflow": "annotation_postprocess_table2asn",
  "assumptions": [...],
  "source_bundle": {
    "agat_cleanup_results": "<path>"
  },
  "copied_source_manifests": {
    "agat_cleanup": "<path>"
  },
  "inputs": {
    "agat_cleanup_results": "<path>",
    "genome_fasta": "<path>",
    "submission_template": "<path>",
    "locus_tag_prefix": "...",
    "organism_annotation": "...",
    "table2asn_binary": "table2asn"
  },
  "outputs": {
    "sqn_file": "<path>",
    "validation_report": "<path>",
    "table2asn_output_dir": "<path>"
  }
}
```

### Workflow

`annotation_postprocess_table2asn` in `src/flytetest/workflows/agat.py`:
- Single-node workflow wrapping `table2asn_submission`.
- Registry entry in `src/flytetest/annotation.py` (or the workflow registry)
  following the exact pattern of `annotation_postprocess_agat_cleanup`.

### MCP Surface

- New `ShowcaseTarget` in `SHOWCASE_TARGETS` with `category="workflow"`.
- Local node handler in `server.py`'s `_local_node_handlers()` (inherits from
  the `SUPPORTED_TARGET_NAMES`-derived handler dict only if it is a workflow;
  otherwise add explicitly to the workflow dispatch in `run_workflow`).
- Update `SHOWCASE_LIMITATIONS` and `LIST_ENTRIES_LIMITATIONS` strings to
  mention `annotation_postprocess_table2asn`.

### Tests

Add to `tests/test_server.py` (2 tests):
- `test_run_task_does_not_expose_table2asn_as_ad_hoc_task` — confirm
  `run_task("table2asn_submission", {...})` returns `supported=False`.
- `test_list_entries_includes_table2asn_workflow` — `list_entries()` output
  includes `annotation_postprocess_table2asn` with `category="workflow"`.

Add to `tests/test_agat.py` or a new `tests/test_table2asn.py` (3 tests):
- `test_table2asn_submission_calls_binary_with_correct_flags` — mock
  `run_tool` / subprocess; verify the command shape.
- `test_table2asn_submission_writes_run_manifest` — run with a minimal fake
  output; verify `run_manifest.json` is written with the expected keys.
- `test_table2asn_submission_copies_source_boundary_files` — verify agat
  cleanup GFF3 is found and staged correctly.

---

## Acceptance Criteria

- All new tests pass; full suite stays green (≥383 tests).
- `annotation_postprocess_table2asn` appears in `list_entries()` output.
- `run_task("table2asn_submission", ...)` correctly declines.
- `docs/mcp_showcase.md`: add `annotation_postprocess_table2asn` to the
  Runnable Targets section with example call.
- `docs/capability_maturity.md`: "table2asn / NCBI submission" row updated
  to `Current (M21c)`.
- `README.md`: `annotation_postprocess_table2asn` added to the supported
  targets list.
- `docs/realtime_refactor_checklist.md`: all M21c items marked `[x]`.
- `CHANGELOG.md`: dated entries for M21c.

## Compatibility Risks

- `table2asn` binary availability: the task must degrade gracefully when the
  binary is absent (return `supported=False` limitation, not a crash).
- The AGAT cleanup output directory layout must be inspected correctly to
  locate the cleaned GFF3 — do not hardcode a filename that may change.
- Do not inadvertently add `table2asn_submission` to `SUPPORTED_TASK_NAMES`
  (the ad hoc task surface); it is a workflow-surface-only stage.
- `SERVER_RESOURCE_URIS` indices: if M21b landed before this milestone,
  indices 0–5 are taken. Do not shift any existing indices.

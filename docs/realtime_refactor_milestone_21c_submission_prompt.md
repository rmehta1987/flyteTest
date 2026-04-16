Use this prompt when handing the Milestone 21c Biology Closure slice off to
another Codex session or when starting the next implementation pass.

```text
You are continuing the FLyteTest `realtime` architecture refactor under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_checklist.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/2026-04-15-milestone-21c-table2asn-biology-closure.md
- /home/rmeht/Projects/flyteTest/docs/realtime_refactor_plans/README.md
- /home/rmeht/Projects/flyteTest/docs/braker3_evm_notes.md
- /home/rmeht/Projects/flyteTest/README.md
- /home/rmeht/Projects/flyteTest/docs/capability_maturity.md

Read the relevant repo-local guides under `.codex/` for the area you touch,
especially:

- /home/rmeht/Projects/flyteTest/.codex/documentation.md
- /home/rmeht/Projects/flyteTest/.codex/testing.md
- /home/rmeht/Projects/flyteTest/.codex/tasks.md
- /home/rmeht/Projects/flyteTest/.codex/workflows.md

Context:

- This is Milestone 21c. Milestone 21 must be complete before starting this
  work. Confirm the `## Milestone 21` section in
  `docs/realtime_refactor_checklist.md` is marked complete before proceeding.
  M21b may or may not be complete; M21c does not depend on it.
- M21c adds `table2asn_submission` task and `annotation_postprocess_table2asn`
  workflow to close out the NCBI annotation submission step that follows
  `agat_cleanup_gff3` in the biology pipeline.
- The AGAT slices in `src/flytetest/tasks/agat.py` and
  `src/flytetest/workflows/agat.py` are the direct implementation precedent.
  Read both files carefully before writing any code.
- Read `docs/braker3_evm_notes.md` around line 900 for the exact `table2asn`
  command shape used in the reference run.

Key decisions already made (do not re-litigate):

- Task name: `table2asn_submission` in `src/flytetest/tasks/agat.py`.
- Workflow name constant: `TABLE2ASN_WORKFLOW_NAME = "annotation_postprocess_table2asn"`
  in `src/flytetest/config.py`.
- Results prefix constant: `TABLE2ASN_RESULTS_PREFIX = "table2asn_results"` in
  `src/flytetest/config.py`.
- The task accepts `agat_cleanup_results: Dir` (not a raw GFF3 path) as the
  upstream boundary input, plus `genome_fasta: File`, `submission_template: File`,
  optional `locus_tag_prefix: str = ""`, `organism_annotation: str = ""`,
  `table2asn_binary: str = "table2asn"`, `table2asn_sif: str = ""`.
- `table2asn_submission` is NOT added to `SUPPORTED_TASK_NAMES` (the ad hoc task
  surface). It is workflow-surface only.
- MCP surface: new `ShowcaseTarget(category="workflow")` entry in
  `SHOWCASE_TARGETS` in `mcp_contract.py`; update `SHOWCASE_LIMITATIONS` and
  `LIST_ENTRIES_LIMITATIONS` strings.
- `SERVER_RESOURCE_URIS` indices: do not shift any existing index. If M21b
  added indices 4 and 5, append after those. If M21b has not landed, existing
  indices 0–3 are in use.

Baseline:

- Run `.venv/bin/python -m unittest 2>&1 | tail -5` before any changes.
  Baseline after M21: 381 tests, all pass (1 skipped). After M21b (if landed):
  389+ tests. Do not regress.

Task (implement in order):

Part 1 — Constants

1. In `src/flytetest/config.py`:
   - Add `TABLE2ASN_RESULTS_PREFIX = "table2asn_results"`.
   - Add `TABLE2ASN_WORKFLOW_NAME = "annotation_postprocess_table2asn"`.

2. In `src/flytetest/mcp_contract.py`:
   - Import `TABLE2ASN_WORKFLOW_NAME` from `flytetest.config`.
   - Add `SUPPORTED_TABLE2ASN_WORKFLOW_NAME = TABLE2ASN_WORKFLOW_NAME`.
   - Append a new `ShowcaseTarget(name=SUPPORTED_TABLE2ASN_WORKFLOW_NAME,
     category="workflow", ...)` to `SHOWCASE_TARGETS` following the exact
     pattern of `SUPPORTED_AGAT_CLEANUP_WORKFLOW_NAME`.
   - Update `SHOWCASE_LIMITATIONS` and `LIST_ENTRIES_LIMITATIONS` strings to
     include `annotation_postprocess_table2asn`.

Part 2 — Task

3. In `src/flytetest/tasks/agat.py`:
   - Import `TABLE2ASN_RESULTS_PREFIX` and `TABLE2ASN_WORKFLOW_NAME` from
     `flytetest.config`.
   - Add `TABLE2ASN_OUTPUT_DIRNAME = "table2asn_output"` module-level constant.
   - Implement `table2asn_submission(agat_cleanup_results, genome_fasta,
     submission_template, locus_tag_prefix="", organism_annotation="",
     table2asn_binary="table2asn", table2asn_sif="") -> Dir`.
   - Locate the cleaned GFF3 from the AGAT cleanup result dir by scanning for
     `*.gff3` in the `agat_output` subdirectory (match the actual output layout
     of `agat_cleanup_gff3`).
   - Build the `table2asn` command following the reference in
     `docs/braker3_evm_notes.md` line ~920. Include `-M n -J -c w -euk
     -gaps-min 10 -l proximity-ligation`; use `locus_tag_prefix` for
     `-locus-tag-prefix` when non-empty; use `organism_annotation` for `-j`
     when non-empty.
   - Write `run_manifest.json` with `workflow`, `assumptions`, `source_bundle`,
     `copied_source_manifests`, `inputs`, and `outputs` keys.
   - Add `"table2asn remains deferred"` notes to existing AGAT task assumptions
     can now be updated to remove the deferral note — but only if doing so is a
     trivial one-line change. Do not refactor existing task assumptions broadly.
   - Export `table2asn_submission` in `__all__`.

Part 3 — Workflow

4. In `src/flytetest/workflows/agat.py`:
   - Import `table2asn_submission` from `flytetest.tasks.agat`.
   - Import `TABLE2ASN_WORKFLOW_NAME` from `flytetest.config`.
   - Add `annotation_postprocess_table2asn` workflow following the pattern of
     `annotation_postprocess_agat_cleanup`.
   - Register the workflow in the workflow registry following the existing AGAT
     workflow registration pattern.

Part 4 — MCP surface

5. In `src/flytetest/server.py`:
   - Add a local node handler for `annotation_postprocess_table2asn` following
     the pattern of `annotation_postprocess_agat_cleanup`.
   - Verify the tool appears correctly in `list_entries()` output.

Part 5 — Tests

6. Add 2 tests to `tests/test_server.py`:
   - `test_run_task_does_not_expose_table2asn_as_ad_hoc_task` — confirm
     `run_task("table2asn_submission", {})` returns `supported=False`.
   - `test_list_entries_includes_table2asn_workflow` — confirm `list_entries()`
     output includes an entry with `name="annotation_postprocess_table2asn"`
     and `category="workflow"`.

7. Add 3 tests to `tests/test_agat.py` (or a new `tests/test_table2asn.py`
   if the test file grows too large):
   - `test_table2asn_submission_builds_correct_command` — mock `run_tool`;
     verify the command list includes the required flags.
   - `test_table2asn_submission_writes_run_manifest` — run with all-fake
     paths; verify `run_manifest.json` is written and has the expected keys.
   - `test_table2asn_submission_declines_when_gff3_not_found` — pass an
     `agat_cleanup_results` dir that contains no GFF3; verify a clear error
     is raised or returned.

Part 6 — Docs

8. Update `docs/mcp_showcase.md`: add `annotation_postprocess_table2asn` to
   the Runnable Targets section alongside the AGAT slices, with an example
   `prompt_and_run` call and the accepted input fields.

9. Update `docs/capability_maturity.md`: add a "table2asn / NCBI submission"
   row with `Current (M21c)` and a brief description.

10. Update `README.md`: add `annotation_postprocess_table2asn` to the
    supported targets list.

11. Update `docs/realtime_refactor_checklist.md`: mark all M21c checkboxes
    `[x]`, update status to `Complete (2026-04-15)` (or the actual date).

12. Update `CHANGELOG.md`: add dated entries for M21c.

Validation:

- `.venv/bin/python -m unittest tests.test_server -v 2>&1 | tail -30`
- `.venv/bin/python -m unittest 2>&1 | tail -5` — must show ≥386 tests, all pass
- `git diff --check` — no trailing whitespace
```

Use this prompt when starting Step 07 or when handing it off to another session.

```text
You are continuing the FLyteTest scientist-centered MCP surface reshape under the rules in:

- /home/rmeht/Projects/flyteTest/AGENTS.md
- /home/rmeht/Projects/flyteTest/DESIGN.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/checklist.md
- /home/rmeht/Projects/flyteTest/docs/mcp_reshape/mcp_reshape_plan.md  (§3h — recipe_id format)

Context:

- This is Step 07. Narrow format change to `recipe_id`. Breaks external code
  that regex-matched the old `<ISO-second>-<short-hash>` form. This is a
  coordinated change; Step 26 (call-site sweep) catches any hits.

Key decisions already made (do not re-litigate):

- New format: `<YYYYMMDDThhmmss.mmm>Z-<target_name>` (no hash — uniqueness is
  millisecond-resolution + serialized event loop; collision is documented as
  a negligible edge case).
- Composition-fallback DAGs use `composed-<first_stage>_to_<last_stage>` for
  the target slot.
- Filesystem layout stays `.runtime/specs/<recipe_id>.json` and
  `results/<recipe_id>/` — no second grouping layer.

BEFORE YOU BEGIN: confirm implementation detail about the current hash. Read
`src/flytetest/spec_artifacts.py::artifact_from_typed_plan`. If the old short
hash is content-addressed (same plan content → same recipe_id) AND any
existing code relies on that for dedup/caching, RETAIN the hash rather than
dropping it. If the hash is purely a uniqueness salt (expected), drop it.

Task:

1. In `src/flytetest/spec_artifacts.py::artifact_from_typed_plan`, generate
   the new recipe_id using `datetime.now(UTC).strftime("%Y%m%dT%H%M%S")` +
   `.{millis:03d}Z-` + `target_name`. Strip any characters that would be
   invalid in a filename from `target_name` (but registry names are already
   snake_case — a short sanity regex is enough).

2. Composition-fallback plans emit `target_name =
   "composed-" + "_to_".join([first_stage, last_stage])` (or just `composed`
   if either is empty).

3. If `SlurmWorkflowSpecExecutor.submit` sets `--job-name`, pass `recipe_id`
   so `sacct --format=JobName` is self-describing.

Tests to add (tests/test_spec_artifacts.py):

- Format assertion: `run_task("exonerate_align_chunk", ...)` returns a
  `recipe_id` matching `r"^\d{8}T\d{6}\.\d{3}Z-exonerate_align_chunk$"`.
  (Alternatively, a direct unit test on the id generator with a mocked
  `datetime.now`.)
- Filesystem round-trip: `.runtime/specs/<recipe_id>.json` exists after
  freeze; `load_workflow_spec_artifact(path)` returns an artifact whose
  `recipe_id` matches.
- Composition sentinel: a planner-composed novel DAG produces a recipe_id
  with the `composed-` prefix.
- Distinct mocked timestamps produce distinct ids.

Verification:

- `python -m compileall src/flytetest/spec_artifacts.py`
- `pytest tests/test_spec_artifacts.py`

Commit message: "spec_artifacts: new recipe_id format (millisecond + target_name)".

Then mark Step 07 Complete in docs/mcp_reshape/checklist.md.
```

Use this prompt when handing the Milestone 22 registry-driven pipeline tracker
slice off to another session or when starting the next implementation pass.

```text
You are continuing the FLyteTest realtime architecture refactor.

Milestone 22 goal: make the pipeline status tracker registry-driven by adding
`pipeline_family` and `pipeline_stage_order` fields to `RegistryCompatibilityMetadata`
in `src/flytetest/registry.py`, so the tracker derives stage lists from the
registry instead of maintaining a hardcoded list.

Full plan: docs/realtime_refactor_plans/2026-04-16-milestone-22-registry-driven-pipeline-tracker.md

Key changes (code only — documentation renames are already done):
1. Add `pipeline_family: str = ""` and `pipeline_stage_order: int = 0` to
   `RegistryCompatibilityMetadata` (frozen dataclass, safe defaults).
2. Populate all 17 entries in `_WORKFLOW_COMPATIBILITY_METADATA` with
   `pipeline_family="annotation"` and `pipeline_stage_order=1..15` for the 15
   annotation pipeline workflows; leave `busco_assess_proteins` and
   `rnaseq_qc_quant` with defaults.
3. Add `get_pipeline_stages(family: str) -> list[tuple[str, str]]` to
   `registry.py` — pure function, no I/O, safe at import time.
4. Replace the hardcoded `ANNOTATION_PIPELINE_STAGES` literal in
   `pipeline_tracker.py` with `get_pipeline_stages("annotation")`. Keep the
   public name; remove the now-unused config.py workflow name imports.
5. Add 3 tests to `tests/test_pipeline_tracker.py` (see plan doc for details).
6. Update `CHANGELOG.md`.

Constraints:
- Do not make any further documentation renames — those are complete.
- `RegistryCompatibilityMetadata` is a compatibility-critical surface; read
  AGENTS.md before editing it.
- `ANNOTATION_PIPELINE_STAGES` must remain a public module-level name in
  `pipeline_tracker.py` — tests import it directly.
- Run `python -m pytest tests/test_pipeline_tracker.py tests/test_server.py -v`
  before committing.
```

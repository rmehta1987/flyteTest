# Step 06 — Human-readable formatter for `StagingFinding`

## Goal

A scientist whose first `sbatch` is blocked by `check_offline_staging`
should see actionable English, not a list of dataclass dumps.

## Where

`src/flytetest/staging.py:18–24` — `StagingFinding` is the structured
record. Add a sibling helper.

## Shape

```python
def format_finding(finding: StagingFinding) -> str:
    """Render a StagingFinding as one actionable line for a human reader."""
```

Output examples (style guide — match the tone of `bundles.py:fetch_hints`):

- `not_found` → `"Container 'braker_sif' at data/images/braker3.sif: not found. Pull with `apptainer pull data/images/braker3.sif docker://teambraker/braker3:latest`."`
- `not_readable` → `"Tool database 'busco_lineage_dir' at /scratch/busco/lineages: present but not readable by the running user."`
- `not_on_shared_fs` → `"Input path 'ReferenceGenome.fasta_path' at /tmp/ref.fa: not on the compute-visible filesystem; restage to /project or /scratch."`

Hard-coded suggestion strings should only be added when the finding's
`kind` clearly maps to a fix; otherwise just describe the failure.

## Wire one caller

Pick the most user-facing caller — likely `validate_run_recipe` in
`server.py` — and have it format findings before returning. Don't change
`SlurmWorkflowSpecExecutor.submit` (that's a hard-constraint path); leave
its callers free to format on their own.

## Test

Add 3 unit tests in `tests/test_staging.py`, one per `reason` value, that
assert the formatter produces a non-empty string containing the path and
the kind.

## Acceptance

- `format_finding` is exported from `staging.py`.
- At least one MCP-surface caller uses it.
- 3 new unit tests pass alongside the existing 887.

## Commit

`critique-followup: add format_finding helper for staging preflight`

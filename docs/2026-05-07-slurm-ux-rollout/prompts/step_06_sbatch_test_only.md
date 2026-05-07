# Step 06 — sbatch --test-only integration in validate_run_recipe

## Context

Slurm has a built-in `--test-only` flag that asks the controller "would this submission be accepted?" without queuing a job. Catches things `check_offline_staging` can't: invalid partition name, account-without-membership, requested resources exceeding partition limits, qos issues. Cheap (~30s round-trip), no canary job actually runs. Wire this into `validate_run_recipe` so users discover those errors before the real sbatch.

## Files to read before editing

- `src/flytetest/staging.py` — `check_offline_staging` flow + `StagingFinding` shape
- `src/flytetest/server.py:3014` — `validate_run_recipe` MCP tool (current behavior: runs `check_offline_staging`, returns findings)
- `src/flytetest/spec_executor.py` — sbatch script generation; reuse the script writer to feed `--test-only`
- Slurm documentation on `sbatch --test-only` — the reasons it can fail

## Files to create / edit

| Action | File |
|---|---|
| Edit | `src/flytetest/staging.py` (or `src/flytetest/spec_executor.py`, depending on where the helper fits) |
| Edit | `src/flytetest/server.py` (`validate_run_recipe`) |
| Edit | `tests/test_validate_run_recipe.py` (or matching) |
| Edit | `CHANGELOG.md` |

## Implementation instructions

### Where the helper lives

`sbatch --test-only` validation belongs alongside `check_offline_staging` since it's another preflight check. Two options:

- **Option A**: New helper in `staging.py` returning `list[StagingFinding]`. Keeps all preflight in one module.
- **Option B**: Helper in `spec_executor.py` since that's where sbatch script generation lives.

**Recommended: Option A.** Keep preflight as a unified surface. Import the script writer from `spec_executor.py` if needed.

### `src/flytetest/staging.py` — new helper

```python
import subprocess
from pathlib import Path

@dataclass(frozen=True)
class SlurmTestOnlyFinding:
    kind: Literal["slurm_test_only"]
    reason: Literal[
        "partition_invalid",
        "account_unknown",
        "resources_exceed_limits",
        "qos_invalid",
        "test_only_failed",
    ]
    message: str

def check_sbatch_test_only(script_path: Path) -> list[StagingFinding]:
    """Run `sbatch --test-only` against the generated submission script.

    Returns structured findings if Slurm rejects the submission for
    pre-queue reasons (partition/account/resources/qos). Empty list
    means Slurm accepts it.

    Does NOT queue or run the job. Slurm's --test-only flag is
    designed for exactly this purpose.
    """
    if not script_path.exists():
        return [
            StagingFinding(
                kind="slurm_test_only",
                key="script_path",
                path=str(script_path),
                reason="script_missing",
                message=f"Generated sbatch script not found at {script_path}",
            )
        ]

    proc = subprocess.run(
        ["sbatch", "--test-only", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode == 0:
        return []  # Slurm would accept

    stderr = (proc.stderr or "").strip()
    reason = _classify_test_only_failure(stderr)
    return [
        StagingFinding(
            kind="slurm_test_only",
            key="sbatch_test_only",
            path=str(script_path),
            reason=reason,
            message=stderr or "sbatch --test-only returned non-zero",
        )
    ]


_REASON_PATTERNS = {
    "partition_invalid": ("invalid partition", "partition specification"),
    "account_unknown": ("invalid account", "user does not have permission"),
    "resources_exceed_limits": (
        "memorypernode",
        "time limit",
        "exceeds the limit",
        "node count",
    ),
    "qos_invalid": ("invalid qos", "qos.*does not exist"),
}

def _classify_test_only_failure(stderr: str) -> str:
    """Bucket Slurm's --test-only stderr into structured reasons."""
    lower = stderr.lower()
    for reason, patterns in _REASON_PATTERNS.items():
        if any(p in lower for p in patterns):
            return reason
    return "test_only_failed"
```

### `src/flytetest/server.py:3014` — `validate_run_recipe`

After `check_offline_staging` succeeds (or returns findings), invoke `check_sbatch_test_only` against the generated submission script. Combine findings:

```python
def validate_run_recipe(...) -> dict:
    artifact = _load_artifact(artifact_path)
    staging_findings = check_offline_staging(artifact, shared_fs_roots, execution_profile=...)

    # New: test-only sbatch check after staging passes (skip if staging
    # already failed — pointless to test sbatch when paths are missing).
    test_only_findings: list[StagingFinding] = []
    if not staging_findings and execution_profile == "slurm":
        # Generate the script (or reuse a cached one) and probe with --test-only.
        script_path = _generate_or_locate_script(artifact)
        test_only_findings = check_sbatch_test_only(script_path)

    all_findings = staging_findings + test_only_findings
    return {
        "supported": not bool(all_findings),
        "recipe_id": artifact.recipe_id,
        "execution_profile": execution_profile,
        "staging_findings": [_format_finding(f) for f in staging_findings],
        "test_only_findings": [_format_finding(f) for f in test_only_findings],
        "findings": [_format_finding(f) for f in all_findings],
    }
```

Note: `_generate_or_locate_script` may need to be a small new helper if the script is generated only at submit time today. If so, factor the script generation out of `_submit_saved_artifact` so both the validator and the submitter call the same code path.

### Tests

```python
@patch("flytetest.staging.subprocess.run")
def test_sbatch_test_only_invalid_partition(mock_run, tmp_path):
    script = tmp_path / "submit.sh"
    script.write_text("#!/bin/bash\nsleep 1\n")
    mock_run.return_value = Mock(
        returncode=1,
        stderr="sbatch: error: invalid partition specified: bogus_partition\n",
    )
    findings = check_sbatch_test_only(script)
    assert len(findings) == 1
    assert findings[0].reason == "partition_invalid"

@patch("flytetest.staging.subprocess.run")
def test_sbatch_test_only_resources_exceed(mock_run, tmp_path):
    script = tmp_path / "submit.sh"
    script.write_text("#!/bin/bash\nsleep 1\n")
    mock_run.return_value = Mock(
        returncode=1,
        stderr="sbatch: error: Memory exceeds the limit on partition caslake\n",
    )
    findings = check_sbatch_test_only(script)
    assert findings[0].reason == "resources_exceed_limits"

@patch("flytetest.staging.subprocess.run")
def test_sbatch_test_only_pass(mock_run, tmp_path):
    script = tmp_path / "submit.sh"
    script.write_text("#!/bin/bash\nsleep 1\n")
    mock_run.return_value = Mock(returncode=0, stdout="sbatch: Job 12345\n", stderr="")
    findings = check_sbatch_test_only(script)
    assert findings == []
```

## Acceptance criteria

- `validate_run_recipe(...)` calls `check_sbatch_test_only` after `check_offline_staging` succeeds for `execution_profile=="slurm"`
- Test-only failures surface as structured `StagingFinding` records with `kind: "slurm_test_only"` and a classified `reason`
- A real `sbatch --test-only` run on a valid recipe produces no findings; a typo'd partition produces one finding with `reason: "partition_invalid"`
- Tests cover the 4 reason classifications + the pass case
- Full test suite still passes

## CHANGELOG entry template

```
## Unreleased

### Slurm UX rollout — Phase 0 step 06 (2026-05-07)

- [x] 2026-05-07 `staging.py`: `check_sbatch_test_only(script_path)` runs `sbatch --test-only` and returns structured `StagingFinding` records for pre-queue rejections (`partition_invalid`, `account_unknown`, `resources_exceed_limits`, `qos_invalid`). No job is queued or run.
- [x] 2026-05-07 `server.py:3014` `validate_run_recipe`: test-only check runs after `check_offline_staging` for slurm-profile recipes; findings combined and returned alongside staging findings. Catches partition/account/qos typos and over-limit resource requests before the real sbatch attempt.
```

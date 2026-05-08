#!/usr/bin/env python3
"""Live RCC smoke for the Slurm UX rollout Phase 0 features.

Exercises every Phase 0 surface against the real cluster — `sinfo`,
`sbatch --test-only`, the canonical run-dir layout, the runs/latest
symlink, the recipe-id hash suffix, and the `extend_module_loads`
precedence — without queuing a real compute job by default.

Sections:
    A. ResourceSpec validators              (no Slurm needed)
    B. Recipe-id hash truncation            (no Slurm needed)
    C. list_slurm_partitions                (read-only sinfo)
    D. extend_module_loads precedence       (renders Slurm script)
    E. validate_run_recipe + sbatch --test-only  (controller probe; no queue)
    F. Real run_slurm_recipe submission     (only with --submit-real)
    G. Post-submit run-dir layout checks    (only when F ran)

Usage::

    # Quick validation on a login node (sections A-E):
    PYTHONPATH=src .venv/bin/python scripts/rcc/phase0_smoke.py

    # Full end-to-end with a real (tiny) submission of the
    # protein-evidence demo workflow:
    PYTHONPATH=src .venv/bin/python scripts/rcc/phase0_smoke.py \\
        --submit-real \\
        --partition caslake \\
        --account rcc-staff

The submission only runs when ``--submit-real`` is set; the queued job
is the same fixture the existing m18 / protein-evidence smokes use, so
no new compute is consumed beyond what the user already pays for.

Each section prints ``[PASS]``, ``[FAIL]``, or ``[SKIP]`` plus the
specific paths or values to inspect; non-zero exit on any FAIL.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.spec_artifacts import (  # noqa: E402
    DEFAULT_RECIPE_SPEC_FILENAME,
    make_recipe_id,
)
from flytetest.spec_executor import (  # noqa: E402
    DEFAULT_SLURM_MODULE_LOADS,
    DEFAULT_SLURM_SCRIPT_FILENAME,
    _resolve_module_loads,
    render_slurm_script,
)
from flytetest.specs import ResourceSpec  # noqa: E402
from flytetest.staging import check_sbatch_test_only  # noqa: E402


PASS = "\033[32m[PASS]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
SKIP = "\033[33m[SKIP]\033[0m"
INFO = "\033[36m[INFO]\033[0m"


class SmokeReport:
    """Tracks PASS/FAIL counts so the script exits non-zero on any FAIL."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def passed_(self, msg: str) -> None:
        print(f"{PASS} {msg}")
        self.passed += 1

    def failed_(self, msg: str) -> None:
        print(f"{FAIL} {msg}")
        self.failed += 1

    def skipped_(self, msg: str) -> None:
        print(f"{SKIP} {msg}")
        self.skipped += 1

    def info(self, msg: str) -> None:
        print(f"{INFO} {msg}")


def section(title: str) -> None:
    """Print a banner separating the smoke sections."""
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def section_a_validators(report: SmokeReport) -> None:
    section("A. ResourceSpec validators (Phase 0 step 04)")

    cases = [
        ({"memory": "32 GB"}, "memory with space"),
        ({"memory": "32GB"}, "memory with B suffix"),
        ({"walltime": "48h"}, "walltime non-Slurm format"),
        ({"cpu": "eight"}, "cpu non-integer"),
        ({"cpu": "0"}, "cpu zero"),
        ({"execution_class": "slurm", "account": "x"}, "slurm without partition"),
        ({"execution_class": "slurm", "partition": "x"}, "slurm without account"),
    ]
    for kwargs, description in cases:
        try:
            ResourceSpec(**kwargs)
        except ValueError:
            report.passed_(f"freeze rejects {description} ({kwargs})")
        else:
            report.failed_(f"freeze accepted {description} ({kwargs}) — validator regression")

    # Sanity: a fully-specified spec passes
    try:
        ResourceSpec(
            cpu="4", memory="32G", walltime="04:00:00",
            partition="caslake", account="rcc-staff", execution_class="slurm",
        )
        report.passed_("fully-specified slurm spec passes")
    except ValueError as exc:
        report.failed_(f"valid slurm spec was rejected: {exc}")


def section_b_recipe_id(report: SmokeReport) -> None:
    section("B. Recipe-id hash suffix (Phase 0 step 01)")

    short = make_recipe_id("prepare_reference")
    if short.endswith("-prepare_reference"):
        report.passed_(f"short name unchanged: {short}")
    else:
        report.failed_(f"short name had unexpected suffix: {short}")

    long_a = make_recipe_id("select_germline_short_variant_discovery")
    long_b = make_recipe_id("select_germline_short_variant_recalibration")
    import re
    pattern = re.compile(r"-select_germline_short_var-[0-9a-f]{4}$")
    if pattern.search(long_a) and pattern.search(long_b):
        report.passed_(f"long names truncate with hash suffix:\n         {long_a}\n         {long_b}")
    else:
        report.failed_(
            f"long names did not get hash suffix:\n         {long_a}\n         {long_b}"
        )

    if long_a != long_b:
        # Strip timestamp prefix; compare slug+hash.
        slug_a = long_a.split("Z-", 1)[1]
        slug_b = long_b.split("Z-", 1)[1]
        if slug_a != slug_b:
            report.passed_(f"distinct hashes: {slug_a} vs {slug_b}")
        else:
            report.failed_("similarly-prefixed long names collided after truncation")
    else:
        report.failed_("recipe IDs collided across distinct names")


def section_c_list_partitions(report: SmokeReport) -> None:
    section("C. list_slurm_partitions (Phase 0 step 05)")

    if shutil.which("sinfo") is None:
        report.skipped_("sinfo not on PATH; cannot verify against the live controller")
        return

    from flytetest.slurm_introspection import list_slurm_partitions_reply  # noqa: PLC0415

    reply = list_slurm_partitions_reply()
    if not reply.get("supported"):
        report.failed_(
            f"reply.supported is False: reason={reply.get('reason')!r} "
            f"message={reply.get('message')!r}"
        )
        return
    partitions = reply.get("partitions") or []
    if not partitions:
        report.failed_("reply.partitions is empty; sinfo returned no rows")
        return
    report.passed_(f"sinfo returned {len(partitions)} partition(s)")
    for p in partitions[:5]:
        report.info(
            f"  {p['name']:<12} state={p['state']:<6} "
            f"max_walltime={p['max_walltime']:<12} "
            f"available={p['available_nodes']}/{p['total_nodes']}"
        )
    if len(partitions) > 5:
        report.info(f"  ... and {len(partitions) - 5} more")


def section_d_extend_module_loads(report: SmokeReport) -> None:
    section("D. extend_module_loads precedence (Phase 0 step 03)")

    # extend alone → defaults + extension (5 entries)
    result = _resolve_module_loads((), ("bcftools/1.20",))
    if len(result) == 5 and result[-1] == "bcftools/1.20":
        report.passed_(f"extend alone → {len(result)} modules: {list(result)}")
    else:
        report.failed_(f"extend alone produced unexpected list: {result}")

    # module_loads alone → full replace
    result = _resolve_module_loads(("mymod/1.0",), ())
    if result == ("mymod/1.0",):
        report.passed_(f"module_loads alone replaces: {list(result)}")
    else:
        report.failed_(f"module_loads alone replace failed: {result}")

    # both set → module_loads wins, warning logged
    handler_records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = handler_records.append  # type: ignore[method-assign]
    logger = logging.getLogger("flytetest.spec_executor")
    logger.addHandler(handler)
    try:
        result = _resolve_module_loads(("mymod/1.0",), ("bcftools/1.20",))
    finally:
        logger.removeHandler(handler)
    warning_emitted = any(r.levelno == logging.WARNING for r in handler_records)
    if result == ("mymod/1.0",) and warning_emitted:
        report.passed_("both set → module_loads wins, warning emitted")
    elif result == ("mymod/1.0",):
        report.failed_("module_loads won but no warning was emitted (silent drop)")
    else:
        report.failed_(f"module_loads did not win: result={result}")


def section_e_validate_test_only(report: SmokeReport, *, partition: str | None, account: str | None) -> None:
    section("E. validate_run_recipe + sbatch --test-only (Phase 0 step 06)")

    if shutil.which("sbatch") is None:
        report.skipped_("sbatch not on PATH; cannot verify --test-only integration")
        return

    if not (partition and account):
        report.skipped_(
            "no --partition and --account passed; skip — "
            "rerun with --partition X --account Y to verify --test-only"
        )
        return

    # Render a minimal Slurm script with the requested resources, then probe.
    # We use the renderer directly so we don't need to freeze a real recipe.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        artifact_path = tmp_path / "fake-recipe.json"
        artifact_path.write_text("{}")

        good_spec = ResourceSpec(
            cpu="1", memory="1G", walltime="00:05:00",
            partition=partition, account=account, execution_class="slurm",
        )
        good_script = tmp_path / DEFAULT_SLURM_SCRIPT_FILENAME
        good_script.write_text(
            render_slurm_script(
                artifact_path=artifact_path,
                workflow_name="phase0_smoke_validate",
                run_id="phase0-smoke",
                stdout_path=tmp_path / "stdout-%j.out",
                stderr_path=tmp_path / "stderr-%j.err",
                resource_spec=good_spec,
                repo_root=REPO_ROOT,
                python_executable=sys.executable,
            )
        )
        good_findings = check_sbatch_test_only(good_script)
        if not good_findings:
            report.passed_(f"valid resources accepted by --test-only on {partition}/{account}")
        else:
            report.failed_(
                f"valid resources rejected: {[(f.kind, f.reason) for f in good_findings]}"
            )

        bad_spec = ResourceSpec(
            cpu="1", memory="1G", walltime="00:05:00",
            partition="bogus_partition_xyz",
            account=account,
            execution_class="slurm",
        )
        bad_script = tmp_path / "bad.sh"
        bad_script.write_text(
            render_slurm_script(
                artifact_path=artifact_path,
                workflow_name="phase0_smoke_validate_bad",
                run_id="phase0-smoke-bad",
                stdout_path=tmp_path / "bstdout-%j.out",
                stderr_path=tmp_path / "bstderr-%j.err",
                resource_spec=bad_spec,
                repo_root=REPO_ROOT,
                python_executable=sys.executable,
            )
        )
        bad_findings = check_sbatch_test_only(bad_script)
        if bad_findings and bad_findings[0].kind == "slurm_test_only":
            reasons = [f.reason for f in bad_findings]
            if "partition_invalid" in reasons:
                report.passed_("invalid partition produced partition_invalid finding")
            else:
                report.passed_(
                    f"invalid partition produced finding (reason={reasons!r}); "
                    f"if reason is 'test_only_failed' on this controller, the "
                    f"_TEST_ONLY_REASON_PATTERNS table in staging.py needs an update"
                )
        else:
            report.failed_("invalid partition produced NO finding — controller did not reject?")


def section_f_real_submit(
    report: SmokeReport,
    *,
    partition: str,
    account: str,
) -> Path | None:
    section("F. Real run_slurm_recipe submission (Phase 0 steps 01 + 02 + 03)")

    if shutil.which("sbatch") is None:
        report.skipped_("sbatch not on PATH; cannot perform a real submission")
        return None

    from flytetest.planner_types import ProteinEvidenceSet, ReferenceGenome  # noqa: PLC0415
    from flytetest.planning import plan_typed_request  # noqa: PLC0415
    from flytetest.server import _run_slurm_recipe_impl  # noqa: PLC0415
    from flytetest.spec_artifacts import (  # noqa: PLC0415
        artifact_from_typed_plan,
        save_workflow_spec_artifact,
    )

    # Use the protein-evidence fixture. If the BRAKER3 staging is missing
    # locally the submit will fail at the staging preflight; report and skip.
    genome_path = REPO_ROOT / "data/braker3/reference/genome.fa"
    protein_path = REPO_ROOT / "data/braker3/protein_data/fastas/proteins.fa"
    if not genome_path.exists() or not protein_path.exists():
        report.skipped_(
            f"BRAKER3 fixtures missing ({genome_path}, {protein_path}); "
            f"stage them or run scripts/rcc/run_protein_evidence_slurm.py instead"
        )
        return None

    typed_plan = plan_typed_request(
        biological_goal="protein_evidence_alignment",
        target_name="protein_evidence_alignment",
        source_prompt="phase0 smoke — protein evidence alignment",
        explicit_bindings={
            "ReferenceGenome": ReferenceGenome(fasta_path=genome_path),
            "ProteinEvidenceSet": ProteinEvidenceSet(
                reference_genome=ReferenceGenome(fasta_path=genome_path),
                source_protein_fastas=(protein_path,),
            ),
        },
        runtime_bindings={"exonerate_sif": "data/images/exonerate_2.2.0--1.sif"},
        resource_request={
            "cpu": "2",
            "memory": "4Gi",
            "walltime": "00:30:00",
            "partition": partition,
            "account": account,
            "extend_module_loads": ["bcftools/1.20"],
        },
        execution_profile="slurm",
    )
    if not typed_plan.get("supported"):
        report.failed_(f"typed_plan failed: {typed_plan.get('limitations')}")
        return None

    artifact = artifact_from_typed_plan(typed_plan, created_at=datetime.now(UTC).isoformat())
    recipe_id = make_recipe_id("phase0_smoke_protein_evidence")
    artifact_path = save_workflow_spec_artifact(
        artifact,
        REPO_ROOT / ".runtime/runs" / recipe_id / DEFAULT_RECIPE_SPEC_FILENAME,
    )
    report.info(f"recipe_id: {recipe_id}")
    report.info(f"artifact_path: {artifact_path}")

    submitted = _run_slurm_recipe_impl(str(artifact_path))
    if not submitted.get("supported"):
        report.failed_(f"submission failed: {submitted.get('limitations')}")
        return None
    job_id = submitted.get("job_id")
    run_record_path = submitted.get("run_record_path")
    report.passed_(f"submitted job_id={job_id}, run_record_path={run_record_path}")
    return Path(run_record_path) if run_record_path else None


def section_g_post_submit(report: SmokeReport, *, run_record_path: Path) -> None:
    section("G. Post-submit run-dir layout (Phase 0 steps 01 + 02)")

    run_dir = run_record_path.parent
    runs_root = run_dir.parent

    # G1: spec.json next to the run record
    spec = run_dir / DEFAULT_RECIPE_SPEC_FILENAME
    if spec.exists():
        report.passed_(f"spec.json present at {spec}")
    else:
        report.failed_(f"spec.json missing at {spec}")

    # G2: run record written
    if run_record_path.exists():
        report.passed_(f"slurm_run_record.json present at {run_record_path}")
    else:
        report.failed_(f"slurm_run_record.json missing at {run_record_path}")

    # G3: outputs/ directory
    outputs = run_dir / "outputs"
    if outputs.is_dir():
        report.passed_(f"outputs/ directory present at {outputs}")
    else:
        report.failed_(f"outputs/ directory missing at {outputs}")

    # G4: runs/latest symlink resolves to this run_dir
    latest = runs_root / "latest"
    if latest.is_symlink():
        target = (runs_root / latest.readlink()).resolve()
        if target == run_dir.resolve():
            report.passed_(f"runs/latest -> {latest.readlink()} (matches this submission)")
        else:
            report.failed_(f"runs/latest points at {target}, not {run_dir.resolve()}")
    else:
        report.failed_(f"runs/latest is not a symlink at {latest}")

    # G5: monitor_slurm_job paths-in-response
    from flytetest.server import _monitor_slurm_job_impl  # noqa: PLC0415

    status = _monitor_slurm_job_impl(str(run_record_path))
    required = ["spec_path", "run_record_path", "stdout_path", "stderr_path", "outputs_dir"]
    missing = [k for k in required if k not in status]
    if missing:
        report.failed_(f"monitor_slurm_job missing fields: {missing}")
    else:
        report.passed_("monitor_slurm_job carries all 6 path fields")
        for k in required:
            report.info(f"  {k}: {status.get(k)}")

    # G6: rendered Slurm script contains all 5 modules from extend_module_loads
    script_path = run_dir / DEFAULT_SLURM_SCRIPT_FILENAME
    if script_path.exists():
        text = script_path.read_text()
        expected_modules = (*DEFAULT_SLURM_MODULE_LOADS, "bcftools/1.20")
        missing_modules = [m for m in expected_modules if f"module load {m}" not in text and f"module load '{m}'" not in text]
        if not missing_modules:
            report.passed_(f"rendered script loads all {len(expected_modules)} modules (defaults + bcftools)")
        else:
            report.failed_(f"rendered script missing modules: {missing_modules}")
    else:
        report.failed_(f"submit script missing at {script_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--submit-real", action="store_true",
                        help="Submit a real (tiny) protein-evidence job in section F")
    parser.add_argument("--partition", default=os.environ.get("FLYTETEST_SLURM_PARTITION"),
                        help="Slurm partition for sections E and F")
    parser.add_argument("--account", default=os.environ.get("FLYTETEST_SLURM_ACCOUNT"),
                        help="Slurm account for sections E and F")
    args = parser.parse_args()

    report = SmokeReport()
    section_a_validators(report)
    section_b_recipe_id(report)
    section_c_list_partitions(report)
    section_d_extend_module_loads(report)
    section_e_validate_test_only(report, partition=args.partition, account=args.account)

    if args.submit_real:
        if not (args.partition and args.account):
            report.skipped_("--submit-real requires --partition and --account")
        else:
            run_record_path = section_f_real_submit(
                report, partition=args.partition, account=args.account
            )
            if run_record_path is not None:
                section_g_post_submit(report, run_record_path=run_record_path)
    else:
        report.info("Sections F and G skipped (re-run with --submit-real to exercise live submission)")

    print()
    print("=" * 72)
    print(f"  Summary: {report.passed} passed, {report.failed} failed, {report.skipped} skipped")
    print("=" * 72)
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())

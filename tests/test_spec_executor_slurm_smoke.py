"""Optional live smoke tests for the Slurm submission boundary.

The synthetic coverage in `tests/test_spec_executor.py` already checks script
rendering, `sbatch` parsing, and durable run-record persistence with injected
subprocess fakes. This module adds one real cluster smoke test that is skipped
unless `sbatch` is available on the local machine.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.spec_executor import parse_sbatch_job_id


SBATCH_AVAILABLE = shutil.which("sbatch") is not None


class SlurmSpecExecutorSmokeTests(unittest.TestCase):
    """Live Slurm smoke tests that remain optional in CI."""

    @unittest.skipUnless(SBATCH_AVAILABLE, "sbatch is required for the live Slurm smoke test")
    def test_sbatch_accepts_a_tiny_hello_script(self) -> None:
        """Submit one trivial Slurm script and confirm it writes the expected stdout."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / "FlyteTest"
            output_dir.mkdir()

            script_path = tmp_path / "hello_from_slurm.sbatch"
            script_path.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env bash
                    # Here is a comment
                    #SBATCH --time=00:05:00
                    #SBATCH --nodes=1
                    #SBATCH --ntasks-per-node=1
                    #SBATCH --mem-per-cpu=1M
                    #SBATCH --job-name=FlyteTest
                    #SBATCH --account=rcc-staff
                    #SBATCH --partition=caslake
                    #SBATCH --output=FlyteTest/%j.out
                    #SBATCH --error=FlyteTest/%j.err

                    echo "hello from slurm"
                    """
                )
            )
            script_path.chmod(0o755)

            submission = subprocess.run(
                ["sbatch", "--wait", str(script_path)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(submission.returncode, 0, submission.stderr)
            job_id = parse_sbatch_job_id(submission.stdout, submission.stderr)
            stdout_path = output_dir / f"{job_id}.out"

            self.assertTrue(stdout_path.exists())
            self.assertIn("hello from slurm", stdout_path.read_text())

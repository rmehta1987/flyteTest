"""Synthetic coverage for RCC Milestone 18 helper script behavior."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from flytetest.spec_artifacts import load_workflow_spec_artifact


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/rcc/m18_prepare_slurm_recipe.py"


def _load_m18_prepare_module():
    """Load the standalone M18 prepare script as a testable module."""
    spec = importlib.util.spec_from_file_location("m18_prepare_slurm_recipe", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class M18RccHelperTests(TestCase):
    """Checks for the RCC Milestone 18 Slurm recipe helper."""

    def test_prepare_recipe_freezes_relative_busco_sif_as_absolute_path(self) -> None:
        """Keep Apptainer image paths independent of the BUSCO task working directory."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            genome_fasta = repo_root / "data/busco/test_data/eukaryota/genome.fna"
            genome_fasta.parent.mkdir(parents=True)
            genome_fasta.write_text(">fixture\nACGT\n")
            busco_sif = repo_root / "data/images/busco_v6.0.0_cv1.sif"
            busco_sif.parent.mkdir(parents=True)
            busco_sif.write_text("synthetic image placeholder\n")

            env = {
                "FLYTETEST_REPO_ROOT": str(repo_root),
                "FLYTETEST_SLURM_ACCOUNT": "rcc-staff",
                "FLYTETEST_SLURM_QUEUE": "caslake",
                "FLYTETEST_SLURM_WALLTIME": "00:10:00",
                "FLYTETEST_SLURM_CPU": "2",
                "FLYTETEST_BUSCO_CPU": "2",
                "FLYTETEST_SLURM_MEMORY": "8Gi",
                "BUSCO_SIF": "data/images/busco_v6.0.0_cv1.sif",
                "FLYTETEST_BUSCO_GENOME_FASTA": "data/busco/test_data/eukaryota/genome.fna",
            }

            module = _load_m18_prepare_module()
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(module.main(), 0)

            artifact_pointer = repo_root / ".runtime/runs/latest_m18_slurm_artifact.txt"
            artifact = load_workflow_spec_artifact(Path(artifact_pointer.read_text().strip()))
            self.assertEqual(artifact.binding_plan.runtime_bindings["busco_sif"], str(busco_sif))
            self.assertEqual(artifact.binding_plan.runtime_image.apptainer_image, str(busco_sif))

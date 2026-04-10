"""Tests for the shared Flyte task-environment catalog.

These checks keep the environment refactor honest without implying a broader
workflow-runtime change.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest import config


class ConfigTests(TestCase):
    """Coverage for the shared TaskEnvironment catalog and compatibility aliases."""

    def test_task_environment_catalog_applies_shared_defaults(self) -> None:
        """Keep the shared env vars and resources applied to each task family."""
        self.assertIn(config.TASK_ENV_NAME, config.TASK_ENVIRONMENT_NAMES)
        self.assertIn(config.TRANSCRIPT_EVIDENCE_WORKFLOW_NAME, config.TASK_ENVIRONMENT_NAMES)
        self.assertEqual(config.WORKFLOW_NAME, config.TASK_ENV_NAME)

        env = config.TASK_ENVIRONMENTS_BY_NAME[config.TASK_ENV_NAME]
        self.assertEqual(env.kwargs["env_vars"], {"PYTHONUNBUFFERED": "1"})
        self.assertEqual(env.kwargs["resources"].cpu, "1")
        self.assertEqual(env.kwargs["resources"].memory, "1Gi")

        annotation_env = config.TASK_ENVIRONMENTS_BY_NAME[config.ANNOTATION_WORKFLOW_NAME]
        self.assertEqual(annotation_env.kwargs["resources"].cpu, "16")
        self.assertEqual(annotation_env.kwargs["resources"].memory, "64Gi")
        self.assertEqual(annotation_env.kwargs["description"], "BRAKER3 ab initio annotation stage.")

        functional_qc_env = config.TASK_ENVIRONMENTS_BY_NAME[config.FUNCTIONAL_QC_WORKFLOW_NAME]
        self.assertEqual(functional_qc_env.kwargs["resources"].cpu, "4")
        self.assertEqual(functional_qc_env.kwargs["resources"].memory, "8Gi")
        self.assertEqual(functional_qc_env.kwargs["description"], "BUSCO functional QC stage.")

    def test_environment_aliases_stay_stable(self) -> None:
        """Keep the exported environment names available for current imports."""
        self.assertIs(
            config.rnaseq_qc_quant_env,
            config.TASK_ENVIRONMENTS_BY_NAME[config.TASK_ENV_NAME],
        )
        self.assertIs(config.env, config.rnaseq_qc_quant_env)
        self.assertIs(
            config.transcript_evidence_env,
            config.TASK_ENVIRONMENTS_BY_NAME[config.TRANSCRIPT_EVIDENCE_WORKFLOW_NAME],
        )
        self.assertIs(config.consensus_env, config.consensus_prep_env)

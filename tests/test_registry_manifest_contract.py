"""Registry-manifest contract test for showcased entries.

This test keeps showcased registry outputs aligned with the manifest output keys
declared by the task modules that actually write `run_manifest.json` files.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"

sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(SRC_DIR))

from flyte_stub import install_flyte_stub

install_flyte_stub()

from flytetest.registry import REGISTRY_ENTRIES


def _manifest_contract_module_name(showcase_module: str) -> str:
    """Resolve the task module that owns MANIFEST_OUTPUT_KEYS for one showcased entry."""
    if ".tasks." in showcase_module:
        return showcase_module
    if ".workflows." in showcase_module:
        task_module = showcase_module.replace(".workflows.", ".tasks.", 1)
        if importlib.util.find_spec(task_module) is not None:
            return task_module
    return showcase_module


def _missing_declared_manifest_keys(entry: object) -> tuple[str, set[str]]:
    """Return the manifest module name and any registry outputs missing from its key export."""
    showcase_module = getattr(entry, "showcase_module")
    manifest_module_name = _manifest_contract_module_name(showcase_module)
    task_module = importlib.import_module(manifest_module_name)
    manifest_keys = set(getattr(task_module, "MANIFEST_OUTPUT_KEYS", ()))
    declared = {field.name for field in getattr(entry, "outputs")}
    return manifest_module_name, declared - manifest_keys


def test_every_declared_output_is_a_declared_manifest_key() -> None:
    """Every showcased registry output must be listed in the owning task module's manifest keys."""
    for entry in REGISTRY_ENTRIES:
        if not entry.showcase_module:
            continue
        manifest_module_name, missing = _missing_declared_manifest_keys(entry)
        assert not missing, (
            f"{entry.name}: declared outputs {sorted(missing)} are not "
            f"listed in {manifest_module_name}.MANIFEST_OUTPUT_KEYS"
        )


import pytest

_VARIANT_CALLING_TASK_NAMES = [
    "create_sequence_dictionary",
    "index_feature_file",
    "base_recalibrator",
    "apply_bqsr",
    "haplotype_caller",
    "combine_gvcfs",
    "joint_call_gvcfs",
]


@pytest.mark.parametrize("task_name", _VARIANT_CALLING_TASK_NAMES)
def test_variant_calling_manifest_output_keys_align(task_name: str) -> None:
    """Each variant_calling task's registry output names must be in MANIFEST_OUTPUT_KEYS."""
    import importlib
    from flytetest.registry import get_entry

    entry = get_entry(task_name)
    task_module = importlib.import_module("flytetest.tasks.variant_calling")
    manifest_keys = set(getattr(task_module, "MANIFEST_OUTPUT_KEYS", ()))
    declared = {field.name for field in entry.outputs}
    missing = declared - manifest_keys
    assert not missing, (
        f"{task_name}: declared outputs {sorted(missing)} are not listed in "
        f"flytetest.tasks.variant_calling.MANIFEST_OUTPUT_KEYS"
    )
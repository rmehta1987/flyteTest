# Step 04 — Closure

Run all verification gates, update CHANGELOG.md, and prepare for merge.

---

## Verification gates (all must pass)

### Test suite
```bash
PYTHONPATH=src python -m pytest tests/ -q 2>&1 | tail -5
# Expected: 858 passed (+ new tests), 1 skipped
```

### Bundle key fix (Step 01)
```bash
PYTHONPATH=src python -c "
from flytetest.bundles import BUNDLES
for name in ['variant_calling_germline_minimal', 'variant_calling_vqsr_chr20']:
    ri = BUNDLES[name].runtime_images
    assert 'sif_path' not in ri, f'FAIL: {name} still has sif_path'
    assert 'gatk_sif' in ri, f'FAIL: {name} missing gatk_sif'
    print(f'OK: {name} -> {sorted(ri.keys())}')
"
```

### run_slurm_recipe signature (Step 02)
```bash
PYTHONPATH=src python -c "
import inspect
from flytetest.server import run_slurm_recipe
params = inspect.signature(run_slurm_recipe).parameters
assert 'shared_fs_roots' in params, 'FAIL: shared_fs_roots missing'
print('OK: run_slurm_recipe accepts shared_fs_roots')
"
```

### dry_run staging_findings (Step 03)
```bash
PYTHONPATH=src python -c "
import sys; sys.path.insert(0, 'src')
from flytetest.server import run_task
reply = run_task(
    task_name='create_sequence_dictionary',
    inputs={'reference_fasta': '/nonexistent/ref.fa'},
    runtime_images={'gatk_sif': '/nonexistent/gatk4.sif'},
    dry_run=True,
)
assert reply['supported'] == True, 'FAIL: dry_run must stay supported=True'
assert len(reply['staging_findings']) > 0, 'FAIL: staging_findings must be non-empty'
print('OK: dry_run staging_findings populated, supported=True')
"
```

---

## CHANGELOG.md entry

Add under 2026-04-24:
- `bundles.py`: renamed `"sif_path"` → `"gatk_sif"` in GATK bundle `runtime_images`
  so `load_bundle(**bundle)` wires the GATK SIF without manual intervention
- `server.py`: `run_slurm_recipe` now accepts `shared_fs_roots` and passes it to
  the staging preflight, matching `validate_run_recipe` behaviour
- `server.py`: `run_task` and `run_workflow` `dry_run=True` now runs
  `check_offline_staging` and populates `staging_findings` in the reply;
  `supported` remains `True` regardless of findings (informational only)

---

## Merge

```bash
git add -p
git commit -m "mcp-surface-polish: runtime_images key, shared_fs_roots, dry_run staging"
git checkout main && git merge mcp-surface-polish
git mv docs/2026-04-24-mcp-surface-polish docs/archive/2026-04-24-mcp-surface-polish
git commit -m "archive: mcp-surface-polish milestone"
```

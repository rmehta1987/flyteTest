# Step 01 — Fix runtime_images Key in GATK Bundles

The GATK bundles in `src/flytetest/bundles.py` use `"sif_path"` as the key for the
GATK container image in `runtime_images`. But every workflow and task in
`src/flytetest/workflows/variant_calling.py` and `src/flytetest/tasks/variant_calling.py`
accepts a parameter named `gatk_sif`. When a scientist calls `run_workflow(**bundle)`,
`sif_path` does not map to `gatk_sif`, so the GATK SIF is silently ignored.

All other bundles already use matching keys: `braker_sif`, `busco_sif`, `star_sif`,
etc. The GATK bundles are the only ones using the generic `sif_path` key.

---

## Change

File: `src/flytetest/bundles.py`

Find the two GATK bundles and rename `"sif_path"` to `"gatk_sif"` in their
`runtime_images` dicts:

### variant_calling_germline_minimal
```python
# Before:
runtime_images={
    "sif_path": "data/images/gatk4.sif",
    "bwa_sif": "data/images/bwa_mem2.sif",
},

# After:
runtime_images={
    "gatk_sif": "data/images/gatk4.sif",
    "bwa_sif": "data/images/bwa_mem2.sif",
},
```

### variant_calling_vqsr_chr20
```python
# Before:
runtime_images={"sif_path": "data/images/gatk4.sif"},

# After:
runtime_images={"gatk_sif": "data/images/gatk4.sif"},
```

---

## Tests to add

File: `tests/test_bundles.py` (or the nearest bundle test file)

Add a test asserting that the variant_calling bundle `runtime_images` keys match
the actual task/workflow parameter names:
- `"gatk_sif"` present, `"sif_path"` absent
- `"bwa_sif"` present (already correct)

---

## Verification

```bash
PYTHONPATH=src python -c "
from flytetest.bundles import BUNDLES
for name in ['variant_calling_germline_minimal', 'variant_calling_vqsr_chr20']:
    ri = BUNDLES[name].runtime_images
    assert 'sif_path' not in ri, f'{name} still has sif_path key'
    assert 'gatk_sif' in ri, f'{name} missing gatk_sif key'
    print(f'OK: {name} -> {list(ri.keys())}')
"

PYTHONPATH=src python -m pytest tests/ -q 2>&1 | tail -5
```

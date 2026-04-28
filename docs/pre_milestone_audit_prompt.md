# Pre-Milestone Codebase Audit Prompt

Run this before starting the next milestone (user-authored tasks and workflow composition).
The goal is to find silent failures, mismatches, and gaps of the same class as the bugs
discovered during the showcase prep session on 2026-04-28, before they surface during demo
or production runs.

---

## Context — bugs found on 2026-04-28

These bugs all shared the same failure mode: they were silent at plan/dry-run time but
failed during actual Slurm execution, or caused every MCP call to decline without a clear
error message pointing at the root cause.

1. `resource_request` parameter named `resources` in run_workflow/run_task — silent TypeError
2. `File.download_sync()` used for reference FASTA — copies file to temp dir, leaves index
   files (.bwt.2bit.64, .dict, .fai) at original path; bwa-mem2/GATK fail on compute node
3. `bwa_sif` present in workflow Python signatures but missing from registry InterfaceField
   inputs — silently dropped by _build_node_inputs, falls back to PATH (not found)
4. Empty string not clearing runtime_images default — gatk_sif="" passed but registry default
   "data/images/gatk4.sif" survived the merge in _coerce_string_mapping
5. ReadPair, VariantCallSet missing from resolver._PLANNER_TYPES_BY_NAME — plan always
   declined with "No resolver registered" even when scalar inputs were provided
6. KnownSites, AlignmentSet in accepted_planner_types for workflows that only use them as
   scalars — blocked every plan for those workflows
7. 8 of 23 flat tools missing required planner type bindings — annotation_protein_evidence,
   annotation_braker3, vc_post_genotyping_refinement, vc_post_call_qc_summary,
   vc_annotate_variants_snpeff and others
8. ANSI escape codes from module load polluting MCP stdio stream — server failed to start

---

## Audit Tasks

Work through each check below. For each finding, report: file, line number, the pattern,
and the severity (BREAKING / SILENT_FAILURE / WRONG_RESULT / MINOR).

Read the relevant source files directly — do not rely on memory.

---

### Check 1 — File.download_sync() on companion-file inputs

Search for all uses of `download_sync()` across src/flytetest/tasks/.
For each call, determine whether the downloaded file has companion files (indexes, dict
files, BAI files, etc.) that must exist in the same directory.

The pattern to flag:
  ref = Path(some_file.download_sync())   # copies file, leaves companions at original path
  cmd = ["tool", str(ref), ...]           # tool looks for ref.bwt.2bit.64 beside ref — not there

Files to check: src/flytetest/tasks/*.py
Severity if found: SILENT_FAILURE on compute node

---

### Check 2 — Registry InterfaceField gaps

For every workflow in src/flytetest/workflows/*.py, compare:
  a. The Python function signature parameters
  b. The InterfaceField inputs in the corresponding RegistryEntry

Flag any parameter that is in (a) but not in (b). These parameters are silently dropped
by _build_node_inputs in spec_executor.py because it only looks up fields declared in
entry.inputs.

Pay particular attention to SIF path parameters (gatk_sif, bwa_sif, pasa_sif, etc.) and
any File-typed parameters that carry companion files.

Files to check:
  src/flytetest/workflows/*.py  (function signatures)
  src/flytetest/registry/_*.py  (InterfaceField inputs tuples)
Severity if found: SILENT_FAILURE — parameter silently dropped, tool falls back to PATH

---

### Check 3 — Unresolvable planner types in accepted_planner_types

For every RegistryEntry, check whether each type listed in accepted_planner_types has a
registered materializer in resolver._PLANNER_TYPES_BY_NAME.

The current registered types are:
  ReferenceGenome, ReadPair, ReadSet, VariantCallSet, TranscriptEvidenceSet,
  ProteinEvidenceSet, AnnotationEvidenceSet, ConsensusAnnotation, QualityAssessmentTarget

Any type listed in accepted_planner_types that is NOT in this set will cause the planner
to always decline for that workflow, even if scalar inputs are provided.

Files to check:
  src/flytetest/registry/_*.py  (accepted_planner_types fields)
  src/flytetest/resolver.py     (_PLANNER_TYPES_BY_NAME dict)
Severity if found: BREAKING — plan always declined, workflow uncallable via run_workflow

---

### Check 4 — Flat tool binding completeness

For every function in src/flytetest/mcp_tools.py, confirm that the bindings dict it
constructs contains a key for every type listed in the target workflow's
accepted_planner_types.

The accepted_planner_types for a workflow can be read from:
  get_entry(workflow_name).compatibility.accepted_planner_types

A flat tool that passes only ReferenceGenome when the workflow also requires ProteinEvidenceSet
will fail at the planning stage despite the flat tool having an explicit protein_fasta_path
parameter.

Files to check: src/flytetest/mcp_tools.py, src/flytetest/registry/_*.py
Severity if found: BREAKING — flat tool call always declines

---

### Check 5 — Silent scalar input conflicts

For any flat tool that puts a parameter value in BOTH bindings (as an inner-dict key)
AND in inputs (as a top-level key), the scalar-input validator will flag it as
"Unknown scalar inputs" because _scalar_params_for_workflow filters out names that appear
in bound_field_names.

Pattern to flag:
  bindings = {"SomeType": {"vcf_path": vcf}}
  inputs   = {"vcf_path": vcf}   # vcf_path is in bound_field_names → unknown scalar

Files to check: src/flytetest/mcp_tools.py
Severity if found: BREAKING — call always declines with "Unknown scalar inputs"

---

### Check 6 — runtime_images default override

In planning._select_execution_policy, _coerce_string_mapping silently drops empty-string
values. The 2026-04-28 fix added a second pass to delete keys where the caller explicitly
passed "". Verify this fix is in place and covers all callers.

Also check: are there any tool_databases entries in flat tools or bundles that might have
the same silent-no-op problem if a user passes "" to clear a default?

Files to check:
  src/flytetest/planning.py  (_select_execution_policy, around line 546)
  src/flytetest/mcp_tools.py  (tool_databases handling in flat tools)
Severity if found: WRONG_RESULT — registry default silently wins over caller intent

---

### Check 7 — MCP server stdout pollution

Check the opencode.json server command and any other MCP server startup configurations
for commands that might write to stdout before exec-ing the Python server.

Pattern to flag: any shell command between server startup and the Python process that
could emit text (echo, printf, module load without >/dev/null, motd, PS1 setup, etc.)

Files to check:
  .config/opencode/opencode.json
  Any other MCP server config files in the repo
Severity if found: BREAKING — MCP handshake fails, server appears unresponsive

---

### Check 8 — Task-level download_sync on BAM/VCF inputs

Check all task functions that call download_sync() on aligned BAM, VCF, or GFF3 inputs.
These file types have companion index files (.bai, .tbi, .csi) that must be in the same
directory. If download_sync() copies the main file to a temp dir without the index, samtools
view, tabix, and GATK will fail.

The fix pattern (already applied to reference_fasta calls):
  path = Path(file_input.path)   # use .path, not .download_sync()

Files to check: src/flytetest/tasks/*.py
Look for: aligned_bam.download_sync(), vcf.download_sync(), gff3.download_sync()
Severity if found: SILENT_FAILURE on any indexed file type

---

### Check 9 — Registry entry / showcase_module completeness

For every function decorated with @variant_calling_env.task or similar in
src/flytetest/tasks/*.py, check whether the corresponding RegistryEntry has
showcase_module set. Entries without showcase_module are not exposed as MCP tools.

Cross-check: every entry with showcase_module should have a corresponding flat tool
in mcp_tools.py (per the convention added in the simplified-mcp-tools milestone).

Files to check:
  src/flytetest/tasks/*.py     (task definitions)
  src/flytetest/registry/_*.py (showcase_module fields)
  src/flytetest/mcp_tools.py   (flat tool coverage)
Severity if found: MINOR — task registered but not callable via MCP surface

---

### Check 10 — Test coverage for Slurm execution path

Confirm that for the primary demo workflows (prepare_reference,
germline_short_variant_discovery, protein_evidence_alignment, ab_initio_annotation_braker3),
there are tests that exercise the full run_workflow → plan_typed_request → artifact creation
path with dry_run=True and assert supported=True.

A test that only checks result.get("target") == "workflow_name" is asserting the decline
path, not the success path.

Files to check: tests/test_server.py, tests/test_mcp_tools.py
Severity if found: MINOR — gap doesn't cause a runtime bug but hides regressions

---

## What to produce

For each check, report:

  CHECK N: <name>
  Status: PASS / FINDINGS
  Findings:
    - file:line — description — severity
  Recommended fix: one sentence

If all checks pass, confirm clean. If findings exist, prioritize by severity and list
the highest-severity items first.

Do not fix anything. Report only. The goal is a punch list to address before the next
milestone begins.

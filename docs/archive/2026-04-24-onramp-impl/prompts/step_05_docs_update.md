# Step 05 — Documentation Updates

Two doc files need updating now that the implementation exists. Read both files in
full before editing.

---

## Edit 1 — `.codex/user_tasks.md`

### 1a. Update the execution-mode section

Find the section that describes SIF images and the `run_tool` escape hatch
(currently `run_tool` native fallback at `config.py:261`). Replace or expand it to
document all three modes as a clear decision table. The section heading may vary;
update whatever currently describes how execution works:

```markdown
## Execution modes — choosing the right run_tool path

`run_tool` in `src/flytetest/config.py` supports three modes. Pick exactly one:

| Mode | When to use | Call shape |
|---|---|---|
| **SIF / container** | tool ships in a container (GATK, bwa-mem2, SnpEff, BRAKER3) | `run_tool(cmd, sif_path, bind_paths)` |
| **Native executable** | binary on PATH or at an explicit path (Rscript, compiled C++, samtools) | `run_tool(cmd, sif="", bind_paths=[])` |
| **Python callable** | pure-Python logic, no external binary | `run_tool(python_callable=fn, callable_kwargs={...})` |

**SIF mode** is the default for bioinformatics tools that ship containers. Pass
`sif=""` (or omit the SIF argument) to fall back to the native binary on PATH.

**Native executable mode** works for any binary the compute node can reach: an
Rscript installed as a module, a compiled C++ tool in a project `bin/`, or any
system utility. No container overhead.

**Python callable mode** invokes a function in-process. No subprocess is started.
Use this when your logic has no external binary dependency — a threshold filter,
a statistics aggregation, a file-format converter written in Python. The callable
must accept keyword arguments matching `callable_kwargs`.
```

### 1b. Update the worked example to point to the real implementation

Find the worked example ("custom Python variant filter"). Update the text to
reference the real implementation rather than an inline sketch:

```markdown
The reference implementation of this pattern is `my_custom_filter` in
`src/flytetest/tasks/variant_calling.py`. It uses `run_tool` in Python-callable
mode, calling `filter_vcf` from `src/flytetest/tasks/_filter_helpers.py`.
Read it before writing your own task — it is the copyable template.
```

### 1c. Update the testing section

Find the "Testing without a SIF" section. Add a note that Python-callable tasks
do not need `patch.object(config, "run_tool", ...)`:

```markdown
**Pure-Python tasks** (Python-callable mode) are simpler to test than SIF tasks:
there is no subprocess to mock. Call the task directly with a `File` stub and
assert on the output file and manifest. See `MyCustomFilterInvocationTests` in
`tests/test_variant_calling.py` for the pattern — it is shorter than the
`patch.object(config, "run_tool", ...)` pattern needed for subprocess tasks.
```

---

## Edit 2 — `.codex/agent/scaffold.md`

### 2a. Fix Core Principle 1 wording

Find Core Principle 1. It currently says something like "up to four file edits".
Replace that wording with the accurate count:

```markdown
**Core Principle 1 — One intent, one coordinated patch.**
A scaffolding run produces exactly these touch points:
1. Task wrapper appended to the family task module
2. `MANIFEST_OUTPUT_KEYS` append in that same module
3. `RegistryEntry` appended to the family registry file
4. `TASK_PARAMETERS` append in `server.py` (tasks only; workflows skip this)
5. Test stubs appended to the family test file
6. `CHANGELOG.md` dated entry
7. (Optional) workflow wiring if the user asked for it

Never produce fewer than 1–5 + 6. Never produce more without an explicit request.
```

### 2b. Update the Execution Mode section in Generation Order

Find the SIF Image Decision section (or wherever execution mode is discussed in
the scaffold). Add the Python-callable mode:

```markdown
**Execution mode — three choices:**

- **SIF**: user supplies a `.sif` path → `run_tool(cmd, sif_path, bind_paths)`
- **Native**: tool is a system binary → `run_tool(cmd, sif="", bind_paths=[])`
- **Python callable**: no external binary → `run_tool(python_callable=fn, callable_kwargs={...})`

When the user says "pure Python" or "no container", generate the Python-callable
form. Declare `runtime_images={}` and `module_loads=("python/3.11.9",)` in the
registry entry.
```

---

## Verification

```bash
# Confirm the three-mode table appears in the guide
grep -n "Native executable\|Python callable\|SIF" .codex/user_tasks.md

# Confirm Core Principle 1 mentions five touch points
grep -n "MANIFEST_OUTPUT_KEYS\|TASK_PARAMETERS\|RegistryEntry" .codex/agent/scaffold.md | head -10

# Confirm the real implementation is linked
grep -n "my_custom_filter\|_filter_helpers" .codex/user_tasks.md
```

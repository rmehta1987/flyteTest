# Step 05 — Documentation Update

Read `.codex/user_tasks.md` in full before editing.

---

## Edit — `.codex/user_tasks.md`

### Update the "Worked example" section

Find the section "Worked example — custom Python variant filter". The current text
describes the pattern as a hypothetical. Update the final part to link both the
task-level flat tool and the composed workflow as real, callable examples:

```markdown
## Real on-ramp artifacts (callable today)

After the user-authored-workflows milestone the following are all real, registered
entries callable via MCP:

| Name | Type | Flat tool | Description |
|---|---|---|---|
| `my_custom_filter` | task | `vc_custom_filter` | QUAL filter via Python callable mode |
| `apply_custom_filter` | workflow | `vc_apply_custom_filter` | Composed: existing VCF → `my_custom_filter` |

Use these as copy-paste templates. The task shows Python-callable mode; the workflow
shows how to wire a custom task into a new end-to-end entry without touching
upstream GATK steps.
```

### Update the "Wiring into a workflow" section

After the prose description, add a pointer to the real implementation:

```markdown
The reference composition is `apply_custom_filter` in
`src/flytetest/workflows/variant_calling.py`. Read it before writing your own
composed workflow — it is the minimal, copyable template.
```

---

## Verification

```bash
grep -n "apply_custom_filter\|vc_custom_filter\|vc_apply_custom_filter" \
    .codex/user_tasks.md
```

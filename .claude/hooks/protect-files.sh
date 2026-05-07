#!/bin/bash
# Block accidental edits to flyteTest's compatibility-critical surfaces.
# To override (use sparingly): export FLYTETEST_ALLOW_COMPAT_EDIT=1
#
# Operational enforcement of the MCP-Layer Branch-Free Rule and related
# compatibility invariants documented in AGENTS.md (Hard Constraints).

# Allow the edit if the override env var is set.
if [ "${FLYTETEST_ALLOW_COMPAT_EDIT:-0}" = "1" ]; then
  exit 0
fi

INPUT=$(cat)

# jq is required to parse the tool-input JSON. Skip silently if missing
# rather than blocking edits unintentionally.
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

TOOL=$(echo "$INPUT" | jq -r '.tool_name')

# Only enforce on Edit/Write tools.
if [ "$TOOL" != "Edit" ] && [ "$TOOL" != "Write" ]; then
  exit 0
fi

FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [ -z "$FILE" ]; then
  exit 0
fi

# Compatibility-critical surfaces. Edits here can break the MCP layer,
# planner contract, or workflow compatibility surface. See AGENTS.md
# (Hard Constraints) and the MCP-Layer Branch-Free Rule.
PROTECTED_PATHS=(
  "src/flytetest/server.py"
  "src/flytetest/mcp_contract.py"
  "src/flytetest/planning.py"
  "src/flytetest/spec_executor.py"
  "src/flytetest/registry/__init__.py"
  "flyte_rnaseq_workflow.py"
)

for PATTERN in "${PROTECTED_PATHS[@]}"; do
  if [[ "$FILE" == *"$PATTERN" ]]; then
    {
      echo "Protected file: $PATTERN"
      echo ""
      echo "This file is part of flyteTest's compatibility-critical surface."
      echo "Edits to it can break the MCP contract, planner output shape,"
      echo "or workflow compatibility exports."
      echo ""
      echo "See AGENTS.md (Hard Constraints) and .codex/agent/code-review.md"
      echo "(MCP-Layer Branch-Free Rule)."
      echo ""
      echo "To override (use sparingly):"
      echo "  export FLYTETEST_ALLOW_COMPAT_EDIT=1"
    } >&2
    exit 2
  fi
done

exit 0

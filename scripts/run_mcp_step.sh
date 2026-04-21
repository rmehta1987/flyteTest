#!/usr/bin/env bash
# Unattended overnight runner for MCP reshape steps 17-30.
#
# Usage:
#   ./scripts/run_mcp_step.sh            # run all remaining steps (17-30)
#   ./scripts/run_mcp_step.sh 17         # single step
#   ./scripts/run_mcp_step.sh 17 18 19   # specific steps in order
#   ./scripts/run_mcp_step.sh --from 20  # step 20 through 30
#
# Logs land in logs/mcp_steps/YYYYMMDD_HHMMSS/step_NN.log
# On step failure the run stops; re-run with --from <failed_step> to resume.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_DIR="${REPO_ROOT}/docs/mcp_reshape/prompts"
LOG_BASE="${REPO_ROOT}/logs/mcp_steps"
RUN_TAG="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${LOG_BASE}/${RUN_TAG}"

ALL_STEPS=(17 18 19 20 21 22 23 24 25 26 27 28 29 30)

# Model + effort per step.
# Only steps where prompts explicitly say "Opus recommended" use opus.
# Everything else uses sonnet.
#   max    — BC-critical; prompt says Opus
#   high   — server reshape; complex but not BC-cascade-critical
#   medium — additive wiring, sweep, docs
declare -A STEP_MODEL=(
    [17]="opus"   [18]="sonnet" [19]="sonnet" [20]="sonnet"
    [21]="opus"   [22]="opus"   [23]="sonnet" [24]="sonnet"
    [25]="sonnet" [26]="sonnet" [27]="sonnet" [28]="sonnet"
    [29]="sonnet" [30]="sonnet"
)
declare -A STEP_EFFORT=(
    [17]="max"    [18]="high"   [19]="high"   [20]="high"
    [21]="max"    [22]="max"    [23]="high"   [24]="medium"
    [25]="medium" [26]="medium" [27]="medium" [28]="medium"
    [29]="medium" [30]="medium"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

log() { echo "[$(date +%H:%M:%S)] $*"; }

resolve_prompt_file() {
    local step
    step=$(printf '%02d' "$1")
    local match
    match=$(ls "${PROMPT_DIR}/step_${step}_"*.md 2>/dev/null | head -1)
    if [[ -z "$match" ]]; then
        log "ERROR: No prompt file for step $1 in ${PROMPT_DIR}" >&2
        return 1
    fi
    echo "$match"
}

run_step() {
    local step="$1"
    local model="${STEP_MODEL[$step]:-sonnet}"
    local effort="${STEP_EFFORT[$step]:-medium}"
    local prompt_file
    prompt_file=$(resolve_prompt_file "$step")
    local step_log="${LOG_DIR}/step_$(printf '%02d' "$step").log"

    log "━━━ Step ${step}: $(basename "$prompt_file" .md) ━━━"
    log "Model: ${model}  |  Effort: ${effort}  |  Log: ${step_log}"

    local t0
    t0=$(date +%s)

    # bypassPermissions skips all approval prompts — safe for unattended runs
    # on a trusted local repo. Tee so progress is visible AND saved to log.
    # < /dev/null prevents claude from hanging waiting for stdin under nohup.
    claude \
        --model "$model" \
        --effort "$effort" \
        --permission-mode bypassPermissions \
        -p "$(cat "$prompt_file")" \
        < /dev/null \
        2>&1 | tee "$step_log"

    local exit_code=${PIPESTATUS[0]}
    local elapsed=$(( $(date +%s) - t0 ))

    if [[ $exit_code -ne 0 ]]; then
        log "FAILED (exit ${exit_code}) after ${elapsed}s — stopping."
        log "Resume with: ./scripts/run_mcp_step.sh --from ${step}"
        exit $exit_code
    fi

    log "Step ${step} done in ${elapsed}s."
}

# ── Argument parsing ──────────────────────────────────────────────────────────

steps=()

if [[ $# -eq 0 ]]; then
    steps=("${ALL_STEPS[@]}")
elif [[ "$1" == "--from" ]]; then
    if [[ -z "${2:-}" ]]; then
        echo "Usage: $(basename "$0") --from <step>" >&2; exit 1
    fi
    for s in "${ALL_STEPS[@]}"; do
        [[ $s -ge $2 ]] && steps+=("$s")
    done
else
    steps=("$@")
fi

if [[ ${#steps[@]} -eq 0 ]]; then
    echo "No steps to run." >&2; exit 1
fi

# ── Run ───────────────────────────────────────────────────────────────────────

mkdir -p "$LOG_DIR"

log "MCP reshape run: steps ${steps[*]}"
log "Model: per-step (opus/sonnet)  |  Effort: per-step (max/high/medium)"
log "Logs: ${LOG_DIR}/"
log ""

OVERALL_START=$(date +%s)
FAILED=()

for step in "${steps[@]}"; do
    if ! run_step "$step"; then
        FAILED+=("$step")
        break
    fi
    echo ""
done

ELAPSED=$(( $(date +%s) - OVERALL_START ))

echo ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ ${#FAILED[@]} -eq 0 ]]; then
    log "All steps complete in ${ELAPSED}s."
else
    log "Stopped at step ${FAILED[0]} after ${ELAPSED}s."
    log "Resume: ./scripts/run_mcp_step.sh --from ${FAILED[0]}"
    exit 1
fi

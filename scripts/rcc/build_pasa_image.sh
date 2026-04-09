#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DOCKERFILE="${DOCKERFILE:-$REPO_ROOT/containers/pasa/Dockerfile}"
DOCKER_CONTEXT="${DOCKER_CONTEXT:-$REPO_ROOT/containers/pasa}"
DOCKER_IMAGE_TAG="${DOCKER_IMAGE_TAG:-flytetest/pasa-legacyblast:2.5.3}"
APPTAINER_DEF_FILE="${APPTAINER_DEF_FILE:-$REPO_ROOT/containers/pasa/pasa_legacyblast.def}"
OUTPUT_SIF="${OUTPUT_SIF:-$REPO_ROOT/data/images/pasa_2.5.3.legacyblast.sif}"
APPTAINER_BUILD_OPTS="${APPTAINER_BUILD_OPTS:-}"

if command -v docker >/dev/null 2>&1 && [[ -f "$DOCKERFILE" ]]; then
  if ! command -v apptainer >/dev/null 2>&1; then
    echo "apptainer is required to export the built Docker image to a SIF." >&2
    exit 1
  fi

  echo "Building PASA image from Dockerfile:"
  echo "  dockerfile: $DOCKERFILE"
  echo "  context:    $DOCKER_CONTEXT"
  echo "  tag:        $DOCKER_IMAGE_TAG"
  echo "  output:     $OUTPUT_SIF"

  docker build -t "$DOCKER_IMAGE_TAG" -f "$DOCKERFILE" "$DOCKER_CONTEXT"
  if [[ -n "$APPTAINER_BUILD_OPTS" ]]; then
    # shellcheck disable=SC2086
    apptainer build $APPTAINER_BUILD_OPTS "$OUTPUT_SIF" "docker-daemon://$DOCKER_IMAGE_TAG"
  else
    apptainer build "$OUTPUT_SIF" "docker-daemon://$DOCKER_IMAGE_TAG"
  fi
elif command -v apptainer >/dev/null 2>&1 && [[ -f "$APPTAINER_DEF_FILE" ]]; then
  echo "Building PASA image from Apptainer definition:"
  echo "  definition: $APPTAINER_DEF_FILE"
  echo "  output:     $OUTPUT_SIF"

  if [[ -n "$APPTAINER_BUILD_OPTS" ]]; then
    # shellcheck disable=SC2086
    apptainer build $APPTAINER_BUILD_OPTS "$OUTPUT_SIF" "$APPTAINER_DEF_FILE"
  else
    apptainer build "$OUTPUT_SIF" "$APPTAINER_DEF_FILE"
  fi
else
  echo "need either docker + apptainer + $DOCKERFILE, or apptainer + $APPTAINER_DEF_FILE" >&2
  exit 1
fi

echo "Built PASA image at $OUTPUT_SIF"

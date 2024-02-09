#!/usr/bin/env sh

set -o errexit
set -o nounset

OPTIONS=$(yq --no-colors --exit-status '
.items.[]
  | select(
      .apiVersion == "kustomize.shamrock.systems/v1alpha1"
      and .kind == "JsonnetGenerator"
    )
  | .spec' <&0)
export OPTIONS

PROJECT_DIR=$(yq --null-input '(env(OPTIONS) | .projectDir)')
PROJECT_FILE=$(yq --null-input '(env(OPTIONS) | .projectFile)')
USE_JB=$(yq --null-input '(env(OPTIONS) | .useJsonnetBundler) // "false"')

cd "$PROJECT_DIR"

JSONNET_ARGS=""
if [ "$USE_JB" = "true" ]; then
  JSONNET_ARGS="-J vendor"

  jb install
fi

# shellcheck disable=SC2086
jsonnet $JSONNET_ARGS "$PROJECT_FILE"

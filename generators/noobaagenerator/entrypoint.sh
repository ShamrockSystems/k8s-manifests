#!/usr/bin/env bash

set -o errexit
set -o nounset

OPTIONS=$(yq --no-colors --exit-status '
.items.[]
  | select(
      .apiVersion == "kustomize.shamrock.systems/v1alpha1"
      and .kind == "NoobaaGenerator"
    )
  | .spec' <&0)
export OPTIONS

INSTALL_ARGS=$(yq --null-input '(env(OPTIONS) | .installArgs[])' | tr '\n' ' ')

eval "noobaa install yaml $INSTALL_ARGS"

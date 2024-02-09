#!/usr/bin/env sh

set -o errexit
set -o nounset

OPTIONS=$(yq --no-colors --exit-status '
.items.[]
  | select(
      .apiVersion == "kustomize.shamrock.systems/v1alpha1"
      and .kind == "GithubCollectorGenerator"
    )
  | .spec' <&0)
export OPTIONS

API_URL=$(yq --no-colors --exit-status '
[
  "https://github.com",
  (env(OPTIONS) | .organization),
  (env(OPTIONS) | .repository),
  "tree",
  (env(OPTIONS) | .ref),
  (env(OPTIONS) | .path)
]
  | join("/")')
RAW_URL_BASE=$(yq --no-colors --exit-status '
[
  "https://raw.githubusercontent.com/",
  (env(OPTIONS) | .organization),
  (env(OPTIONS) | .repository),
  (env(OPTIONS) | .ref)
]
  | join("/")')
export RAW_URL_BASE

URLS=$(curl -sL "$API_URL" |
  yq '
    .payload.tree.items.[]
      | select(
          .contentType=="file"
          and (.name | test(.*\.yaml$))
        )
      | [
        strenv(RAW_URL_BASE),
        .path
      ]
      | join("/")')

COMBINED=""
while read -r url; do
    COMBINED="$COMBINED
---
$(curl -sL "$url")"
done <<EOF
$URLS
EOF

# shellcheck disable=SC2016
echo "$COMBINED" | yq eval-all '
  select(has("apiVersion") and has("kind"))
    | . as $item ireduce ([]; . + [$item])
    | {
        "apiVersion": "config.kubernetes.io/v1",
        "kind": "ResourceList",
        "items": .
      }'

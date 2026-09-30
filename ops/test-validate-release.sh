#!/usr/bin/env bash
set -Eeuo pipefail

# Synthetic references only: the preflight must reject untrusted registries before authentication.
export SOURCE_IMAGE_PREFIX="us-central1-docker.pkg.dev/nodo-test/nodo"
digest="$(printf '%064d' 0)"
export API_IMAGE="${SOURCE_IMAGE_PREFIX}/api@sha256:${digest}"
export PWA_IMAGE="${SOURCE_IMAGE_PREFIX}/pwa@sha256:${digest}"
bash ops/validate-release.sh digests

reject() {
  if env "$@" bash ops/validate-release.sh digests >/dev/null 2>&1; then
    printf 'ERROR: accepted an untrusted or mutable image reference.\n' >&2
    exit 1
  fi
}

reject API_IMAGE="attacker.example/api@sha256:${digest}"
reject SOURCE_IMAGE_PREFIX="attacker.example/project/repo" API_IMAGE="attacker.example/project/repo/api@sha256:${digest}" PWA_IMAGE="attacker.example/project/repo/pwa@sha256:${digest}"
reject API_IMAGE="${SOURCE_IMAGE_PREFIX}.evil/api@sha256:${digest}"
reject API_IMAGE="us-central1-docker.pkg.dev/another-project/nodo/api@sha256:${digest}"
reject API_IMAGE="${SOURCE_IMAGE_PREFIX}/pwa@sha256:${digest}"
reject PWA_IMAGE="${SOURCE_IMAGE_PREFIX}/pwa:latest"
reject SOURCE_IMAGE_PREFIX=""
printf 'Release origin tests OK (1 accepted, 7 rejected).\n'

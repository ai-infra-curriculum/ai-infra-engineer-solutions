#!/usr/bin/env bash
set -euo pipefail
IMAGE=${IMAGE:-ghcr.io/me/iris-api:0.4}
IDENTITY=${IDENTITY:-https://github.com/me/iris-api/.github/workflows/sign-publish.yml@refs/heads/main}

COSIGN_EXPERIMENTAL=1 cosign verify "$IMAGE" \
  --certificate-identity "$IDENTITY" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

COSIGN_EXPERIMENTAL=1 cosign verify-attestation "$IMAGE" \
  --type cyclonedx \
  --certificate-identity "$IDENTITY" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

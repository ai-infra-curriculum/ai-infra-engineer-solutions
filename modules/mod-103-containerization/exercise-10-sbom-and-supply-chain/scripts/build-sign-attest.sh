#!/usr/bin/env bash
# Build → SBOM → scan → sign → attest. Requires: docker, syft, grype, cosign.
set -euo pipefail
IMAGE=${IMAGE:-ghcr.io/me/iris-api:0.4}

echo "--- build ---"
docker buildx build -t "$IMAGE" --push .

echo "--- SBOM ---"
syft -o cyclonedx-json "$IMAGE" > sbom.cdx.json

echo "--- vuln scan ---"
grype sbom:sbom.cdx.json --fail-on high --output table

echo "--- sign keyless (Sigstore) ---"
COSIGN_EXPERIMENTAL=1 cosign sign --yes "$IMAGE"

echo "--- attest SBOM ---"
COSIGN_EXPERIMENTAL=1 cosign attest --yes --type cyclonedx \
  --predicate sbom.cdx.json "$IMAGE"

echo "--- attest SLSA provenance ---"
# Provenance generated separately by GitHub Actions (slsa-github-generator).
# Locally we attach a stub:
cat > provenance.json <<EOF
{ "buildType": "https://example.com/local-build/v1",
  "builder": { "id": "$(id -un)@$(hostname)" },
  "invocation": { "configSource": { "uri": "git+$(git config --get remote.origin.url)" } } }
EOF
COSIGN_EXPERIMENTAL=1 cosign attest --yes --type slsaprovenance \
  --predicate provenance.json "$IMAGE"

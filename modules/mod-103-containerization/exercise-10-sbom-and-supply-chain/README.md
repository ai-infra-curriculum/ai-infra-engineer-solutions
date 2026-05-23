# SBOM + Supply Chain (SLSA L2) — Solution

Reference for [learning exercise-10](https://github.com/ai-infra-curriculum/ai-infra-engineer-learning/blob/main/lessons/mod-103-containerization/exercises/exercise-10-sbom-and-supply-chain/README.md).

End-to-end: build → SBOM (syft) → scan (grype) → sign keyless (cosign) → attach SBOM
attestation → Kyverno policy gate.

## Layout

```
exercise-10-sbom-and-supply-chain/
├── README.md
├── scripts/
│   ├── build-sign-attest.sh
│   └── verify.sh
├── kyverno/
│   ├── require-signed.yaml
│   └── require-sbom-no-critical.yaml
└── .github/workflows/sign-publish.yml
```

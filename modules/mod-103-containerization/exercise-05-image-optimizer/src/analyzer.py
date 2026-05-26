"""
Dockerfile Analyzer

Parses Dockerfiles into a structured representation and surfaces
optimization opportunities: single-stage builds that should be
multi-stage, build tools left in the final image, unordered layers
that hurt caching, large files in intermediate layers, and suboptimal
base images.

The parser is intentionally simple — it handles the subset of
Dockerfile syntax that matters for analysis (FROM/RUN/COPY/WORKDIR/
ENV/CMD/USER/ENTRYPOINT/ARG/EXPOSE/HEALTHCHECK/LABEL/ADD), respects
backslash continuation, and tracks per-stage scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Tools that signal build-time dependencies that should not survive
# into the final runtime image.
BUILD_TOOLS = {
    "gcc", "g++", "make", "cmake", "automake", "autoconf",
    "build-essential", "git", "curl", "wget", "tar", "unzip",
    "npm", "yarn", "pnpm",
    "maven", "gradle",
    "rustup", "cargo",
    "go", "golang",
    "pip", "poetry", "pipenv",
}

# Slim/distroless base images that are typically the right destination
# for the final stage of a multi-stage build.
PREFERRED_BASE_IMAGES = {
    "python": [
        ("python:slim", "python:[0-9.]+-slim"),
        ("distroless/python", "gcr.io/distroless/python3-debian.*"),
    ],
    "node": [
        ("node:slim", "node:[0-9.]+-slim"),
        ("distroless/nodejs", "gcr.io/distroless/nodejs"),
    ],
    "java": [
        ("eclipse-temurin:jre", "eclipse-temurin:.*-jre"),
        ("distroless/java", "gcr.io/distroless/java"),
    ],
}

# Common patterns that suggest a leftover build artifact.
LARGE_ARTIFACT_HINTS = (
    "build/", "target/", "node_modules", ".git",
    "*.tar.gz", "*.zip", "*.deb",
)


@dataclass
class Instruction:
    """A single Dockerfile instruction within a stage."""

    name: str  # "FROM", "RUN", "COPY", ...
    args: str
    line_number: int

    def as_text(self) -> str:
        return f"{self.name} {self.args}"


@dataclass
class Stage:
    """One stage in a Dockerfile (between two FROM lines)."""

    index: int
    base_image: str
    alias: Optional[str]  # `AS builder` target
    instructions: List[Instruction] = field(default_factory=list)

    @property
    def is_final(self) -> bool:
        # The analyzer sets this externally — here it's a placeholder.
        return False

    def get(self, name: str) -> List[Instruction]:
        return [i for i in self.instructions if i.name == name.upper()]


@dataclass
class Dockerfile:
    """Parsed Dockerfile with per-stage breakdown."""

    path: Optional[Path]
    raw_text: str
    stages: List[Stage]

    @property
    def final_stage(self) -> Stage:
        return self.stages[-1]

    @property
    def is_multi_stage(self) -> bool:
        return len(self.stages) > 1


@dataclass(frozen=True)
class Finding:
    """An optimization opportunity discovered by the analyzer."""

    rule_id: str
    title: str
    severity: FindingSeverity
    line_number: Optional[int]
    stage_index: Optional[int]
    description: str
    recommendation: str
    estimated_savings_mb: float = 0.0


_INSTRUCTION_RE = re.compile(r"^\s*([A-Z]+)\s+(.*?)\s*$")
_FROM_RE = re.compile(r"^\s*FROM\s+([^\s]+)(?:\s+AS\s+([A-Za-z0-9_.-]+))?\s*$", re.IGNORECASE)


class DockerfileParser:
    """Parse a Dockerfile into a Dockerfile + Stage list."""

    KNOWN_INSTRUCTIONS = {
        "FROM", "RUN", "COPY", "ADD", "WORKDIR", "ENV", "ARG",
        "CMD", "ENTRYPOINT", "EXPOSE", "VOLUME", "USER",
        "HEALTHCHECK", "LABEL", "SHELL", "STOPSIGNAL", "ONBUILD",
    }

    def parse_text(self, text: str, path: Optional[Path] = None) -> Dockerfile:
        physical_lines = text.splitlines()
        # Merge continuation lines.
        joined: List[Tuple[int, str]] = []  # (line_number, content)
        buffer: List[str] = []
        first_line: Optional[int] = None
        for idx, line in enumerate(physical_lines, start=1):
            stripped = line.split("#", 1)[0].rstrip()
            if not stripped.strip():
                if buffer:
                    joined.append((first_line or idx, " ".join(buffer)))
                    buffer = []
                    first_line = None
                continue
            if buffer:
                if stripped.endswith("\\"):
                    buffer.append(stripped[:-1].strip())
                else:
                    buffer.append(stripped.strip())
                    joined.append((first_line or idx, " ".join(buffer)))
                    buffer = []
                    first_line = None
            else:
                if stripped.endswith("\\"):
                    buffer.append(stripped[:-1].strip())
                    first_line = idx
                else:
                    joined.append((idx, stripped.strip()))
        if buffer:
            joined.append((first_line or len(physical_lines), " ".join(buffer)))

        stages: List[Stage] = []
        current: Optional[Stage] = None
        for line_no, content in joined:
            from_match = _FROM_RE.match(content)
            if from_match:
                if current is not None:
                    stages.append(current)
                base = from_match.group(1)
                alias = from_match.group(2)
                current = Stage(index=len(stages), base_image=base, alias=alias)
                continue
            if current is None:
                # Skip directives (`# syntax=...`) and stray ARGs above FROM.
                if not content.upper().startswith("ARG"):
                    continue
                # Hoist ARG-before-FROM into a synthetic stage-less context.
                continue
            m = _INSTRUCTION_RE.match(content)
            if not m:
                continue
            name = m.group(1).upper()
            args = m.group(2)
            if name not in self.KNOWN_INSTRUCTIONS:
                continue
            current.instructions.append(Instruction(name=name, args=args, line_number=line_no))
        if current is not None:
            stages.append(current)

        return Dockerfile(path=path, raw_text=text, stages=stages)

    def parse_file(self, path: Path) -> Dockerfile:
        return self.parse_text(Path(path).read_text(), path=Path(path))


class DockerfileAnalyzer:
    """Generate Finding list against a parsed Dockerfile."""

    def analyze(self, dockerfile: Dockerfile) -> List[Finding]:
        findings: List[Finding] = []
        findings.extend(self._single_stage_check(dockerfile))
        findings.extend(self._build_tools_in_final_stage(dockerfile))
        findings.extend(self._layer_ordering(dockerfile))
        findings.extend(self._large_artifact_hints(dockerfile))
        findings.extend(self._suboptimal_base_image(dockerfile))
        findings.extend(self._missing_user(dockerfile))
        findings.extend(self._apt_without_cleanup(dockerfile))
        return sorted(findings, key=lambda f: (-_severity_order(f.severity), f.rule_id))

    # -- individual checks ---------------------------------------------

    def _single_stage_check(self, df: Dockerfile) -> List[Finding]:
        if df.is_multi_stage:
            return []
        # Heuristic: if the single stage installs any BUILD_TOOL, it
        # would benefit from a multi-stage layout.
        runs = df.final_stage.get("RUN")
        if any(_uses_build_tools(r.args) for r in runs):
            return [Finding(
                rule_id="single_stage_with_build_tools",
                title="Single-stage Dockerfile with build tools in runtime",
                severity=FindingSeverity.HIGH,
                line_number=runs[0].line_number,
                stage_index=df.final_stage.index,
                description=(
                    "The image is a single stage that installs build tools "
                    "(compilers, package managers) and runs the application "
                    "from the same layer set. Build tools and intermediate "
                    "artifacts ship to production."
                ),
                recommendation=(
                    "Split into two stages: a builder stage with build tools "
                    "and a slim runtime stage that copies only the built "
                    "artifacts via COPY --from=builder."
                ),
                estimated_savings_mb=400.0,
            )]
        return []

    def _build_tools_in_final_stage(self, df: Dockerfile) -> List[Finding]:
        if not df.is_multi_stage:
            return []
        runs = df.final_stage.get("RUN")
        return [
            Finding(
                rule_id="build_tools_in_final_stage",
                title=f"Build tools installed in final stage ({_match_tools(r.args)})",
                severity=FindingSeverity.HIGH,
                line_number=r.line_number,
                stage_index=df.final_stage.index,
                description=(
                    "The final stage installs build tools that don't belong "
                    "in a runtime image."
                ),
                recommendation=(
                    "Move tool installation to the builder stage and copy "
                    "only the artifact into the final stage."
                ),
                estimated_savings_mb=200.0,
            )
            for r in runs if _uses_build_tools(r.args)
        ]

    def _layer_ordering(self, df: Dockerfile) -> List[Finding]:
        # If a COPY of source code appears before installing dependencies,
        # cache invalidates on every code change.
        findings: List[Finding] = []
        for stage in df.stages:
            seen_app_copy: Optional[Instruction] = None
            for instr in stage.instructions:
                if instr.name == "COPY" and _looks_like_app_copy(instr.args):
                    seen_app_copy = instr
                if instr.name == "RUN" and _looks_like_dependency_install(instr.args):
                    if seen_app_copy is not None:
                        findings.append(Finding(
                            rule_id="cache_unfriendly_layer_order",
                            title="Dependencies installed after copying app source",
                            severity=FindingSeverity.MEDIUM,
                            line_number=seen_app_copy.line_number,
                            stage_index=stage.index,
                            description=(
                                "Source code is copied before the dependency install "
                                "step. Any source change invalidates the dependency "
                                "layer cache."
                            ),
                            recommendation=(
                                "COPY only the manifest (requirements.txt / package.json / "
                                "pom.xml) first, run the install, then COPY the rest "
                                "of the source."
                            ),
                        ))
                        break  # one per stage is enough
        return findings

    def _large_artifact_hints(self, df: Dockerfile) -> List[Finding]:
        findings: List[Finding] = []
        for stage in df.stages:
            for instr in stage.instructions:
                if instr.name not in {"COPY", "ADD", "RUN"}:
                    continue
                for hint in LARGE_ARTIFACT_HINTS:
                    if hint in instr.args:
                        findings.append(Finding(
                            rule_id="large_intermediate_artifact",
                            title=f"Possible large artifact: {hint}",
                            severity=FindingSeverity.LOW,
                            line_number=instr.line_number,
                            stage_index=stage.index,
                            description=(
                                f"The instruction references {hint!r} which often "
                                "represents a large directory or archive that "
                                "should not survive into the final image."
                            ),
                            recommendation=(
                                f"Use a .dockerignore entry for {hint!r} or remove it "
                                "in a follow-up RUN within the same layer."
                            ),
                            estimated_savings_mb=50.0,
                        ))
                        break
        return findings

    def _suboptimal_base_image(self, df: Dockerfile) -> List[Finding]:
        final = df.final_stage
        base = final.base_image
        # Family aliases for base-image detection.
        family_aliases = {
            "python": ("python",),
            "node": ("node",),
            "java": ("java", "openjdk", "temurin"),
        }
        for family, candidates in PREFERRED_BASE_IMAGES.items():
            aliases = family_aliases.get(family, (family,))
            if any(alias in base.lower() for alias in aliases) and not any(
                re.match(pat, base) for _, pat in candidates
            ):
                preferred = ", ".join(c[0] for c in candidates)
                return [Finding(
                    rule_id="suboptimal_base_image",
                    title=f"Base image {base!r} is not a slim/distroless variant",
                    severity=FindingSeverity.MEDIUM,
                    line_number=None,
                    stage_index=final.index,
                    description=(
                        f"The final stage uses {base!r}. Slim or distroless "
                        f"variants reduce image size by 60-90% and shrink the "
                        "attack surface."
                    ),
                    recommendation=f"Switch to one of: {preferred}.",
                    estimated_savings_mb=600.0,
                )]
        return []

    def _missing_user(self, df: Dockerfile) -> List[Finding]:
        final = df.final_stage
        if not final.get("USER"):
            return [Finding(
                rule_id="no_user_directive",
                title="Image runs as root",
                severity=FindingSeverity.MEDIUM,
                line_number=None,
                stage_index=final.index,
                description="The final stage has no USER directive; the image runs as root.",
                recommendation="Add `USER appuser` after creating a non-root user.",
            )]
        return []

    def _apt_without_cleanup(self, df: Dockerfile) -> List[Finding]:
        findings: List[Finding] = []
        for stage in df.stages:
            for instr in stage.get("RUN"):
                if "apt-get install" in instr.args and "apt-get clean" not in instr.args \
                        and "rm -rf /var/lib/apt/lists" not in instr.args:
                    findings.append(Finding(
                        rule_id="apt_without_cleanup",
                        title="apt-get install without cache cleanup",
                        severity=FindingSeverity.LOW,
                        line_number=instr.line_number,
                        stage_index=stage.index,
                        description=(
                            "apt-get installs without removing /var/lib/apt/lists "
                            "leave ~30-80MB of cache behind in the layer."
                        ),
                        recommendation=(
                            "Append `&& rm -rf /var/lib/apt/lists/*` to the same "
                            "RUN to keep the cleanup in the same layer."
                        ),
                        estimated_savings_mb=50.0,
                    ))
        return findings


# -- helpers -----------------------------------------------------------


def _severity_order(s: FindingSeverity) -> int:
    return {
        FindingSeverity.INFO: 0,
        FindingSeverity.LOW: 1,
        FindingSeverity.MEDIUM: 2,
        FindingSeverity.HIGH: 3,
    }[s]


def _uses_build_tools(args: str) -> bool:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_+-]+", args.lower())
    return any(t in BUILD_TOOLS for t in tokens)


def _match_tools(args: str) -> str:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_+-]+", args.lower())
    found = sorted({t for t in tokens if t in BUILD_TOOLS})
    return ", ".join(found) if found else "build tools"


def _looks_like_app_copy(args: str) -> bool:
    parts = args.split()
    if len(parts) < 2:
        return False
    src = parts[0].strip("\"'")
    # Heuristic: "." or "./..." but not manifest-style filenames.
    if src in {".", "./"}:
        return True
    manifest_files = {
        "requirements.txt", "pyproject.toml", "package.json", "package-lock.json",
        "yarn.lock", "pom.xml", "build.gradle", "go.mod", "go.sum", "Cargo.toml",
    }
    return src not in manifest_files and not src.endswith((".txt", ".lock", ".toml"))


def _looks_like_dependency_install(args: str) -> bool:
    triggers = ("pip install", "npm install", "yarn install", "mvn install",
                "gradle install", "go mod download", "cargo fetch")
    return any(t in args for t in triggers)

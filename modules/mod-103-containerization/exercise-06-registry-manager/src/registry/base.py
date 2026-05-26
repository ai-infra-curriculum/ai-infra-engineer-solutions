"""
Base abstractions for container registries.

The Registry ABC defines the operations needed by sync, promotion,
retention, and audit. Concrete subclasses for ECR/GCR/ACR plug in their
own cloud SDK calls; an InMemoryRegistry (declared here) gives the rest
of the system something to integrate with in tests and demos that don't
have cloud credentials.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional


class RegistryError(Exception):
    """Raised when a registry operation fails."""


@dataclass(frozen=True)
class ImageManifest:
    """OCI image manifest summary."""

    digest: str  # sha256:...
    size_bytes: int
    media_type: str = "application/vnd.docker.distribution.manifest.v2+json"
    layers: int = 1
    architecture: str = "amd64"
    os: str = "linux"


@dataclass
class ImageTag:
    """A tag pointing at a manifest within a repository."""

    repository: str
    tag: str
    manifest: ImageManifest
    pushed_at: datetime
    last_pulled_at: Optional[datetime] = None
    pull_count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def reference(self) -> str:
        return f"{self.repository}:{self.tag}"

    @property
    def age(self) -> timedelta:
        return datetime.now(timezone.utc) - self.pushed_at


@dataclass(frozen=True)
class RetentionRule:
    """Declarative rule for which tags to keep / delete."""

    repository_pattern: str  # supports "*" for "any repo"
    keep_min_count: int = 5  # always keep at least N tags per repository
    max_age_days: Optional[int] = None
    max_pulls_threshold: Optional[int] = None  # delete if pull_count <= threshold
    protect_tags: List[str] = field(default_factory=lambda: ["latest", "stable", "prod"])

    def matches_repository(self, repo: str) -> bool:
        if self.repository_pattern == "*":
            return True
        # Simple glob-ish: support trailing "*".
        if self.repository_pattern.endswith("*"):
            prefix = self.repository_pattern[:-1]
            return repo.startswith(prefix)
        return repo == self.repository_pattern


class Registry(ABC):
    """Abstract container registry."""

    provider: str = "base"

    def __init__(self, *, name: str, region: str):
        self.name = name
        self.region = region

    @abstractmethod
    def list_repositories(self) -> List[str]: ...

    @abstractmethod
    def list_tags(self, repository: str) -> List[ImageTag]: ...

    @abstractmethod
    def get_tag(self, repository: str, tag: str) -> ImageTag: ...

    @abstractmethod
    def push(self, repository: str, tag: str, manifest: ImageManifest) -> ImageTag: ...

    @abstractmethod
    def delete_tag(self, repository: str, tag: str) -> None: ...

    @abstractmethod
    def record_pull(self, repository: str, tag: str) -> ImageTag: ...

    def copy_to(
        self,
        destination: "Registry",
        repository: str,
        tag: str,
    ) -> ImageTag:
        """Copy a tag to another registry (preserving digest + size)."""
        source = self.get_tag(repository, tag)
        return destination.push(source.repository, source.tag, source.manifest)


class InMemoryRegistry(Registry):
    """Concrete in-memory registry suitable for tests + demos."""

    provider = "memory"

    def __init__(self, *, name: str = "memory", region: str = "local"):
        super().__init__(name=name, region=region)
        self._repositories: Dict[str, Dict[str, ImageTag]] = {}

    def list_repositories(self) -> List[str]:
        return sorted(self._repositories.keys())

    def list_tags(self, repository: str) -> List[ImageTag]:
        if repository not in self._repositories:
            return []
        return sorted(
            self._repositories[repository].values(),
            key=lambda t: t.pushed_at,
            reverse=True,
        )

    def get_tag(self, repository: str, tag: str) -> ImageTag:
        try:
            return self._repositories[repository][tag]
        except KeyError as exc:
            raise RegistryError(f"Tag {repository}:{tag} not found in {self.name}") from exc

    def push(self, repository: str, tag: str, manifest: ImageManifest) -> ImageTag:
        tags = self._repositories.setdefault(repository, {})
        record = ImageTag(
            repository=repository,
            tag=tag,
            manifest=manifest,
            pushed_at=datetime.now(timezone.utc),
        )
        tags[tag] = record
        return record

    def delete_tag(self, repository: str, tag: str) -> None:
        try:
            del self._repositories[repository][tag]
        except KeyError as exc:
            raise RegistryError(f"Tag {repository}:{tag} not found") from exc
        if not self._repositories[repository]:
            del self._repositories[repository]

    def record_pull(self, repository: str, tag: str) -> ImageTag:
        record = self.get_tag(repository, tag)
        record.pull_count += 1
        record.last_pulled_at = datetime.now(timezone.utc)
        return record

    # -- testing convenience -------------------------------------------

    def seed(
        self,
        repository: str,
        tag: str,
        *,
        pushed_at: Optional[datetime] = None,
        pull_count: int = 0,
        size_bytes: int = 100 * 1024 * 1024,
        labels: Optional[Dict[str, str]] = None,
    ) -> ImageTag:
        digest = "sha256:" + hashlib.sha256(f"{repository}:{tag}".encode()).hexdigest()
        manifest = ImageManifest(digest=digest, size_bytes=size_bytes)
        record = ImageTag(
            repository=repository,
            tag=tag,
            manifest=manifest,
            pushed_at=pushed_at or datetime.now(timezone.utc),
            pull_count=pull_count,
            labels=labels or {},
        )
        self._repositories.setdefault(repository, {})[tag] = record
        return record

"""
Google Container Registry (GCR / Artifact Registry) implementation.

Concrete Registry subclass with an InMemoryRegistry default path and a
hook for the gcloud Container Analysis / Artifact Registry client.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .base import InMemoryRegistry


class GCRRegistry(InMemoryRegistry):
    """GCP Artifact / Container Registry."""

    provider = "gcr"

    def __init__(
        self,
        *,
        project_id: str,
        region: str = "us",
        client: Optional[Any] = None,
    ):
        # gcr.io for legacy, <region>-docker.pkg.dev for Artifact Registry.
        host = f"{region}.gcr.io" if region in {"us", "eu", "asia"} else f"{region}-docker.pkg.dev"
        super().__init__(name=f"{host}/{project_id}", region=region)
        self.project_id = project_id
        self._client = client

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def list_repositories(self) -> List[str]:
        if self.is_live:
            return self._list_repositories_live()
        return super().list_repositories()

    def _list_repositories_live(self) -> List[str]:
        # Live path queries the Artifact Registry list_repositories API.
        # Consumers wire this in their integration tests; the default
        # is the in-memory implementation that backs CI runs.
        return [r.name.split("/")[-1] for r in self._client.list_repositories(parent=f"projects/{self.project_id}/locations/{self.region}")]

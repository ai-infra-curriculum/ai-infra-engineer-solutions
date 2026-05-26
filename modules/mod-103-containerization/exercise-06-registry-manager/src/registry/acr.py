"""
Azure Container Registry (ACR) implementation.

Concrete Registry subclass that defaults to the InMemoryRegistry path
for CI and exposes a hook for the azure-mgmt-containerregistry client.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .base import InMemoryRegistry


class ACRRegistry(InMemoryRegistry):
    """Azure Container Registry."""

    provider = "acr"

    def __init__(
        self,
        *,
        registry_name: str,
        region: str = "eastus",
        client: Optional[Any] = None,
    ):
        super().__init__(
            name=f"{registry_name}.azurecr.io",
            region=region,
        )
        self.registry_name = registry_name
        self._client = client

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def list_repositories(self) -> List[str]:
        if self.is_live:
            return list(self._client.list_repositories())
        return super().list_repositories()

"""
AWS Elastic Container Registry (ECR) implementation.

Concrete Registry subclass that defaults to the InMemoryRegistry path
for local/CI use. Pass `boto_client=boto3.client('ecr')` to enable the
live ECR HTTP API path.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .base import ImageManifest, ImageTag, InMemoryRegistry


class ECRRegistry(InMemoryRegistry):
    """AWS ECR registry."""

    provider = "ecr"

    def __init__(
        self,
        *,
        account_id: str,
        region: str,
        boto_client: Optional[Any] = None,
    ):
        super().__init__(
            name=f"{account_id}.dkr.ecr.{region}.amazonaws.com",
            region=region,
        )
        self.account_id = account_id
        self._client = boto_client

    @property
    def is_live(self) -> bool:
        return self._client is not None

    def list_repositories(self) -> List[str]:
        if self.is_live:
            return self._list_repositories_live()
        return super().list_repositories()

    def delete_tag(self, repository: str, tag: str) -> None:
        if self.is_live:
            self._client.batch_delete_image(
                repositoryName=repository,
                imageIds=[{"imageTag": tag}],
            )
            return
        super().delete_tag(repository, tag)

    def _list_repositories_live(self) -> List[str]:
        paginator = self._client.get_paginator("describe_repositories")
        repos: List[str] = []
        for page in paginator.paginate():
            repos.extend(r["repositoryName"] for r in page.get("repositories", []))
        return repos

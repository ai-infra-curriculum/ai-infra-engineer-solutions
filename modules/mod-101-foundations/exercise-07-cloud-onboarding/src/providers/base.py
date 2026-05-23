"""Provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Provisioned:
    bucket: str
    iam_principal: str
    creds: dict[str, str]


class Provider(ABC):
    @abstractmethod
    def init(self, user: str, region: str) -> Provisioned: ...
    @abstractmethod
    def status(self, user: str) -> dict: ...
    @abstractmethod
    def rotate_key(self, user: str) -> dict[str, str]: ...
    @abstractmethod
    def destroy(self, user: str) -> None: ...

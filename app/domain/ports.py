from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.domain.models_asset import Alert, AssetSnapshot, DigestContext


@runtime_checkable
class DataPort(Protocol):
    async def fetch(self, ticker: str) -> "AssetSnapshot": ...


@runtime_checkable
class RulePort(Protocol):
    def evaluate(self, snapshot: "AssetSnapshot") -> list["Alert"]: ...


@runtime_checkable
class ScorePort(Protocol):
    def score(self, snapshot: "AssetSnapshot") -> int: ...


@runtime_checkable
class NarratorPort(Protocol):
    async def narrate(self, context: "DigestContext") -> str: ...


@runtime_checkable
class DeliveryPort(Protocol):
    async def send(self, message: str) -> None: ...

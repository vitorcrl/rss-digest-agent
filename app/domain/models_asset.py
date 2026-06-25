from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


@dataclass
class Alert:
    ticker: str
    rule: str
    message: str
    severity: AlertSeverity = AlertSeverity.warning
    value: float | None = None
    threshold: float | None = None


@dataclass
class AssetSnapshot:
    ticker: str
    market: str                  # "BR" | "US"
    date: date
    price: float
    dy_12m: float                # dividend yield 12 meses (%)
    pvp: float                   # preço / valor patrimonial
    vacancia: float | None       # % vacância (fundos tijolo)
    ltv: float | None            # loan-to-value % (fundos papel)
    liquidez: float              # volume médio diário R$
    delta_dy: float = 0.0        # variação DY vs semana anterior
    delta_vacancia: float = 0.0  # variação vacância vs semana anterior
    delta_price: float = 0.0     # variação preço vs dia anterior (%)
    provento_anunciado: float | None = None  # R$/cota anunciado hoje


@dataclass
class DigestContext:
    date: date
    snapshots: list[AssetSnapshot]
    alerts: list[Alert]
    scores: dict[str, int] = field(default_factory=dict)  # ticker → score

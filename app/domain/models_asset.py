# Objetos de valor internos ao pipeline — não são tabelas do banco.
# Usamos dataclasses puras (sem SQLAlchemy) porque esses dados vivem só
# em memória durante a execução do pipeline. O ORM fica em models_fii.py.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class AlertSeverity(str, Enum):
    """Gravidade de um alerta — usada pelo narrator para formatar a mensagem."""

    info = "info"          # evento neutro, ex: provento anunciado
    warning = "warning"    # indicador fora do threshold, mas não crítico
    critical = "critical"  # situação que merece atenção imediata (ex: queda >5%)


@dataclass
class Alert:
    """
    Representa um alerta disparado por uma regra para um ativo específico.
    O narrator só recebe objetos Alert — nunca o snapshot bruto inteiro,
    para manter o contexto enviado à Claude o menor possível.
    """

    ticker: str            # código do fundo, ex: "MXRF11"
    rule: str              # nome da regra que disparou, ex: "dy_falling"
    message: str           # mensagem legível, ex: "DY caindo: 10,2% (era 11,5%)"
    severity: AlertSeverity = AlertSeverity.warning
    value: float | None = None      # valor atual do indicador
    threshold: float | None = None  # limite configurado que foi violado


@dataclass
class AssetSnapshot:
    """
    Fotografia dos indicadores de um ativo em uma data específica.
    Produzido pelo DataPort (ex: BrapiDataAdapter) e consumido pelo
    RulePort e ScorePort. Os campos delta_* são calculados pelo pipeline
    comparando com o snapshot da semana anterior salvo no banco.
    """

    ticker: str    # código do ativo, ex: "KNCR11"
    market: str    # mercado de origem: "BR" para FIIs, "US" para REITs
    date: date     # data de referência do snapshot
    price: float   # cotação de fechamento

    # Indicadores fundamentalistas
    dy_12m: float         # dividend yield dos últimos 12 meses em %
    pvp: float            # preço dividido pelo valor patrimonial (P/VP)
    vacancia: float | None   # % de área desocupada (só fundos de tijolo)
    ltv: float | None        # loan-to-value em % (só fundos de papel)
    liquidez: float          # volume médio diário negociado em R$

    # Deltas calculados pelo pipeline vs semana/dia anterior
    delta_dy: float = 0.0         # variação do DY em pontos percentuais
    delta_vacancia: float = 0.0   # variação da vacância em pontos percentuais
    delta_price: float = 0.0      # variação percentual do preço em 1 dia

    # Evento pontual: provento anunciado hoje (None se não houve anúncio)
    provento_anunciado: float | None = None  # valor em R$ por cota


@dataclass
class DigestContext:
    """
    Tudo que o NarratorPort precisa para redigir o digest do dia.
    O pipeline monta este objeto após coletar snapshots, calcular deltas,
    aplicar regras e calcular scores — aí passa para o narrator.
    """

    date: date                        # data do digest
    snapshots: list[AssetSnapshot]    # todos os ativos da watchlist
    alerts: list[Alert]               # apenas os alertas disparados
    scores: dict[str, int] = field(default_factory=dict)  # ticker → score 0–100

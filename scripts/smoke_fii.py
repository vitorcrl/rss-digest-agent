"""
Smoke test do pipeline de FIIs — sem Claude, sem banco.

Busca dados reais da brapi.dev para os tickers da watchlist,
aplica as regras e envia a mensagem formatada via Telegram.

Uso:
    BRAPI_TOKEN=seu_token TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
        python scripts/smoke_fii.py

    Ou com .env configurado:
        python scripts/smoke_fii.py
"""

import asyncio
import logging
import sys
from pathlib import Path

import httpx

# Garante que o projeto está no PYTHONPATH quando rodado direto
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.adapters.data.brapi_adapter import BrapiDataAdapter, BrapiError
from app.adapters.delivery.telegram_adapter import TelegramAdapter, TelegramDeliveryError
from app.adapters.narrators.template_narrator import TemplateNarrator
from app.adapters.rules.fii_rule_set import FIIRuleSet
from app.adapters.scoring.weighted_score_engine import WeightedScoreEngine
from app.core.config import get_settings
from app.domain.models_asset import DigestContext
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Posições da carteira — cotas por ticker
PORTFOLIO: dict[str, int] = {
    "MXRF11": 100,
    "KNCR11": 10,
    "CPTS11": 20,
}

# Reserva em caixinha — valor e percentual do CDI
RESERVA_VALOR = 20_000.0
RESERVA_PCT_CDI = 1.10  # 110% do CDI


async def _fetch_selic_diaria() -> float | None:
    """Busca a taxa Selic diária mais recente no Banco Central (série 11)."""
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados/ultimos/1?formato=json"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url)
        return float(r.json()[0]["valor"])
    except Exception as e:
        logger.warning("Não foi possível buscar Selic no BCB: %s", e)
        return None


def _format_reserva(selic_diaria: float | None, valor: float, pct_cdi: float) -> str:
    """Bloco de reserva com estimativa mensal de rendimento."""
    lines = [f"🏦 Reserva (Mercado Pago)  R$ {valor:,.2f}"]
    if selic_diaria is None:
        lines.append("  Selic indisponível no momento")
        return "\n".join(lines)

    # CDI ≈ Selic — BCB série 11 é a taxa Over diária em %
    # Converte taxa diária → mensal: (1 + d/100)^21 - 1  (21 dias úteis/mês)
    taxa_diaria = (selic_diaria / 100) * pct_cdi
    rendimento_mensal = valor * ((1 + taxa_diaria) ** 21 - 1)
    selic_anual = ((1 + selic_diaria / 100) ** 252 - 1) * 100

    lines.append(
        f"  {pct_cdi * 100:.0f}% CDI (Selic {selic_anual:.2f}% a.a.)"
        f"  ≈ R$ {rendimento_mensal:,.2f}/mês"
    )
    return "\n".join(lines)


def _format_portfolio_summary(snapshots: list, portfolio: dict[str, int]) -> str:
    """Monta o bloco de carteira com valor total e variação do dia em reais."""
    lines = ["💼 Carteira"]
    total_value = 0.0
    total_variation = 0.0

    for snap in snapshots:
        cotas = portfolio.get(snap.ticker, 0)
        if cotas == 0:
            continue
        valor = snap.price * cotas
        variacao_rs = valor * (snap.delta_price / 100)
        total_value += valor
        total_variation += variacao_rs
        sign = "+" if variacao_rs >= 0 else ""
        lines.append(
            f"  {snap.ticker} ({cotas} cotas)  R$ {valor:,.2f}  {sign}R$ {variacao_rs:,.2f}"
        )

    sign_total = "+" if total_variation >= 0 else ""
    lines.append(f"  Total  R$ {total_value:,.2f}  {sign_total}R$ {total_variation:,.2f} hoje")
    return "\n".join(lines)


async def main() -> None:
    settings = get_settings()
    tickers = settings.fii_watchlist_tickers

    if not tickers:
        logger.error("FII_WATCHLIST está vazia — configure no .env")
        sys.exit(1)

    if not settings.BRAPI_TOKEN:
        logger.warning("BRAPI_TOKEN vazio — a brapi.dev pode rejeitar a requisição")

    logger.info("Buscando dados para: %s", ", ".join(tickers))

    data_adapter = BrapiDataAdapter(base_url=settings.BRAPI_BASE_URL, token=settings.BRAPI_TOKEN)
    rules = FIIRuleSet(settings=settings)
    scorer = WeightedScoreEngine()

    snapshots = []
    all_alerts = []
    scores = {}

    for ticker in tickers:
        try:
            snap = await data_adapter.fetch(ticker)
            logger.info("  %s → preço R$ %.2f | DY %.1f%% | P/VP %.2f", ticker, snap.price, snap.dy_12m, snap.pvp)
        except BrapiError as e:
            logger.warning("  %s → falha na brapi: %s", ticker, e)
            continue

        alerts = rules.evaluate(snap)
        scores[ticker] = scorer.score(snap)
        snapshots.append(snap)
        all_alerts.extend(alerts)

        for alert in alerts:
            logger.info("    ⚠ [%s] %s", alert.rule, alert.message)

    logger.info("")
    logger.info("Total: %d fundos | %d alertas", len(snapshots), len(all_alerts))

    context = DigestContext(
        date=date.today(),
        snapshots=snapshots,
        alerts=all_alerts,
        scores=scores,
    )

    narrator = TemplateNarrator()
    message = await narrator.narrate(context)

    portfolio_block = _format_portfolio_summary(snapshots, PORTFOLIO)

    selic = await _fetch_selic_diaria()
    reserva_block = _format_reserva(selic, RESERVA_VALOR, RESERVA_PCT_CDI)

    message = message + "\n\n" + portfolio_block + "\n\n" + reserva_block

    logger.info("\n--- Mensagem que será enviada ---")
    print(message)
    logger.info("---")

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados — pulando envio")
        return

    try:
        delivery = TelegramAdapter(settings=settings)
        await delivery.send(message)
        logger.info("✅ Mensagem enviada com sucesso!")
    except TelegramDeliveryError as e:
        logger.error("❌ Falha no Telegram: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
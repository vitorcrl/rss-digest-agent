# Narrator principal do pipeline — só chama a Claude API quando há alertas.
# Implementa NarratorPort.
#
# Filosofia de custo zero:
#   - DigestContext.total_alerts == 0  → retorna mensagem estática (zero tokens)
#   - DigestContext.total_alerts  > 0  → chama claude-haiku-4-5 para narrar
#
# Se a chamada à API falhar por qualquer motivo (timeout, quota, etc.),
# o TemplateNarrator entra como fallback para garantir que o Telegram
# sempre receba uma mensagem, mesmo que sem a narrativa gerada pela Claude.

import logging

import anthropic

from app.adapters.narrators.template_narrator import TemplateNarrator
from app.core.config import get_settings
from app.domain.models_asset import Alert, AlertSeverity, DigestContext

logger = logging.getLogger(__name__)

# Modelo mais barato da família Claude — ideal para narração de texto curto.
# Preço (Jun/2026): $1.00 input / $5.00 output por 1M tokens.
_MODEL = "claude-haiku-4-5"

# Limita a resposta a ~400 tokens — suficiente para um digest diário conciso.
_MAX_TOKENS = 512

# Ícones por severity para incluir no prompt (ajuda a Claude entender urgência)
_ICON = {
    AlertSeverity.critical: "🚨",
    AlertSeverity.warning: "⚠️",
    AlertSeverity.info: "🔔",
}


class ClaudeHaikuNarrator:
    """
    Narrator que usa claude-haiku-4-5 para transformar alertas técnicos em
    texto natural para o Telegram. Implementa NarratorPort.

    Custo: zero tokens quando não há alertas.
    Fallback: TemplateNarrator quando a API está indisponível.
    """

    def __init__(self, api_key: str | None = None) -> None:
        # Aceita api_key injetada (útil nos testes) ou lê de Settings.
        # O cliente AsyncAnthropic é criado na primeira chamada para evitar
        # import-time de Settings (que quebraria testes sem .env).
        self._api_key = api_key
        self._client: anthropic.AsyncAnthropic | None = None
        self._fallback = TemplateNarrator()

    def _get_client(self) -> anthropic.AsyncAnthropic:
        # Lazy init — só cria o cliente quando narrate() é chamado pela primeira vez
        if self._client is None:
            key = self._api_key or get_settings().ANTHROPIC_API_KEY
            self._client = anthropic.AsyncAnthropic(api_key=key)
        return self._client

    async def narrate(self, context: DigestContext) -> str:
        # Caminho zero tokens — nem alertas nem eventos informativos (ex: proventos).
        # Checar len(alerts) e não total_alerts porque total_alerts ignora severity=info.
        # Se checarmos só total_alerts==0, um provento anunciado seria silenciado.
        if not context.alerts:
            logger.info(
                "ClaudeHaikuNarrator: no alerts for %d assets on %s — skipping API call",
                context.watchlist_size,
                context.date,
            )
            date_br = context.date.strftime("%d/%m/%Y")
            return (
                f"✅ FIIs — {date_br}\n"
                f"Todos os {context.watchlist_size} fundos dentro dos parâmetros."
            )

        logger.info(
            "ClaudeHaikuNarrator: calling %s for %d alerts on %s",
            _MODEL,
            context.total_alerts,
            context.date,
        )

        try:
            prompt = _build_prompt(context)
            client = self._get_client()

            response = await client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extrai o texto do primeiro bloco de conteúdo
            text = response.content[0].text.strip()

            logger.info(
                "ClaudeHaikuNarrator: received %d chars, stop_reason=%s",
                len(text),
                response.stop_reason,
            )

            return text

        except anthropic.APIStatusError as exc:
            # Erros de quota, autenticação ou modelo indisponível
            logger.warning(
                "ClaudeHaikuNarrator: API error %s — falling back to TemplateNarrator",
                exc.status_code,
            )
        except anthropic.APIConnectionError:
            logger.warning(
                "ClaudeHaikuNarrator: connection error — falling back to TemplateNarrator"
            )
        except Exception:
            logger.exception(
                "ClaudeHaikuNarrator: unexpected error — falling back to TemplateNarrator"
            )

        # Fallback: mesmo sem Claude, o Telegram recebe uma mensagem estruturada
        return await self._fallback.narrate(context)


# ---------------------------------------------------------------------------
# Funções auxiliares de construção do prompt
# ---------------------------------------------------------------------------


def _build_prompt(context: DigestContext) -> str:
    """
    Monta o prompt para a Claude com o contexto completo do digest.

    O prompt usa a saída do TemplateNarrator como contexto estruturado para que
    a Claude possa narrar os mesmos dados de forma mais natural e personalizada,
    sem precisar reinterpretar o DigestContext do zero.
    """
    date_br = context.date.strftime("%d/%m/%Y")

    # Seção de alertas agrupados por ticker
    alerts_section = _format_alerts_for_prompt(context.alerts)

    return f"""Você é um analista de fundos imobiliários (FIIs) brasileiros que envia um resumo diário pelo Telegram para um investidor individual.

Data do digest: {date_br}
Watchlist: {context.watchlist_size} fundos monitorados
Total de alertas: {context.total_alerts}
Total de eventos informativos: {context.total_events}

Alertas do dia:
{alerts_section}

Escreva um resumo conciso e direto para o Telegram com:
1. Uma linha de cabeçalho com a data e número de alertas
2. Para cada fundo com alerta, explique brevemente o que o dado significa para o investidor
3. Se houver alertas críticos (🚨), destaque-os primeiro
4. Um rodapé com: Watchlist: {context.watchlist_size} fundos | {context.total_alerts} alertas | {context.total_events} eventos

Use linguagem simples e objetiva. Evite jargões técnicos excessivos. O investidor quer saber o que fazer, não só o que aconteceu.
Máximo de {_MAX_TOKENS} tokens na resposta."""


def _format_alerts_for_prompt(alerts: list[Alert]) -> str:
    """
    Formata a lista de alertas como texto estruturado para o prompt.
    Agrupa por ticker e ordena críticos primeiro.
    """
    if not alerts:
        return "(sem alertas)"

    # Ordena: críticos → warnings → info
    _severity_order = {
        AlertSeverity.critical: 0,
        AlertSeverity.warning: 1,
        AlertSeverity.info: 2,
    }
    sorted_alerts = sorted(alerts, key=lambda a: (_severity_order[a.severity], a.ticker))

    lines: list[str] = []
    for alert in sorted_alerts:
        icon = _ICON[alert.severity]
        streak_note = f" (há {alert.streak} semanas consecutivas)" if alert.streak > 1 else ""
        lines.append(f"{icon} {alert.ticker} [{alert.rule}]: {alert.message}{streak_note}")

    return "\n".join(lines)

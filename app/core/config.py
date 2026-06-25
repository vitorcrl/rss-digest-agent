from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Banco de dados ---
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/digest_db"

    # --- Claude API (Parte 1 — RSS digest) ---
    ANTHROPIC_API_KEY: str = ""
    AI_RELEVANCE_MODEL: str = "claude-haiku-4-5-20251001"
    AI_SUMMARY_MODEL: str = "claude-sonnet-4-6"
    AI_MIN_RELEVANCE_SCORE: int = 6
    AI_MAX_ARTICLES_PER_DIGEST: int = 10

    # --- Delivery RSS (Parte 1) ---
    DELIVERY_WEBHOOK_URL: str = ""
    DELIVERY_RETRY_ATTEMPTS: int = 3

    # --- Scheduler RSS (Parte 1) ---
    DIGEST_CRON_HOUR: int = 7
    DIGEST_CRON_TIMEZONE: str = "America/Sao_Paulo"

    # --- Telegram (Parte 2 — FIIs) ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # --- brapi.dev (fonte de dados FIIs BR) ---
    # Token gratuito disponível em https://brapi.dev
    BRAPI_TOKEN: str = ""
    BRAPI_BASE_URL: str = "https://brapi.dev/api"

    # --- Watchlist e orçamento FIIs ---
    # Lista de tickers separados por vírgula, ex: "KNCR11,MXRF11,HSML11"
    FII_WATCHLIST: str = "KNCR11,MXRF11,HSML11,BRCO11,LVBI11"
    FII_WEEKLY_BUDGET: float = 500.00       # aporte fixo semanal em R$
    FII_REINVEST_PROVENTOS: bool = True     # somar proventos ao orçamento?
    FII_CRON_HOUR: int = 10                 # hora de execução diária (Brasília)

    # --- Thresholds das regras de FIIs (todos opcionais — defaults abaixo) ---
    FII_MIN_DY: float = 8.0           # DY 12m mínimo aceitável em %
    FII_MAX_PVP: float = 1.15         # P/VP máximo antes de considerar caro
    FII_PVP_DISCOUNT: float = 0.80    # P/VP abaixo disso é oportunidade de desconto
    FII_MAX_VACANCIA: float = 15.0    # vacância máxima para fundos tijolo em %
    FII_MAX_LTV: float = 70.0         # LTV máximo para fundos papel em %
    FII_MIN_LIQUIDEZ: float = 500_000 # liquidez diária mínima em R$
    FII_MAX_PRICE_DROP: float = 5.0   # queda máxima de preço em 1 dia em %
    FII_MIN_DELTA_DY: float = -1.0    # queda de DY em 7 dias que dispara alerta

    @property
    def fii_watchlist_tickers(self) -> list[str]:
        """Converte a string "KNCR11,MXRF11" em lista ["KNCR11", "MXRF11"]."""
        return [t.strip().upper() for t in self.FII_WATCHLIST.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache garante que o .env é lido uma única vez em toda a execução.
    # Nos testes, basta chamar get_settings.cache_clear() para resetar entre casos.
    # Evita o problema de `settings = Settings()` no topo do módulo, que executa
    # em import time e quebra testes que rodam sem .env configurado.
    return Settings()


# Atalho para código que já usava `from app.core.config import settings`
# sem precisar refatorar nada — aponta para a instância cacheada.
settings = get_settings()

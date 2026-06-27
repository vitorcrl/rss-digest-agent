import httpx

from app.core.config import Settings, get_settings


class TelegramDeliveryError(Exception):
    pass


class TelegramAdapter:
    """Implementa DeliveryPort — envia mensagem para um chat Telegram via Bot API."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self._token = cfg.TELEGRAM_BOT_TOKEN
        self._chat_id = cfg.TELEGRAM_CHAT_ID
        self._base_url = f"https://api.telegram.org/bot{self._token}"

    async def send(self, message: str) -> None:
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            raise TelegramDeliveryError(
                f"Telegram API retornou {response.status_code}: {response.text}"
            )

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.delivery.telegram_adapter import TelegramAdapter, TelegramDeliveryError
from app.core.config import Settings


def make_settings(**kwargs) -> Settings:
    defaults = dict(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHAT_ID="123456789",
    )
    defaults.update(kwargs)
    return Settings(**defaults)


@pytest.fixture
def adapter():
    return TelegramAdapter(settings=make_settings())


@pytest.fixture
def mock_httpx():
    with patch("app.adapters.delivery.telegram_adapter.httpx.AsyncClient") as mock_cls:
        client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client


class TestTelegramAdapterSend:
    async def test_sends_message_to_correct_url(self, adapter, mock_httpx):
        response = MagicMock()
        response.status_code = 200
        mock_httpx.post = AsyncMock(return_value=response)

        await adapter.send("Olá, mundo!")

        call_url = mock_httpx.post.call_args.args[0]
        assert "sendMessage" in call_url
        assert "test-token" in call_url

    async def test_sends_correct_chat_id(self, adapter, mock_httpx):
        response = MagicMock()
        response.status_code = 200
        mock_httpx.post = AsyncMock(return_value=response)

        await adapter.send("Olá!")

        payload = mock_httpx.post.call_args.kwargs["json"]
        assert payload["chat_id"] == "123456789"

    async def test_sends_message_text(self, adapter, mock_httpx):
        response = MagicMock()
        response.status_code = 200
        mock_httpx.post = AsyncMock(return_value=response)

        await adapter.send("Mensagem de teste")

        payload = mock_httpx.post.call_args.kwargs["json"]
        assert payload["text"] == "Mensagem de teste"

    async def test_uses_markdown_parse_mode(self, adapter, mock_httpx):
        response = MagicMock()
        response.status_code = 200
        mock_httpx.post = AsyncMock(return_value=response)

        await adapter.send("*negrito*")

        payload = mock_httpx.post.call_args.kwargs["json"]
        assert payload["parse_mode"] == "Markdown"

    async def test_raises_on_non_200_status(self, adapter, mock_httpx):
        response = MagicMock()
        response.status_code = 400
        response.text = "Bad Request"
        mock_httpx.post = AsyncMock(return_value=response)

        with pytest.raises(TelegramDeliveryError):
            await adapter.send("Mensagem")

    async def test_error_message_includes_status_code(self, adapter, mock_httpx):
        response = MagicMock()
        response.status_code = 429
        response.text = "Too Many Requests"
        mock_httpx.post = AsyncMock(return_value=response)

        with pytest.raises(TelegramDeliveryError, match="429"):
            await adapter.send("Mensagem")

    async def test_implements_delivery_port(self):
        from app.domain.ports import DeliveryPort
        assert isinstance(TelegramAdapter(settings=make_settings()), DeliveryPort)

    async def test_builds_url_from_token(self):
        adapter = TelegramAdapter(settings=make_settings(TELEGRAM_BOT_TOKEN="meu-token"))
        assert "meu-token" in adapter._base_url

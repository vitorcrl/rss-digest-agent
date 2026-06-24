import pytest

from app.services.ai_service import AIParseError, AIService
from tests.conftest import make_claude_response


@pytest.fixture
def service(mock_anthropic_client) -> AIService:
    return AIService()


class TestEvaluateRelevance:
    async def test_returns_scores_for_all_titles(self, service, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            '[{"index": 0, "score": 9}, {"index": 1, "score": 2}]'
        )
        scores, tokens = await service.evaluate_relevance(["Article A", "Article B"])

        assert scores == [9, 2]
        assert tokens == 150

    async def test_returns_empty_list_for_no_titles(self, service):
        scores, tokens = await service.evaluate_relevance([])
        assert scores == []
        assert tokens == 0

    async def test_raises_on_malformed_json(self, service, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            "not a json response"
        )
        with pytest.raises(AIParseError):
            await service.evaluate_relevance(["Article A"])

    async def test_defaults_missing_index_to_zero(self, service, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            '[{"index": 0, "score": 8}]'
        )
        scores, _ = await service.evaluate_relevance(["Article A", "Article B"])

        assert scores[0] == 8
        assert scores[1] == 0

    async def test_ignores_out_of_range_indexes(self, service, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            '[{"index": 99, "score": 10}]'
        )
        scores, _ = await service.evaluate_relevance(["Article A"])
        assert scores == [0]

    async def test_uses_relevance_model(self, service, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            '[{"index": 0, "score": 5}]'
        )
        await service.evaluate_relevance(["Article A"])

        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        assert "haiku" in call_kwargs["model"]

    async def test_token_count_is_sum_of_input_and_output(self, service, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            '[{"index": 0, "score": 7}]', input_tokens=200, output_tokens=80
        )
        _, tokens = await service.evaluate_relevance(["Article A"])
        assert tokens == 280


class TestSummarize:
    async def test_returns_summary_and_token_count(self, service, mock_anthropic_client, sample_article):
        mock_anthropic_client.messages.create.return_value = make_claude_response(
            "Resumo do artigo em português.", input_tokens=150, output_tokens=40
        )
        summary, tokens = await service.summarize(sample_article)

        assert summary == "Resumo do artigo em português."
        assert tokens == 190

    async def test_uses_summary_model(self, service, mock_anthropic_client, sample_article):
        mock_anthropic_client.messages.create.return_value = make_claude_response("Resumo.")
        await service.summarize(sample_article)

        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        assert "sonnet" in call_kwargs["model"]

    async def test_sends_title_and_url_in_prompt(self, service, mock_anthropic_client, sample_article):
        mock_anthropic_client.messages.create.return_value = make_claude_response("Resumo.")
        await service.summarize(sample_article)

        call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert sample_article.title in user_content
        assert sample_article.url in user_content

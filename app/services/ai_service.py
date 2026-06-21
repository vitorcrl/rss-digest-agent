import json

import anthropic

from app.core.config import settings
from app.domain.models import Article


class AIParseError(Exception):
    pass


RELEVANCE_SYSTEM_PROMPT = """You are a technical curator specialized in back-end, cloud, and AI.
Your job is to evaluate the relevance of articles for a senior back-end developer
focused on Node.js, Python, AWS, and microservices.

Score each article from 0 to 10:
- 8–10: highly relevant (new technology, real-world case study, architecture, performance)
- 5–7: relevant (best practices, known tools, trends)
- 0–4: low relevance (marketing, front-end, mobile, non-technical management)

Return ONLY a JSON array with objects { "index": N, "score": X }.
Do not add any text, explanation, or markdown."""

SUMMARY_SYSTEM_PROMPT = """You are a technical editor. Generate concise summaries in Brazilian Portuguese,
focused on WHAT is relevant and WHY it matters for a back-end developer.
Maximum 3 sentences. No intro ("This article..."), get straight to the point."""


class AIService:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def evaluate_relevance(self, titles: list[str]) -> tuple[list[int], int]:
        if not titles:
            return [], 0

        numbered = "\n".join(f'[{i}] "{title}"' for i, title in enumerate(titles))
        user_prompt = f"Evaluate the articles below:\n\n{numbered}"

        response = await self._client.messages.create(
            model=settings.AI_RELEVANCE_MODEL,
            max_tokens=500,
            system=RELEVANCE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        raw = response.content[0].text.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIParseError(f"Failed to parse relevance response: {raw!r}") from exc

        scores = [0] * len(titles)
        for item in parsed:
            idx = item["index"]
            if 0 <= idx < len(titles):
                scores[idx] = item["score"]

        return scores, tokens_used

    async def summarize(self, article: Article) -> tuple[str, int]:
        user_prompt = (
            f'Title: "{article.title}"\n'
            f"URL: {article.url}\n"
        )

        response = await self._client.messages.create(
            model=settings.AI_SUMMARY_MODEL,
            max_tokens=300,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        summary = response.content[0].text.strip()

        return summary, tokens_used

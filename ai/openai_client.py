"""OpenAI-compatible API client — supports OpenAI, DeepSeek, Ollama, etc."""

import json

from openai import OpenAI

from ai.base import AIClient, AnalysisResult

_PROMPT = """You are an academic paper analyzer. Analyze the following paper and return a JSON object.

Title: {title}

First pages text:
{full_text}

Return ONLY a JSON object (no other text) with these keys:
- "summary": A concise 3-5 sentence summary of the paper's contribution.
- "keywords": 5-8 comma-separated keywords.
- "research_area": The broad research area (e.g. "NLP", "Computer Vision", "Robotics").

JSON:"""


class OpenAIClient(AIClient):
    """Paper analysis using OpenAI or any OpenAI-compatible API.

    Supports: OpenAI, DeepSeek, Ollama, Groq, Together, etc.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        """Initialize the OpenAI-compatible client.

        Args:
            api_key: API key.
            model: Model name (e.g. gpt-4o-mini, deepseek-chat, llama3).
            base_url: Custom API base URL for non-OpenAI providers.
        """
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model

    def analyze(self, title: str, abstract: str, full_text: str) -> AnalysisResult:
        """Analyze a paper using the API."""
        text = full_text[:8000] if full_text else "No text available."
        prompt = _PROMPT.format(title=title, full_text=text)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content or ""
            return self._parse_response(raw)
        except Exception as exc:
            return AnalysisResult(error=f"API error: {exc}")

    def suggest_title(self, full_text: str) -> str:
        """Suggest a paper title from first page text."""
        text = full_text[:6000] if full_text else ""
        prompt = (
            "Read this paper's first page and give me ONLY the exact title of the paper. "
            "Return just the title string, nothing else. No quotes, no explanation.\n\n"
            f"{text}"
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model, max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content or ""
            return raw.strip().strip('"').strip("'")[:200]
        except Exception:
            return ""

    @staticmethod
    def _parse_response(raw: str) -> AnalysisResult:
        text = raw.strip()
        if text.startswith("```"):
            nl = text.find("\n")
            if nl != -1:
                text = text[nl + 1:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            data = json.loads(text)
            return AnalysisResult(
                summary=data.get("summary", ""),
                keywords=data.get("keywords", ""),
                research_area=data.get("research_area", ""),
            )
        except json.JSONDecodeError:
            return AnalysisResult(
                summary=raw[:1000],
                error=f"Failed to parse JSON. Raw: {raw[:200]}...",
            )

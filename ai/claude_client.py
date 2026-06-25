"""Claude API client for paper analysis."""

import json
import os

from ai.base import AIClient, AnalysisResult

# Prompt template for structured paper analysis.
_ANALYSIS_PROMPT = """You are an academic paper analyzer. Analyze the following paper and return a JSON object.

Title: {title}

First pages text:
{full_text}

Return ONLY a JSON object (no other text) with these keys:
- "summary": A concise 3-5 sentence summary of the paper's contribution.
- "keywords": 5-8 comma-separated keywords.
- "research_area": The broad research area (e.g. "NLP", "Computer Vision", "Robotics").

JSON:"""


class ClaudeClient(AIClient):
    """Paper analysis using the Anthropic Claude API.

    Requires the ANTHROPIC_API_KEY environment variable to be set.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
    ) -> None:
        """Initialize the Claude client.

        Args:
            model: Claude model ID to use.
            api_key: Anthropic API key. Reads ANTHROPIC_API_KEY env var if omitted.
        """
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Set it or pass api_key to ClaudeClient()."
            )
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "Anthropic SDK import failed. If running a packaged EXE, "
                "ensure OpenSSL DLLs (libssl/libcrypto) are bundled."
            ) from exc
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def analyze(
        self,
        title: str,
        abstract: str,
        full_text: str,
    ) -> AnalysisResult:
        """Analyze a paper using the Claude API.

        Args:
            title: The paper's title.
            abstract: The paper's abstract (unused in Claude prompt,
                      included in full_text).
            full_text: Extracted text from the first pages.

        Returns:
            AnalysisResult with summary, keywords, and research_area.
        """
        # Truncate text to avoid token limits (approx 8000 chars).
        text = full_text[:8000] if full_text else "No text available."

        prompt = _ANALYSIS_PROMPT.format(title=title, full_text=text)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            return self._parse_response(raw)

        except Exception as exc:
            return AnalysisResult(error=f"Claude API error: {exc}")

    def suggest_title(self, full_text: str) -> str:
        """Suggest a paper title from first page text."""
        text = full_text[:6000] if full_text else ""
        prompt = (
            "Read this paper's first page and give me ONLY the exact title of the paper. "
            "Return just the title string, nothing else. No quotes, no explanation.\n\n"
            f"{text}"
        )
        try:
            response = self._client.messages.create(
                model=self._model, max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip().strip('"').strip("'")
            return raw[:200]
        except Exception:
            return ""

    @staticmethod
    def _parse_response(raw: str) -> AnalysisResult:
        """Parse the JSON response from Claude.

        Handles cases where the model wraps JSON in markdown code fences.
        """
        # Strip markdown code fences if present.
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```).
            newline = text.find("\n")
            if newline != -1:
                text = text[newline + 1:]
            # Remove closing fence.
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
            # Fallback: try to extract useful content.
            return AnalysisResult(
                summary=raw[:1000],
                error=f"Failed to parse JSON response. Raw: {raw[:200]}...",
            )

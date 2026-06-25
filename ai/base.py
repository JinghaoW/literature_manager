"""AI abstraction — base class and data types for paper analysis."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    """Structured result from paper analysis."""

    summary: str = ""
    """AI-generated summary of the paper."""

    keywords: str = ""
    """Comma-separated keywords extracted from the paper."""

    research_area: str = ""
    """Broad research area / field (e.g. 'NLP', 'Computer Vision')."""

    error: str = ""
    """Error message if analysis failed, empty on success."""

    @property
    def success(self) -> bool:
        """True if analysis completed without error."""
        return not bool(self.error)


class AIClient(ABC):
    """Abstract base for AI analysis providers.

    Implementations provide paper analysis via different backends
    (Claude API, OpenAI, local models, etc.).
    """

    @abstractmethod
    def analyze(
        self,
        title: str,
        abstract: str,
        full_text: str,
    ) -> AnalysisResult:
        """Analyze a paper and return structured results.

        Args:
            title: The paper's title.
            abstract: The paper's abstract (if available, empty otherwise).
            full_text: The full text of the first few pages.

        Returns:
            AnalysisResult with summary, keywords, and research_area.
        """
        ...

    @abstractmethod
    def suggest_title(self, full_text: str) -> str:
        """Suggest a paper title from the first page text.

        Args:
            full_text: Text extracted from the first page(s) of the PDF.

        Returns:
            A short, accurate paper title string.
        """
        ...

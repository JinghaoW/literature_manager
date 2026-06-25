"""Paper analyzer — extract text from PDF and run AI analysis."""

from pathlib import Path

import fitz

from ai.base import AIClient, AnalysisResult
from database.manager import DatabaseManager
from database.models import Paper
from utils.logger import get_logger

_log = get_logger("ai.analyzer")

# Number of pages to extract for AI analysis.
_DEFAULT_MAX_PAGES = 5


def extract_paper_text(file_path: str | Path, max_pages: int = _DEFAULT_MAX_PAGES) -> str:
    """Extract text from the first N pages of a PDF.

    Args:
        file_path: Path to the PDF file.
        max_pages: Maximum number of pages to extract.

    Returns:
        Concatenated text from the first pages.
    """
    try:
        doc = fitz.open(str(file_path))
        pages = min(doc.page_count, max_pages)
        parts: list[str] = []
        for i in range(pages):
            page_text = doc[i].get_text()
            if page_text:
                parts.append(page_text)
        doc.close()
        return "\n\n".join(parts)
    except Exception as exc:
        raise RuntimeError(f"Failed to extract text from {file_path}: {exc}") from exc


def analyze_paper(
    paper: Paper,
    db: DatabaseManager,
    client: AIClient,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> AnalysisResult:
    """Analyze a paper and persist the results to the database.

    Extracts text from the paper's PDF, sends it to the AI client,
    and stores the summary, keywords, and research area back to the DB.

    Args:
        paper: The Paper instance to analyze.
        db: DatabaseManager for persisting results.
        client: An AIClient implementation (e.g. ClaudeClient).
        max_pages: Max pages of PDF text to send to the AI.

    Returns:
        AnalysisResult with the AI output (or error).
    """
    # Extract text from the PDF.
    try:
        full_text = extract_paper_text(paper.file_path, max_pages=max_pages)
    except RuntimeError as exc:
        _log.warning("Text extraction failed for paper #%d: %s", paper.id, exc)
        return AnalysisResult(error=str(exc))

    _log.info("Analyzing paper #%d: %s", paper.id, paper.title)

    # Run AI analysis.
    result = client.analyze(
        title=paper.title,
        abstract="",        # included in full_text
        full_text=full_text,
    )

    # Persist results to DB on success.
    if result.success:
        db.update_paper(
            paper.id,
            summary=result.summary,
            keywords=result.keywords,
        )
        _log.info("Analysis complete for paper #%d", paper.id)
        # Refresh the paper object.
        updated = db.get_paper(paper.id)
        if updated is not None:
            paper.summary = updated.summary
            paper.keywords = updated.keywords
    else:
        _log.error("Analysis failed for paper #%d: %s", paper.id, result.error)

    return result


def analyze_paper_batch(
    papers: list[Paper],
    db: DatabaseManager,
    client: AIClient,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> dict[int, AnalysisResult]:
    """Analyze multiple papers and persist results.

    Args:
        papers: List of Paper instances to analyze.
        db: DatabaseManager for persisting results.
        client: An AIClient implementation.
        max_pages: Max pages of PDF text per paper.

    Returns:
        Dict mapping paper_id to AnalysisResult.
    """
    results: dict[int, AnalysisResult] = {}
    for paper in papers:
        result = analyze_paper(paper, db, client, max_pages=max_pages)
        results[paper.id] = result
    return results

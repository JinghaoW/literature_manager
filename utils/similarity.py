"""Jaccard similarity for paper keyword comparison."""

from __future__ import annotations

from database.models import Paper


def _keyword_set(paper: Paper) -> set[str]:
    """Parse a paper's keywords into a normalized set.

    Args:
        paper: Paper with a keywords string (comma-separated).

    Returns:
        Set of lowercased, stripped keywords. Empty set if no keywords.
    """
    if not paper.keywords:
        return set()
    return {kw.strip().lower() for kw in paper.keywords.split(",") if kw.strip()}


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute the Jaccard similarity coefficient.

    J(A, B) = |A ∩ B| / |A ∪ B|.

    Args:
        set_a: First set.
        set_b: Second set.

    Returns:
        Similarity score in [0.0, 1.0]. Returns 0.0 when both sets are empty.
    """
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    return len(intersection) / len(union)


def find_related_papers(
    paper: Paper,
    all_papers: list[Paper],
    top_n: int = 5,
    min_score: float = 0.0,
) -> list[tuple[Paper, float]]:
    """Find papers related to the given paper by keyword similarity.

    Uses Jaccard similarity on keyword sets. Papers with no keywords
    are skipped. The source paper itself is excluded.

    Args:
        paper: The source paper to find relations for.
        all_papers: All papers in the library.
        top_n: Maximum number of related papers to return.
        min_score: Minimum similarity score (0.0–1.0) to include.

    Returns:
        List of (Paper, similarity_score) tuples, sorted by score descending.
    """
    source_kw = _keyword_set(paper)
    if not source_kw:
        return []

    scored: list[tuple[Paper, float]] = []
    for other in all_papers:
        if other.id == paper.id:
            continue
        other_kw = _keyword_set(other)
        if not other_kw:
            continue
        score = jaccard_similarity(source_kw, other_kw)
        if score >= min_score:
            scored.append((other, score))

    # Sort by score descending, then by title for ties.
    scored.sort(key=lambda item: (-item[1], item[0].title.lower()))
    return scored[:top_n]

"""Extract annotations (highlights, notes, comments) from PDF files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


@dataclass
class Annotation:
    """A single annotation extracted from a PDF."""

    page: int
    """1-based page number where the annotation appears."""

    text: str
    """The annotation content (highlighted text, note body, etc.)."""

    annot_type: str
    """Annotation type: Highlight, Text, Underline, StrikeOut, etc."""

    color: str = ""
    """Annotation color as hex string, if available."""


def extract_annotations(
    file_path: str | Path, max_pages: int | None = None
) -> list[Annotation]:
    """Extract all text-bearing annotations from a PDF.

    Reads highlights, sticky notes, text annotations, underlines,
    and strikeouts.  Each annotation's captured text and metadata
    are returned.

    Args:
        file_path: Path to the PDF file.
        max_pages: Max pages to scan (None = all pages).

    Returns:
        List of Annotation objects, sorted by page number.
    """
    file_path = Path(file_path)
    annotations: list[Annotation] = []

    try:
        doc = fitz.open(str(file_path))
        num_pages = doc.page_count
        if max_pages is not None:
            num_pages = min(num_pages, max_pages)

        for page_idx in range(num_pages):
            page = doc[page_idx]
            annots = list(page.annots())
            if not annots:
                continue

            for a in annots:
                entry = _parse_annot(a, page_idx + 1)
                if entry and entry.text.strip():
                    annotations.append(entry)

        doc.close()

    except Exception:
        # Graceful — return whatever we extracted so far.
        pass

    annotations.sort(key=lambda a: a.page)
    return annotations


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------


# Type-name mapping for PyMuPDF annotation types.
_TYPE_NAMES: dict[int, str] = {
    fitz.PDF_ANNOT_HIGHLIGHT: "Highlight",
    fitz.PDF_ANNOT_TEXT: "Note",
    fitz.PDF_ANNOT_FREE_TEXT: "Comment",
    fitz.PDF_ANNOT_UNDERLINE: "Underline",
    fitz.PDF_ANNOT_STRIKE_OUT: "StrikeOut",
    fitz.PDF_ANNOT_SQUIGGLY: "Squiggly",
}


def _parse_annot(annot, page: int) -> Annotation | None:
    """Convert a PyMuPDF annotation object into an Annotation object."""
    atype = annot.type[0]  # tuple like (8, 'Highlight')
    type_name = _TYPE_NAMES.get(atype, f"Type{atype}")

    # Get the note/content text.
    info = annot.info or {}
    text = (info.get("content", "") or "").strip()

    if not text:
        return None

    # Extract color.
    color = ""
    try:
        colors = getattr(annot, "colors", {}) or {}
        stroke = colors.get("stroke")
        if stroke and len(stroke) >= 3:
            r, g, b = stroke[:3]
            color = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    except (TypeError, ValueError, IndexError, AttributeError):
        pass

    return Annotation(page=page, text=text, annot_type=type_name, color=color)


def extract_highlighted_text(file_path: str | Path) -> str:
    """Extract highlighted text regions from the entire PDF.

    For each highlight annotation, extracts the text that appears
    underneath the highlighted rectangle on the page.

    Returns:
        All highlighted text joined with newlines, or empty string.
    """
    file_path = Path(file_path)
    parts: list[str] = []

    try:
        doc = fitz.open(str(file_path))
        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            annots = list(page.annots())
            if not annots:
                continue

            for a in annots:
                if a.type[0] != fitz.PDF_ANNOT_HIGHLIGHT:
                    continue

                # Get text under the highlighted rectangle.
                rect = a.rect
                if rect:
                    words = page.get_text("words", clip=rect)
                    text = " ".join(w[4] for w in words).strip()
                    if text:
                        parts.append(text)

        doc.close()
    except Exception:
        pass

    return "\n".join(parts)

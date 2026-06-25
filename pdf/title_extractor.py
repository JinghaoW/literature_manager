"""Title extraction from PDF files.

Priority:
  1. PDF metadata title
  2. Largest-font text on the first page
  3. Filename (fallback)
"""

from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def extract_title(file_path: str | Path) -> str:
    """Extract a paper title from a PDF file.

    Tries metadata first, then first-page heuristics, then filename.

    Args:
        file_path: Path to the PDF file.

    Returns:
        The extracted title string (never empty).
    """
    file_path = Path(file_path)

    # Priority 1: PDF metadata
    title = _from_metadata(file_path)
    if title:
        return title

    # Priority 2: First page heuristics
    title = _from_first_page(file_path)
    if title:
        return title

    # Priority 3: Filename fallback
    return _from_filename(file_path)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _from_metadata(file_path: Path) -> Optional[str]:
    """Try to get the title from PDF metadata."""
    try:
        doc = fitz.open(str(file_path))
        meta_title = doc.metadata.get("title", "").strip()
        doc.close()

        # Reject obviously bad / generic titles.
        if not meta_title or len(meta_title) < 3:
            return None
        if meta_title.lower() in {"untitled", "title", "no title", "paper"}:
            return None
        # Reject pure filenames (e.g. "paper.pdf" embedded as title).
        if meta_title.endswith(".pdf") or meta_title.endswith(".PDF"):
            return None
        # Reject when metadata title is just the filename stem.
        filename_title = file_path.stem.replace("_", " ").replace("-", " ").strip()
        if meta_title.lower() == filename_title.lower():
            return None
        return meta_title
    except Exception:
        return None


def _from_first_page(file_path: Path) -> Optional[str]:
    """Extract a title from the first page by finding the largest-font text."""
    try:
        doc = fitz.open(str(file_path))
        if doc.page_count == 0:
            doc.close()
            return None

        page = doc[0]
        blocks = page.get_text("dict")["blocks"]
        page_height = page.rect.height
        doc.close()

        # Collect all spans with their font size and position.
        spans: list[dict] = []  # {text, size, y0}
        for block in blocks:
            if block["type"] != 0:  # text block only
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if text:
                        spans.append({
                            "text": text,
                            "size": span["size"],
                            "y0": line["bbox"][1],
                        })

        if not spans:
            return None

        # Pick spans near the top of the page (top 30%) with largest fonts.
        top_region = page_height * 0.3
        top_spans = [s for s in spans if s["y0"] < top_region]

        if not top_spans:
            top_spans = spans  # fall back to all spans

        # Sort by font size descending, then by vertical position.
        top_spans.sort(key=lambda s: (-s["size"], s["y0"]))

        # Take the largest-font text as the title.
        # If there are multiple spans with the same large font, concatenate them.
        largest_size = top_spans[0]["size"]
        title_parts = []
        for s in top_spans:
            if abs(s["size"] - largest_size) < 0.5:
                title_parts.append(s["text"])
            else:
                break

        title = " ".join(title_parts).strip()
        # Clean up excessive whitespace.
        title = " ".join(title.split())
        return title if len(title) >= 3 else None
    except Exception:
        return None


def _from_filename(file_path: Path) -> str:
    """Derive a title from the filename by removing the extension."""
    return file_path.stem.replace("_", " ").replace("-", " ").strip()

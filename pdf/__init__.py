"""PDF processing — import, title extraction, annotations, and file handling."""

from pdf.title_extractor import extract_title
from pdf.importer import PdfImporter
from pdf.annotations import extract_annotations, extract_highlighted_text, Annotation

__all__ = [
    "extract_title",
    "PdfImporter",
    "extract_annotations",
    "extract_highlighted_text",
    "Annotation",
]

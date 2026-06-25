"""Flask REST API server for Paper Notes."""

import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, abort

from database.manager import DatabaseManager
from database.models import PaperStatus
from pdf.importer import PdfImporter
from pdf.annotations import extract_annotations, extract_highlighted_text
from ai.analyzer import analyze_paper
from ai.claude_client import ClaudeClient
from utils.similarity import find_related_papers
from utils.logger import get_logger

_log = get_logger("web.server")

# ------------------------------------------------------------------
# Flask app factory
# ------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = "papers.db"


def create_app(db_path: str = DB_PATH) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
    db = DatabaseManager(db_path)

    # ------------------------------------------------------------------
    # Static frontend
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        """Serve the single-page app."""
        return send_from_directory(str(STATIC_DIR), "index.html")

    # ------------------------------------------------------------------
    # Paper CRUD
    # ------------------------------------------------------------------

    @app.route("/api/papers", methods=["GET"])
    def list_papers():
        """List all papers, with optional filters.

        Query params:
            status: Filter by reading status (Unread/Reading/Read).
            search: Substring search across title/keywords/notes.
            order_by: Column to sort by (default: created_time).
            descending: 'true' for descending order.
        """
        status_str = request.args.get("status")
        search = request.args.get("search", "").strip()
        order_by = request.args.get("order_by", "created_time")
        descending = request.args.get("descending", "false").lower() == "true"

        # Resolve status filter.
        status = None
        if status_str:
            status = _parse_status(status_str)

        # Fetch from DB.
        papers = db.list_papers(status=status, order_by=order_by, descending=descending)

        # Client-side search filter.
        if search:
            q = search.lower()
            papers = [
                p for p in papers
                if q in p.title.lower()
                or (p.keywords and q in p.keywords.lower())
                or (p.notes and q in p.notes.lower())
            ]

        return jsonify([_paper_to_dict(p) for p in papers])

    @app.route("/api/papers/counts", methods=["GET"])
    def paper_counts():
        """Get paper counts per reading status."""
        return jsonify({
            "all": db.count_papers(),
            "unread": db.count_papers(status=PaperStatus.UNREAD),
            "reading": db.count_papers(status=PaperStatus.READING),
            "read": db.count_papers(status=PaperStatus.READ),
        })

    @app.route("/api/papers/<int:paper_id>", methods=["GET"])
    def get_paper(paper_id: int):
        """Get a single paper by ID."""
        paper = db.get_paper(paper_id)
        if paper is None:
            abort(404, description="Paper not found")
        return jsonify(_paper_to_dict(paper))

    @app.route("/api/papers/<int:paper_id>", methods=["PUT"])
    def update_paper(paper_id: int):
        """Update paper fields (status, notes, etc.)."""
        data = request.get_json(silent=True) or {}

        # Convert status string to enum if present.
        if "status" in data and isinstance(data["status"], str):
            data["status"] = _parse_status(data["status"])

        updated = db.update_paper(paper_id, **data)
        if updated is None:
            abort(404, description="Paper not found")
        return jsonify(_paper_to_dict(updated))

    @app.route("/api/papers/<int:paper_id>", methods=["DELETE"])
    def delete_paper(paper_id: int):
        """Delete a paper by ID."""
        ok = db.delete_paper(paper_id)
        if not ok:
            abort(404, description="Paper not found")
        return jsonify({"deleted": True})

    # ------------------------------------------------------------------
    # Related papers
    # ------------------------------------------------------------------

    @app.route("/api/papers/<int:paper_id>/related", methods=["GET"])
    def related_papers(paper_id: int):
        """Get papers related to the given paper by keyword similarity."""
        paper = db.get_paper(paper_id)
        if paper is None:
            abort(404, description="Paper not found")

        all_papers = db.list_papers()
        related = find_related_papers(paper, all_papers, top_n=5, min_score=0.05)
        return jsonify([
            {"paper": _paper_to_dict(p), "score": round(score, 3)}
            for p, score in related
        ])

    # ------------------------------------------------------------------
    # Open PDF
    # ------------------------------------------------------------------

    @app.route("/api/papers/<int:paper_id>/view", methods=["GET", "POST"])
    def view_pdf(paper_id: int):
        """Open the paper's PDF in the system default viewer."""
        paper = db.get_paper(paper_id)
        if paper is None:
            abort(404, description="Paper not found")

        path = paper.file_path
        if not os.path.isfile(path):
            abort(400, description=f"File not found: {path}")

        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            abort(500, description=f"Failed to open file: {exc}")

        return jsonify({"opened": True})

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    @app.route("/api/papers/<int:paper_id>/annotations", methods=["GET"])
    def paper_annotations(paper_id: int):
        """Get annotations (highlights, notes) extracted from the PDF."""
        paper = db.get_paper(paper_id)
        if paper is None:
            abort(404, description="Paper not found")

        anns = extract_annotations(paper.file_path)
        highlighted = extract_highlighted_text(paper.file_path)

        return jsonify({
            "annotations": [
                {
                    "page": a.page,
                    "text": a.text,
                    "type": a.annot_type,
                    "color": a.color,
                }
                for a in anns
            ],
            "highlighted_text": highlighted,
        })

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    @app.route("/api/import", methods=["POST"])
    def import_folder():
        """Import PDFs from a folder. Body: {"folder_path": "..."}"""
        data = request.get_json(silent=True) or {}
        folder_path = data.get("folder_path", "")

        if not folder_path:
            abort(400, description="Missing folder_path")

        folder = Path(folder_path)
        if not folder.is_dir():
            abort(400, description=f"Not a directory: {folder_path}")

        importer = PdfImporter(db)
        result = importer.import_folder(folder)

        return jsonify({
            "imported": result.total_imported,
            "skipped": result.total_skipped,
            "failed": result.total_failed,
            "imported_list": [str(p) for p in result.imported],
        })

    # ------------------------------------------------------------------
    # AI Analysis
    # ------------------------------------------------------------------

    @app.route("/api/papers/<int:paper_id>/analyze", methods=["POST"])
    def analyze_paper_endpoint(paper_id: int):
        """Run AI analysis on a paper."""
        paper = db.get_paper(paper_id)
        if paper is None:
            abort(404, description="Paper not found")

        try:
            client = ClaudeClient()
        except ValueError as exc:
            abort(400, description=str(exc))

        result = analyze_paper(paper, db, client)
        return jsonify({
            "success": result.success,
            "summary": result.summary,
            "keywords": result.keywords,
            "research_area": result.research_area,
            "error": result.error,
        })

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(err):
        return jsonify({"error": str(err.description)}), 404

    @app.errorhandler(400)
    def bad_request(err):
        return jsonify({"error": str(err.description)}), 400

    return app


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _paper_to_dict(paper) -> dict:
    """Serialize a Paper ORM object to a JSON-safe dict."""
    return {
        "id": paper.id,
        "title": paper.title,
        "file_path": paper.file_path,
        "file_hash": paper.file_hash,
        "summary": paper.summary or "",
        "keywords": paper.keywords or "",
        "notes": paper.notes or "",
        "status": paper.status.value,
        "created_time": paper.created_time.isoformat() if paper.created_time else None,
        "updated_time": paper.updated_time.isoformat() if paper.updated_time else None,
    }


def _parse_status(value: str) -> PaperStatus:
    """Parse a status string into a PaperStatus enum."""
    mapping = {s.value.lower(): s for s in PaperStatus}
    key = value.strip().lower()
    if key not in mapping:
        raise ValueError(f"Invalid status: {value!r}")
    return mapping[key]

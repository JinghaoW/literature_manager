"""PdfImporter — scan folders, import PDFs, detect duplicates."""

from dataclasses import dataclass, field
from pathlib import Path

from database.manager import DatabaseManager
from pdf.title_extractor import extract_title
from utils.file_hash import compute_file_hash
from utils.logger import get_logger

_log = get_logger("pdf.importer")


@dataclass
class ImportResult:
    """Outcome of a batch import operation."""

    imported: list[str] = field(default_factory=list)
    """File paths of successfully imported papers."""

    skipped: list[str] = field(default_factory=list)
    """File paths skipped because they already exist (duplicate hash)."""

    failed: list[str] = field(default_factory=list)
    """File paths that caused an error during import."""

    @property
    def total_imported(self) -> int:
        """Number of successfully imported papers."""
        return len(self.imported)

    @property
    def total_skipped(self) -> int:
        """Number of duplicates skipped."""
        return len(self.skipped)

    @property
    def total_failed(self) -> int:
        """Number of failures."""
        return len(self.failed)


class PdfImporter:
    """Scans folders for PDFs and imports them into the database.

    Each PDF is:
      1. Hashed (SHA-256) for duplicate detection.
      2. Title is extracted via metadata → first page → filename.
      3. Stored in the database via DatabaseManager.

    Duplicates are detected by file hash and skipped automatically.
    """

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize the importer with a database manager.

        Args:
            db: An initialized DatabaseManager instance.
        """
        self._db = db

    def scan_folder(self, folder_path: str | Path) -> list[Path]:
        """Recursively find all PDF files in a folder.

        Args:
            folder_path: Root folder to scan.

        Returns:
            Sorted list of absolute paths to PDF files.
        """
        folder = Path(folder_path)
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder_path}")

        pdf_paths = sorted(folder.rglob("*.pdf"))
        return pdf_paths

    def import_paper(self, file_path: str | Path) -> tuple[bool, str]:
        """Import a single PDF file into the database.

        Hash is computed and checked against existing papers to prevent
        duplicates. If a paper with the same hash already exists, the
        import is skipped.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Tuple of (success, message). success=True if imported or
            already exists; False if an error occurred.
        """
        file_path = Path(file_path)

        if not file_path.is_file():
            return False, f"File not found: {file_path}"

        try:
            # Compute hash.
            file_hash = compute_file_hash(file_path)

            # Duplicate check.
            existing = self._db.get_paper_by_hash(file_hash)
            if existing is not None:
                return True, f"Skipped (duplicate of #{existing.id}): {file_path.name}"

            # Title extraction.
            title = extract_title(file_path)

            # Store.
            self._db.add_paper(
                title=title,
                file_path=str(file_path.resolve()),
                file_hash=file_hash,
            )
            return True, f"Imported: {title}"

        except Exception as exc:
            return False, f"Error importing {file_path.name}: {exc}"

    def import_folder(self, folder_path: str | Path) -> ImportResult:
        """Scan a folder and import all PDFs found.

        Args:
            folder_path: Root folder to scan recursively.

        Returns:
            ImportResult with lists of imported, skipped, and failed paths.
        """
        result = ImportResult()
        pdf_paths = self.scan_folder(folder_path)
        _log.info("Scanning %s: %d PDF(s) found", folder_path, len(pdf_paths))

        for pdf_path in pdf_paths:
            success, message = self.import_paper(pdf_path)
            path_str = str(pdf_path)

            if not success:
                _log.warning("Import failed: %s — %s", path_str, message)
                result.failed.append(path_str)
            elif message.startswith("Skipped"):
                _log.debug("Skipped duplicate: %s", path_str)
                result.skipped.append(path_str)
            else:
                _log.info("Imported: %s", path_str)
                result.imported.append(path_str)

        _log.info(
            "Import complete: %d imported, %d skipped, %d failed",
            result.total_imported, result.total_skipped, result.total_failed,
        )
        return result

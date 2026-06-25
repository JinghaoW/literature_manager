"""Main application window — assembles the three-panel layout."""

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog, QMessageBox,
    QTabWidget, QWidget, QVBoxLayout, QLabel, QListWidget,
)
from PySide6.QtCore import Qt

from database.manager import DatabaseManager
from database.models import PaperStatus
from ui.left_panel import LeftPanel
from ui.center_panel import CenterPanel
from ui.right_panel import RightPanel
from pdf.importer import PdfImporter
from utils.logger import get_logger
from utils.similarity import find_related_papers

_log = get_logger("ui.main_window")

HELP_ITEMS = [
    "1. Click File -> Import Folder... to batch import PDFs.",
    "2. Use All/Unread/Reading/Read in the left panel to filter papers by reading status.",
    "3. Use the center search box for real-time matching by title, keywords, or notes.",
    "4. Update reading status from the right-side status dropdown.",
    "5. Notes (Markdown) supports note-taking and auto-save.",
    "6. Use Related Papers on the right to view and navigate to similar papers.",
    "7. Press F1 or open Help -> Usage Guide to view this guide at any time.",
]


class MainWindow(QMainWindow):
    """Main window with three-panel layout for paper management."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        """Initialize the main window.

        Args:
            db: DatabaseManager instance. Creates a default one if omitted.
        """
        super().__init__()
        self.setWindowTitle("Paper Notes")
        self.setMinimumSize(900, 600)
        self.resize(1200, 750)

        self._db = db or DatabaseManager()

        self._build_ui()
        self._connect_signals()
        self._refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the three-panel layout and menu bar."""
        # Menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        import_action = file_menu.addAction("Import Folder...")
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._on_import_folder)

        help_menu = menubar.addMenu("Help")
        usage_action = help_menu.addAction("Usage Guide")
        usage_action.setShortcut("F1")
        usage_action.triggered.connect(self._show_help_tab)

        self._tabs = QTabWidget()
        self._main_tab = QWidget()
        self._help_tab = QWidget()
        self._tabs.addTab(self._main_tab, "Library")
        self._tabs.addTab(self._help_tab, "Help")

        self._left = LeftPanel()
        self._center = CenterPanel()
        self._right = RightPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._left)
        splitter.addWidget(self._center)
        splitter.addWidget(self._right)
        splitter.setStretchFactor(0, 0)  # left: fixed
        splitter.setStretchFactor(1, 1)  # center: stretches
        splitter.setStretchFactor(2, 1)  # right: stretches
        splitter.setSizes([180, 450, 450])

        main_layout = QVBoxLayout(self._main_tab)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)

        self._build_help_tab()
        self.setCentralWidget(self._tabs)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Connect panel signals to slots."""
        self._left.filter_changed.connect(self._on_filter_changed)
        self._center.paper_selected.connect(self._on_paper_selected)
        self._right.status_changed.connect(self._on_status_changed)
        self._right.notes_changed.connect(self._on_notes_changed)
        self._right.paper_navigate.connect(self._on_paper_navigate)

        # Track active filter for refresh after status changes.
        self._active_filter: PaperStatus | None = None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_filter_changed(self, status: PaperStatus | None) -> None:
        """Reload the center panel when the status filter changes."""
        self._right.flush_notes()
        self._active_filter = status
        papers = self._db.list_papers(status=status)
        self._center.load_papers(papers)
        self._right.clear()

    def _on_paper_selected(self, paper_id: int) -> None:
        """Show paper details and related papers when a row is selected."""
        self._right.flush_notes()
        paper = self._db.get_paper(paper_id)
        if paper is not None:
            self._right.show_paper(paper)
            # Find and display related papers.
            all_papers = self._db.list_papers()
            related = find_related_papers(paper, all_papers, top_n=5, min_score=0.05)
            self._right.show_related_papers(related)
        else:
            self._right.clear()

    def _on_paper_navigate(self, paper_id: int) -> None:
        """Navigate to a paper (from related papers click)."""
        _log.debug("Navigate to paper #%d", paper_id)
        # Switch to All Papers to ensure the target is visible,
        # then select the target row.
        self._on_filter_changed(None)
        self._select_paper_in_table(paper_id)

    def _on_notes_changed(self, paper_id: int, notes: str) -> None:
        """Persist notes to the database (auto-save)."""
        self._db.update_paper(paper_id, notes=notes)

    def _on_status_changed(self, paper_id: int, new_status: PaperStatus) -> None:
        """Persist a status change and refresh the UI."""
        _log.info("Status change: paper #%d -> %s", paper_id, new_status.value)
        self._db.update_paper(paper_id, status=new_status)

        # Refresh center panel (respect active filter).
        papers = self._db.list_papers(status=self._active_filter)
        self._center.load_papers(papers)

        self._update_counts()
        self._select_paper_in_table(paper_id)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Refresh all panels with current data."""
        self._update_counts()
        papers = self._db.list_papers()
        self._center.load_papers(papers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_counts(self) -> None:
        """Refresh the left-panel paper counts from the database."""
        counts: dict[PaperStatus | None, int] = {}
        counts[None] = self._db.count_papers()
        for s in PaperStatus:
            counts[s] = self._db.count_papers(status=s)
        self._left.update_counts(counts)

    def _select_paper_in_table(self, paper_id: int) -> None:
        """Find and select a paper row in the center table by its ID."""
        for row in range(self._center._table.rowCount()):
            item = self._center._table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == paper_id:
                self._center._table.selectRow(row)
                break

    def _on_import_folder(self) -> None:
        """Open a folder picker and import all PDFs found."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder with PDFs", "",
        )
        if not folder:
            return

        _log.info("Importing PDFs from: %s", folder)
        importer = PdfImporter(self._db)
        result = importer.import_folder(folder)

        # Refresh UI.
        self._refresh()
        self._right.clear()

        # Show summary.
        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported: {result.total_imported}\n"
            f"Skipped (duplicates): {result.total_skipped}\n"
            f"Failed: {result.total_failed}",
        )

    def _build_help_tab(self) -> None:
        """Create Help tab with built-in usage instructions."""
        layout = QVBoxLayout(self._help_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Usage Guide")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        help_list = QListWidget()
        for item in HELP_ITEMS:
            help_list.addItem(item)
        layout.addWidget(help_list)

    def _show_help_tab(self) -> None:
        """Switch notebook to Help tab."""
        self._tabs.setCurrentWidget(self._help_tab)

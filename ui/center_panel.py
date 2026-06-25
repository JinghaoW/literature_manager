"""Center panel — paper list table."""

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from database.models import Paper, PaperStatus

# Row background colors by reading status.
_STATUS_COLORS: dict[PaperStatus, QColor] = {
    PaperStatus.UNREAD:  QColor("#ffffff"),   # white (default)
    PaperStatus.READING: QColor("#cce5ff"),   # light blue
    PaperStatus.READ:    QColor("#d4edda"),   # light green
}


class CenterPanel(QWidget):
    """Table widget displaying the list of papers.

    Emits a signal when the user selects a paper.
    """

    paper_selected = Signal(int)  # paper_id

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the center panel."""
        super().__init__(parent)
        self._all_papers: list[Paper] = []   # unfiltered list
        self._papers: list[Paper] = []       # currently displayed
        self._search_text: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the search bar, table, and layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Search bar
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Search title, keywords, notes...")
        self._search_bar.setClearButtonEnabled(True)
        self._search_bar.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_bar)

        # Table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Title", "Status", "Date"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)

        # Column sizing
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 120)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._table)

    def load_papers(self, papers: list[Paper]) -> None:
        """Replace the full paper list and re-apply the current search filter.

        Args:
            papers: Complete list of Paper instances (before search filtering).
        """
        self._all_papers = papers
        self._apply_search()

    def _on_search_changed(self, text: str) -> None:
        """Handle search bar text changes (real-time filtering)."""
        self._search_text = text.strip()
        self._apply_search()

    def _apply_search(self) -> None:
        """Filter _all_papers by search text and render the table."""
        if not self._search_text:
            self._papers = list(self._all_papers)
        else:
            query = self._search_text.lower()
            self._papers = [
                p for p in self._all_papers
                if self._paper_matches(p, query)
            ]
        self._render_table()

    @staticmethod
    def _paper_matches(paper: Paper, query: str) -> bool:
        """Check if a paper matches a search query.

        Searches title, keywords, and notes (case-insensitive substring).
        """
        if query in paper.title.lower():
            return True
        if paper.keywords and query in paper.keywords.lower():
            return True
        if paper.notes and query in paper.notes.lower():
            return True
        return False

    def _render_table(self) -> None:
        """Render self._papers into the table widget."""
        self._table.setRowCount(len(self._papers))

        for row, paper in enumerate(self._papers):
            # Row color by status.
            bg = _STATUS_COLORS.get(paper.status, QColor("#ffffff"))

            # Title
            title_item = QTableWidgetItem(paper.title)
            title_item.setData(Qt.ItemDataRole.UserRole, paper.id)
            title_item.setBackground(bg)
            self._table.setItem(row, 0, title_item)

            # Status
            status_item = QTableWidgetItem(paper.status.value)
            status_item.setBackground(bg)
            self._table.setItem(row, 1, status_item)

            # Date (formatted)
            created = paper.created_time
            if isinstance(created, datetime):
                date_str = created.strftime("%Y-%m-%d")
            else:
                date_str = str(created)[:10]
            date_item = QTableWidgetItem(date_str)
            date_item.setBackground(bg)
            self._table.setItem(row, 2, date_item)

    def _on_selection_changed(self) -> None:
        """Handle row selection and emit paper_selected."""
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._papers):
            self.paper_selected.emit(self._papers[row].id)

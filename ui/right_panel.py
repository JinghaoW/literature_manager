"""Right panel — paper details view."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QScrollArea,
    QFrame,
    QComboBox,
)
from PySide6.QtCore import Qt, Signal, QTimer

from database.models import Paper, PaperStatus


class RightPanel(QWidget):
    """Detail view for a single paper.

    Displays the title, reading status, summary, keywords, and notes.

    Signals:
        status_changed: Emitted when the user changes the reading status.
            Args: paper_id (int), new_status (PaperStatus)
    """

    status_changed = Signal(int, PaperStatus)
    notes_changed = Signal(int, str)  # paper_id, new notes text
    paper_navigate = Signal(int)      # paper_id to navigate to

    # Auto-save debounce delay in milliseconds.
    _AUTO_SAVE_DELAY = 800

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the right panel."""
        super().__init__(parent)
        self._current_paper_id: int | None = None
        self._build_ui()
        self._setup_auto_save()

    def _setup_auto_save(self) -> None:
        """Create the debounced auto-save timer for notes."""
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_notes)

    def _build_ui(self) -> None:
        """Construct the detail view layout."""
        # Outer layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll area for the detail content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title
        self._title_label = QLabel("Select a paper")
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self._title_label)

        # Status row (label + combo)
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #555;")
        status_row.addWidget(status_label)

        self._status_combo = QComboBox()
        for s in PaperStatus:
            self._status_combo.addItem(s.value, s)
        self._status_combo.setCurrentIndex(-1)
        self._status_combo.currentIndexChanged.connect(self._on_status_combo_changed)
        status_row.addWidget(self._status_combo)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Summary section
        layout.addWidget(self._section_label("Summary"))
        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setPlaceholderText("No summary yet.")
        self._summary_text.setMaximumHeight(150)
        layout.addWidget(self._summary_text)

        # Keywords section
        layout.addWidget(self._section_label("Keywords"))
        self._keywords_label = QLabel("—")
        self._keywords_label.setWordWrap(True)
        self._keywords_label.setStyleSheet("color: #3a6ea5;")
        layout.addWidget(self._keywords_label)

        # Notes section
        layout.addWidget(self._section_label("Notes (Markdown)"))
        self._notes_text = QTextEdit()
        self._notes_text.setPlaceholderText("Write your notes here (Markdown supported)...")
        self._notes_text.textChanged.connect(self._on_notes_text_changed)
        layout.addWidget(self._notes_text)

        # Related Papers section
        layout.addWidget(self._section_label("Related Papers"))
        self._related_container = QWidget()
        self._related_layout = QVBoxLayout(self._related_container)
        self._related_layout.setContentsMargins(0, 0, 0, 0)
        self._related_layout.setSpacing(2)
        self._related_placeholder = QLabel("Select a paper with keywords to see related papers.")
        self._related_placeholder.setWordWrap(True)
        self._related_placeholder.setStyleSheet("color: #999; font-size: 11px;")
        self._related_layout.addWidget(self._related_placeholder)
        layout.addWidget(self._related_container)

        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        """Create a section header label."""
        label = QLabel(text)
        label.setStyleSheet("font-size: 12px; font-weight: bold; color: #666; margin-top: 8px;")
        return label

    def show_paper(self, paper: Paper) -> None:
        """Populate the panel with a paper's details.

        Args:
            paper: The Paper instance to display.
        """
        self._current_paper_id = paper.id
        self._title_label.setText(paper.title)

        # Set combo without triggering the signal.
        self._status_combo.blockSignals(True)
        idx = self._status_combo.findData(paper.status)
        self._status_combo.setCurrentIndex(idx)
        self._status_combo.blockSignals(False)

        summary = paper.summary or ""
        self._summary_text.setPlainText(summary)

        keywords = paper.keywords or ""
        self._keywords_label.setText(keywords if keywords else "—")

        notes = paper.notes or ""
        self._notes_text.blockSignals(True)
        self._notes_text.setPlainText(notes)
        self._notes_text.blockSignals(False)

    def show_related_papers(self, related: list[tuple[Paper, float]]) -> None:
        """Display the list of related papers with similarity scores.

        Args:
            related: List of (Paper, similarity_score) tuples, sorted by score desc.
        """
        # Clear existing items (keep the placeholder as fallback).
        self._clear_related()

        if not related:
            self._related_placeholder.setText("No related papers found.")
            self._related_placeholder.setVisible(True)
            return

        self._related_placeholder.setVisible(False)
        for paper, score in related:
            pct = int(round(score * 100))
            label = QLabel(f"▸ {paper.title}  ({pct}%)")
            label.setWordWrap(True)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setStyleSheet(
                "color: #3a6ea5; font-size: 11px; padding: 2px 0;"
            )
            label.setToolTip(f"Click to view: {paper.title}\nSimilarity: {pct}%")
            # Capture paper_id in closure.
            pid = paper.id
            label.mousePressEvent = lambda event, p=pid: self.paper_navigate.emit(p)
            self._related_layout.addWidget(label)

    def _clear_related(self) -> None:
        """Remove all related paper widgets (preserves placeholder)."""
        i = self._related_layout.count()
        while i > 0:
            i -= 1
            item = self._related_layout.itemAt(i)
            if item and item.widget() and item.widget() is not self._related_placeholder:
                widget = item.widget()
                self._related_layout.removeWidget(widget)
                widget.deleteLater()

    def clear(self) -> None:
        """Reset the panel to its empty state."""
        self._current_paper_id = None
        self._save_timer.stop()
        self._title_label.setText("Select a paper")
        self._status_combo.blockSignals(True)
        self._status_combo.setCurrentIndex(-1)
        self._status_combo.blockSignals(False)
        self._summary_text.clear()
        self._keywords_label.setText("—")
        self._notes_text.blockSignals(True)
        self._notes_text.clear()
        self._notes_text.blockSignals(False)
        self._clear_related()
        self._related_placeholder.setText("Select a paper with keywords to see related papers.")
        self._related_placeholder.setVisible(True)

    def flush_notes(self) -> None:
        """Save any pending notes immediately (used before switching papers)."""
        self._save_timer.stop()
        if self._current_paper_id is not None:
            self._save_notes()

    def _on_status_combo_changed(self, index: int) -> None:
        """Handle status combo selection change."""
        if index < 0 or self._current_paper_id is None:
            return
        new_status = self._status_combo.itemData(index)
        if isinstance(new_status, PaperStatus):
            self.status_changed.emit(self._current_paper_id, new_status)

    # ------------------------------------------------------------------
    # Notes auto-save
    # ------------------------------------------------------------------

    def _on_notes_text_changed(self) -> None:
        """Restart the auto-save debounce timer on each edit."""
        if self._current_paper_id is not None:
            self._save_timer.start(self._AUTO_SAVE_DELAY)

    def _save_notes(self) -> None:
        """Emit the notes_changed signal with the current notes text."""
        if self._current_paper_id is None:
            return
        text = self._notes_text.toPlainText()
        self.notes_changed.emit(self._current_paper_id, text)

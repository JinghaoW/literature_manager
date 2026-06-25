"""Left panel — status filter navigation."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from database.models import PaperStatus


class LeftPanel(QWidget):
    """Navigation panel with status filter buttons.

    Emits a signal when the user selects a status filter.
    """

    filter_changed = Signal(object)  # PaperStatus or None (for All)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the left panel."""
        super().__init__(parent)
        self._buttons: dict[PaperStatus | None, QPushButton] = {}
        self._active_filter: PaperStatus | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the panel layout and widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel("Papers")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # All Papers
        btn_all = self._make_button("All Papers")
        btn_all.clicked.connect(lambda: self._on_filter_clicked(None))
        self._buttons[None] = btn_all
        layout.addWidget(btn_all)

        layout.addSpacing(8)

        # Status filters
        for status in PaperStatus:
            btn = self._make_button(status.value)
            btn.clicked.connect(
                lambda checked, s=status: self._on_filter_clicked(s)
            )
            self._buttons[status] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Select "All Papers" by default
        self._on_filter_clicked(None)

    def _make_button(self, text: str) -> QPushButton:
        """Create a styled navigation button."""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setMinimumHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                background: transparent;
            }
            QPushButton:checked {
                background: #3a6ea5;
                color: white;
            }
            QPushButton:hover:!checked {
                background: #e0e0e0;
            }
        """)
        return btn

    def update_counts(self, counts: dict[PaperStatus | None, int]) -> None:
        """Update the button labels with paper counts.

        Args:
            counts: Mapping from status (None=All) to count.
        """
        for status, btn in self._buttons.items():
            count = counts.get(status, 0)
            label = btn.text().split(" (")[0]  # strip old count
            btn.setText(f"{label} ({count})")

    def _on_filter_clicked(self, status: PaperStatus | None) -> None:
        """Handle a filter button click."""
        # Uncheck all buttons first.
        for btn in self._buttons.values():
            btn.setChecked(False)

        # Check the clicked button.
        if status in self._buttons:
            self._buttons[status].setChecked(True)

        self._active_filter = status
        self.filter_changed.emit(status)

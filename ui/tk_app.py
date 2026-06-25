"""Tkinter desktop UI — fast native interface, direct DB access."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from typing import Any

from database.manager import DatabaseManager
from database.models import Paper, PaperStatus
from pdf.importer import PdfImporter
from pdf.annotations import extract_annotations, extract_highlighted_text
from utils.similarity import find_related_papers
from utils.logger import get_logger
from ai.provider import load_config, save_config, create_client, config_path, default_config
from ui.graph_view import GraphView

_log = get_logger("ui.tk_app")

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 14, "bold")

STATUS_COLORS: dict[PaperStatus, str] = {
    PaperStatus.UNREAD: "#f0f0f0",
    PaperStatus.READING: "#cce5ff",
    PaperStatus.READ: "#d4edda",
}


class TkApp:
    """Main tkinter application window."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or DatabaseManager()
        self._all_papers: list[Paper] = []
        self._filtered: list[Paper] = []
        self._current: Paper | None = None
        self._active_filter: PaperStatus | None = None
        self._search_text = ""
        self._notes_save_id: str | None = None
        self._showing_graph = False

        self._root = tk.Tk()
        self._root.title("Paper Notes")
        self._root.geometry("1400x900")
        self._root.minsize(1000, 650)

        self._build_ui()
        self._load_provider_status()
        self._refresh()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the three-panel tkinter layout."""
        # Container using pack — reliable collapse/expand.
        self._main_area = ttk.Frame(self._root)
        self._main_area.pack(fill=tk.BOTH, expand=True)

        # --- Left panel ---
        left = ttk.Frame(self._main_area, width=180)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)
        self._build_left(left)

        # --- Center panel ---
        center = ttk.Frame(self._main_area)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_center(center)

        # --- Right panel ---
        self._right_frame = ttk.Frame(self._main_area, width=420)
        self._right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self._right_frame.pack_propagate(False)
        self._build_right(self._right_frame)

        # Menu
        menubar = tk.Menu(self._root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import Folder...", command=self._import_folder, accelerator="Ctrl+I")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        self._root.config(menu=menubar)
        self._root.bind_all("<Control-i>", lambda e: self._import_folder())
        self._root.bind_all("<Delete>", lambda e: self._delete_paper())

    # ------------------------------------------------------------------
    # Left panel
    # ------------------------------------------------------------------

    def _build_left(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, padx=10, pady=(10, 8))
        ttk.Label(header, text="Papers", font=FONT_BOLD).pack(side=tk.LEFT)
        ttk.Button(header, text="↻", width=3, command=self._refresh).pack(side=tk.RIGHT)

        self._count_labels: dict[str, tk.Label] = {}
        self._filter_buttons: dict[str, ttk.Button] = {}

        for key, label in [("all", "All Papers"), ("unread", "Unread"), ("reading", "Reading"), ("read", "Read")]:
            btn = ttk.Button(parent, text=label, command=lambda k=key: self._on_filter(k))
            btn.pack(fill=tk.X, padx=8, pady=1)
            self._filter_buttons[key] = btn

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=8)

        self._graph_btn = ttk.Button(parent, text="Graph View", command=self._toggle_graph)
        self._graph_btn.pack(fill=tk.X, padx=8, pady=2)

        ttk.Button(parent, text="Import Folder", command=self._import_folder).pack(fill=tk.X, padx=8, pady=2)

        # LLM Config
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=(16, 4))
        self._provider_label = ttk.Label(parent, text="LLM: not configured", font=FONT_SMALL, foreground="gray")
        self._provider_label.pack(padx=10, anchor="w")
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Button(btn_row, text="Open Config", command=self._open_config_file).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="New Config", command=self._create_config_file).pack(side=tk.LEFT)
        self._api_status = ttk.Label(parent, text="", font=("Segoe UI", 8))
        self._api_status.pack(padx=10, anchor="w")

    # ------------------------------------------------------------------
    # Center panel
    # ------------------------------------------------------------------

    def _build_center(self, parent: ttk.Frame) -> None:
        # Search
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, padx=4, pady=4)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search())
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, font=FONT)
        search_entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        ttk.Button(search_frame, text="X", width=3, command=self._clear_search).pack(side=tk.RIGHT)

        # Paper list with scrollbar.
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self._listbox = tk.Listbox(list_frame, font=FONT, selectmode=tk.SINGLE, activestyle="none")
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)

        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # Mousewheel scrolling.
        self._listbox.bind("<MouseWheel>", lambda e: self._listbox.yview_scroll(int(-e.delta/60), "units"))

        self._listbox.bind("<<ListboxSelect>>", self._on_select)
        self._listbox.bind("<Double-Button-1>", self._on_double_click)

        # Graph view (hidden initially).
        self._graph = GraphView(parent, bg="#fafafa")
        self._graph.bind("<<GraphNodeSelected>>", self._on_graph_node)
        self._graph.bind("<<GraphNodeDeselected>>", lambda _: self._hide_detail())
        self._graph.bind("<<GraphNodeOpenPDF>>", self._on_graph_dbl_click)
        self._graph.pack_forget()
        # Keep refs to list frames for toggle.
        self._list_container = list_frame
        self._search_container = search_frame

    # ------------------------------------------------------------------
    # Right panel
    # ------------------------------------------------------------------

    def _build_right(self, parent: ttk.Frame) -> None:
        # Collapse toggle header.
        self._right_header = ttk.Frame(parent)
        self._right_header.pack(fill=tk.X)
        self._right_collapse_btn = ttk.Button(self._right_header, text="◀", width=3,
                                               command=self._toggle_right_panel)
        self._right_collapse_btn.pack(side=tk.RIGHT, padx=4, pady=2)
        ttk.Label(self._right_header, text="Details", font=FONT_BOLD).pack(side=tk.LEFT, padx=12, pady=2)

        # Scrollable canvas for detail content.
        self._right_body = ttk.Frame(parent)
        self._right_body.pack(fill=tk.BOTH, expand=True)
        self._detail_canvas = canvas = tk.Canvas(self._right_body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._right_body, orient=tk.VERTICAL, command=canvas.yview)
        self._detail_frame = ttk.Frame(canvas)
        self._right_panel_collapsed = False

        self._detail_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mousewheel scroll on canvas.
        def _scroll_canvas(event):
            canvas.yview_scroll(int(-event.delta / 60), "units")
        canvas.bind("<MouseWheel>", _scroll_canvas)
        # Also bind to the inner frame so wheel works when hovering content.
        self._detail_frame.bind("<MouseWheel>", _scroll_canvas)

        # Dynamically resize inner frame to match canvas width.
        self._detail_win = canvas.create_window((0, 0), window=self._detail_frame, anchor="nw")
        canvas.bind("<Configure>", self._on_canvas_resize)

        # Placeholder
        self._placeholder = ttk.Label(self._detail_frame, text="Select a paper to view details", font=FONT, foreground="gray")
        self._placeholder.pack(pady=80)

        # Detail widgets (initially hidden).
        self._detail_widgets: dict[str, Any] = {}

        # Title — Text widget for proper multi-line wrapping.
        self._detail_widgets["title"] = tk.Text(
            self._detail_frame, font=FONT_TITLE, wrap=tk.WORD, height=3,
            relief=tk.FLAT, padx=0, pady=0, borderwidth=0,
            state=tk.DISABLED, cursor="",
        )

        # Status row
        status_frame = ttk.Frame(self._detail_frame)
        ttk.Label(status_frame, text="Status:", font=FONT_BOLD).pack(side=tk.LEFT, padx=(0, 6))
        self._status_var = tk.StringVar(value="Unread")
        status_combo = ttk.Combobox(status_frame, textvariable=self._status_var, values=["Unread", "Reading", "Read"], state="readonly", width=10)
        status_combo.pack(side=tk.LEFT)
        status_combo.bind("<<ComboboxSelected>>", self._on_status_change)
        self._detail_widgets["status_combo"] = status_combo

        ttk.Button(status_frame, text="Open PDF", command=self._open_pdf).pack(side=tk.LEFT, padx=10)
        ttk.Button(status_frame, text="Rename PDF", command=self._rename_pdf).pack(side=tk.LEFT, padx=4)
        ttk.Button(status_frame, text="Delete", command=self._delete_paper).pack(side=tk.RIGHT, padx=0)
        self._detail_widgets["status_frame"] = status_frame

        # Quick status buttons.
        quick_frame = ttk.Frame(self._detail_frame)
        for st, lbl in [(PaperStatus.UNREAD, "Unread"), (PaperStatus.READING, "Reading"), (PaperStatus.READ, "Read")]:
            ttk.Button(quick_frame, text=lbl,
                       command=lambda s=st: self._set_status(s)).pack(side=tk.LEFT, padx=2)
        self._detail_widgets["quick_status"] = quick_frame

        # Separator
        self._detail_widgets["sep1"] = ttk.Separator(self._detail_frame, orient=tk.HORIZONTAL)

        # Summary
        self._detail_widgets["summary_label"] = ttk.Label(self._detail_frame, text="Summary", font=FONT_BOLD)
        self._detail_widgets["summary_text"] = tk.Label(self._detail_frame, text="", font=FONT_SMALL, wraplength=460, anchor="w", justify="left", foreground="gray")
        ttk.Button(self._detail_frame, text="AI Analyze", command=self._analyze).pack(anchor="w", pady=(2, 0))

        # Keywords
        self._detail_widgets["kw_label"] = ttk.Label(self._detail_frame, text="Keywords", font=FONT_BOLD)
        self._detail_widgets["kw_text"] = tk.Label(self._detail_frame, text="", font=FONT_SMALL, wraplength=460, anchor="w", justify="left", foreground="#3a6ea5")

        # Notes
        self._detail_widgets["notes_label"] = ttk.Label(self._detail_frame, text="Notes (Markdown)", font=FONT_BOLD)
        self._notes_text = tk.Text(self._detail_frame, font=FONT, height=14, wrap=tk.WORD, padx=6, pady=4, relief=tk.SOLID, borderwidth=1)
        self._notes_text.bind("<FocusOut>", self._save_notes)
        self._detail_widgets["notes"] = self._notes_text

        # Import annotations button
        ttk.Button(self._detail_frame, text="Import PDF Annotations", command=self._import_annotations).pack(anchor="w", pady=(2, 0))

        # Annotations
        self._detail_widgets["annot_label"] = ttk.Label(self._detail_frame, text="PDF Annotations", font=FONT_BOLD)
        self._detail_widgets["annot_text"] = tk.Label(self._detail_frame, text="", font=FONT_SMALL, wraplength=460, anchor="w", justify="left")

        # Related papers
        self._detail_widgets["rel_label"] = ttk.Label(self._detail_frame, text="Related Papers", font=FONT_BOLD)
        self._detail_widgets["rel_list"] = ttk.Frame(self._detail_frame)

    # ------------------------------------------------------------------
    # Filters & search
    # ------------------------------------------------------------------

    def _on_filter(self, key: str) -> None:
        mapping: dict[str, PaperStatus | None] = {
            "all": None, "unread": PaperStatus.UNREAD,
            "reading": PaperStatus.READING, "read": PaperStatus.READ,
        }
        self._active_filter = mapping[key]
        self._current = None
        self._apply_filters()

    def _on_search(self) -> None:
        self._search_text = self._search_var.get().strip()
        self._current = None
        self._apply_filters()

    def _clear_search(self) -> None:
        self._search_var.set("")

    def _apply_filters(self) -> None:
        papers = self._db.list_papers(status=self._active_filter)
        if self._search_text:
            q = self._search_text.lower()
            papers = [p for p in papers
                      if q in p.title.lower()
                      or (p.keywords and q in p.keywords.lower())
                      or (p.notes and q in p.notes.lower())]
        self._filtered = papers
        self._render_list()

    # ------------------------------------------------------------------
    # Paper list
    # ------------------------------------------------------------------

    def _render_list(self) -> None:
        self._listbox.delete(0, tk.END)
        for p in self._filtered:
            title = p.title if len(p.title) <= 65 else p.title[:62] + "..."
            date = p.created_time.strftime("%Y-%m-%d") if p.created_time else ""
            self._listbox.insert(tk.END, f"{title}  [{p.status.value}]  {date}")
        self._hide_detail()

    def _on_select(self, event: Any) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        paper = self._filtered[sel[0]]
        self._load_paper(paper)

    def _on_double_click(self, event: Any) -> None:
        sel = self._listbox.curselection()
        if sel:
            self._open_pdf_file(self._filtered[sel[0]].file_path)

    def _toggle_right_panel(self) -> None:
        """Collapse/expand the entire right panel."""
        self._right_panel_collapsed = not self._right_panel_collapsed
        if self._right_panel_collapsed:
            self._right_frame.pack_forget()
            self._right_collapse_btn.configure(text="◀")
            # Floating restore button.
            self._restore_btn = ttk.Button(self._root, text="◀ Details", width=10,
                                           command=self._toggle_right_panel)
            self._restore_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-4, y=4)
        else:
            if hasattr(self, "_restore_btn"):
                self._restore_btn.destroy()
            self._right_frame.pack(side=tk.RIGHT, fill=tk.Y)
            self._right_collapse_btn.configure(text="◀")

    def _toggle_graph(self) -> None:
        """Switch between list view and graph view."""
        self._showing_graph = not self._showing_graph
        if self._showing_graph:
            self._root.geometry("1500x950")  # more space for graph
            self._search_container.pack_forget()
            self._list_container.pack_forget()
            self._graph.pack(fill=tk.BOTH, expand=True)
            self._graph_btn.configure(text="List View")
            # Build graph from all papers (respect filter).
            papers = self._db.list_papers(status=self._active_filter)
            self._graph.set_papers(papers)
        else:
            self._graph.pack_forget()
            self._search_container.pack(fill=tk.X, padx=4, pady=4)
            self._list_container.pack(fill=tk.BOTH, expand=True)
            self._graph_btn.configure(text="Graph View")

    def _on_graph_node(self, event: tk.Event) -> None:
        """Handle graph node click — load paper detail, auto-expand panel."""
        # Try event data first, fall back to graph's selected id.
        pid_str = getattr(event, "data", None)
        if pid_str is not None:
            paper_id = int(pid_str)
        elif self._graph._sel is not None:
            paper_id = self._graph._sel
        else:
            return
        paper = self._db.get_paper(paper_id)
        if paper:
            if self._right_panel_collapsed:
                self._toggle_right_panel()
            self._load_paper(paper)

    def _on_graph_dbl_click(self, event: tk.Event) -> None:
        """Handle graph node double-click — open PDF."""
        pid_str = getattr(event, "data", None)
        if pid_str is not None:
            paper_id = int(pid_str)
        elif self._graph._sel is not None:
            paper_id = self._graph._sel
        elif self._current:
            self._open_pdf_file(self._current.file_path)
            return
        else:
            return
        paper = self._db.get_paper(paper_id)
        if paper:
            self._open_pdf_file(paper.file_path)

    # ------------------------------------------------------------------
    # Paper detail
    # ------------------------------------------------------------------

    def _on_canvas_resize(self, event: Any) -> None:
        """Keep the inner frame width matched to the canvas."""
        self._detail_canvas.itemconfig(self._detail_win, width=event.width)

    def _load_paper(self, paper: Paper) -> None:
        self._current = paper

        # Show all detail widgets, hide placeholder.
        self._placeholder.pack_forget()
        for w in self._detail_widgets.values():
            if isinstance(w, tk.Widget):
                w.pack_forget()

        # Title — use Text widget for proper wrapping.
        title_widget = self._detail_widgets["title"]
        title_widget.configure(state=tk.NORMAL)
        title_widget.delete("1.0", tk.END)
        title_widget.insert("1.0", paper.title)
        title_widget.configure(state=tk.DISABLED, height=min(4, paper.title.count("\n") + 2 + len(paper.title) // 60))
        title_widget.pack(fill=tk.X, padx=12, pady=(12, 4))

        # Status
        self._status_var.set(paper.status.value)
        self._detail_widgets["status_frame"].pack(fill=tk.X, padx=12, pady=2)
        self._detail_widgets["quick_status"].pack(fill=tk.X, padx=12, pady=(2, 0))

        # Separator
        self._detail_widgets["sep1"].pack(fill=tk.X, padx=12, pady=6)

        # Summary
        self._detail_widgets["summary_label"].pack(fill=tk.X, padx=12, pady=(6, 0))
        summary = paper.summary or "No summary yet."
        self._detail_widgets["summary_text"].configure(text=summary, foreground="gray" if not paper.summary else "black")
        self._detail_widgets["summary_text"].pack(fill=tk.X, padx=12)

        # Keywords
        self._detail_widgets["kw_label"].pack(fill=tk.X, padx=12, pady=(16, 0))
        kw = paper.keywords or "—"
        self._detail_widgets["kw_text"].configure(text=kw)
        self._detail_widgets["kw_text"].pack(fill=tk.X, padx=12)

        # Notes
        self._detail_widgets["notes_label"].pack(fill=tk.X, padx=12, pady=(16, 0))
        self._notes_text.delete("1.0", tk.END)
        self._notes_text.insert("1.0", paper.notes or "")
        self._notes_text.pack(fill=tk.X, padx=12, pady=(2, 0))

        # Annotations
        self._load_annotations(paper)

        # Related
        self._load_related(paper)

    def _hide_detail(self) -> None:
        self._current = None
        for w in self._detail_widgets.values():
            if isinstance(w, tk.Widget):
                w.pack_forget()
        # Reset title Text widget.
        tw = self._detail_widgets["title"]
        tw.configure(state=tk.NORMAL)
        tw.delete("1.0", tk.END)
        tw.configure(state=tk.DISABLED)
        self._placeholder.pack(pady=80)

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    def _load_annotations(self, paper: Paper) -> None:
        try:
            anns = extract_annotations(paper.file_path)
            hl = extract_highlighted_text(paper.file_path)
        except Exception:
            anns, hl = [], ""

        self._detail_widgets["annot_label"].pack(fill=tk.X, padx=12, pady=(16, 0))

        if not anns and not hl:
            self._detail_widgets["annot_text"].configure(text="No annotations found", foreground="gray")
            self._detail_widgets["annot_text"].pack(fill=tk.X, padx=12)
            return

        lines = []
        for a in anns:
            lines.append(f"[{a.annot_type}] p.{a.page}: {a.text}")
        if hl:
            lines.append("Highlighted: " + hl[:300])
        self._detail_widgets["annot_text"].configure(text="\n".join(lines), foreground="black")
        self._detail_widgets["annot_text"].pack(fill=tk.X, padx=12)

    def _import_annotations(self) -> None:
        if not self._current:
            return
        try:
            anns = extract_annotations(self._current.file_path)
            hl = extract_highlighted_text(self._current.file_path)
        except Exception:
            return

        parts = []
        if anns:
            parts.append("## PDF Annotations\n" + "\n".join(f"- [{a.annot_type}] p.{a.page}: {a.text}" for a in anns))
        if hl:
            parts.append("## Highlighted Text\n" + hl)

        if parts:
            existing = self._notes_text.get("1.0", tk.END).strip()
            new = (existing + "\n\n" + "\n\n".join(parts)).strip() if existing else "\n\n".join(parts)
            self._notes_text.delete("1.0", tk.END)
            self._notes_text.insert("1.0", new)
            self._save_notes()

    # ------------------------------------------------------------------
    # Related papers
    # ------------------------------------------------------------------

    def _load_related(self, paper: Paper) -> None:
        self._detail_widgets["rel_label"].pack(fill=tk.X, padx=12, pady=(16, 0))

        # Clear old related items.
        rel_frame = self._detail_widgets["rel_list"]
        for child in rel_frame.winfo_children():
            child.destroy()

        all_papers = self._db.list_papers()
        related = find_related_papers(paper, all_papers, top_n=5, min_score=0.05)

        if not related:
            ttk.Label(rel_frame, text="No related papers", font=FONT_SMALL, foreground="gray").pack(anchor="w")
        else:
            for rp, score in related:
                pct = int(round(score * 100))
                lbl = tk.Label(rel_frame, text=f"▸ {rp.title}  ({pct}%)", font=FONT_SMALL, fg="#3a6ea5", cursor="hand2", anchor="w")
                lbl.pack(fill=tk.X, pady=1)
                lbl.bind("<Button-1>", lambda e, p=rp: self._navigate_to(p))

        rel_frame.pack(fill=tk.X, padx=12, pady=(0, 40))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_pdf(self) -> None:
        if self._current:
            self._open_pdf_file(self._current.file_path)

    def _open_pdf_file(self, path: str) -> None:
        if not os.path.isfile(path):
            messagebox.showerror("Error", f"File not found:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open:\n{exc}")

    def _set_status(self, status: PaperStatus) -> None:
        """Quick set status from button — keep detail panel open."""
        if not self._current:
            return
        self._db.update_paper(self._current.id, status=status)
        self._current.status = status
        self._status_var.set(status.value)
        self._update_counts()
        # Re-filter and re-render list, but DON'T call _hide_detail.
        self._filtered = self._db.list_papers(status=self._active_filter)
        if self._search_text:
            q = self._search_text.lower()
            self._filtered = [p for p in self._filtered
                              if q in p.title.lower()
                              or (p.keywords and q in p.keywords.lower())
                              or (p.notes and q in p.notes.lower())]
        self._render_list_only()
        # Re-select current paper in list.
        if self._current:
            for i, p in enumerate(self._filtered):
                if p.id == self._current.id:
                    self._listbox.selection_clear(0, tk.END)
                    self._listbox.selection_set(i)
                    self._listbox.see(i)
                    break

    def _render_list_only(self) -> None:
        """Update paper list without clearing detail panel."""
        self._listbox.delete(0, tk.END)
        for p in self._filtered:
            title = p.title[:62] + ("..." if len(p.title) > 62 else "")
            date = p.created_time.strftime("%Y-%m-%d") if p.created_time else ""
            self._listbox.insert(tk.END, f"{title}  [{p.status.value}]  {date}")

    def _on_status_change(self, event: Any) -> None:
        if not self._current:
            return
        new_status = PaperStatus(self._status_var.get())
        self._db.update_paper(self._current.id, status=new_status)
        self._apply_filters()
        self._update_counts()

    def _save_notes(self, event: Any | None = None) -> None:
        if not self._current:
            return
        text = self._notes_text.get("1.0", tk.END).strip()
        self._db.update_paper(self._current.id, notes=text)

    def _rename_pdf(self) -> None:
        """Re-extract title from PDF, let user edit, update DB, rename file."""
        if not self._current:
            return
        old_path = Path(self._current.file_path)
        if not old_path.is_file():
            messagebox.showerror("Error", f"File not found:\n{old_path}")
            return

        # Extract title from the PDF first page.
        from pdf.title_extractor import extract_title
        extracted = extract_title(old_path)

        # Simple dialog: show extracted title, let user edit.
        top = tk.Toplevel(self._root)
        top.title("Rename PDF")
        top.geometry("500x200")
        top.transient(self._root)
        top.grab_set()

        ttk.Label(top, text="Current title:", font=("Segoe UI", 9)).pack(padx=12, pady=(12, 0), anchor="w")
        ttk.Label(top, text=self._current.title, font=("Segoe UI", 9, "bold"), foreground="gray").pack(padx=20, anchor="w")

        ttk.Label(top, text="New title:", font=("Segoe UI", 9)).pack(padx=12, pady=(8, 0), anchor="w")
        title_row = ttk.Frame(top)
        title_row.pack(padx=12, pady=4, fill=tk.X)
        title_var = tk.StringVar(value=extracted or self._current.title)
        entry = ttk.Entry(title_row, textvariable=title_var, font=("Segoe UI", 10))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.select_range(0, tk.END)
        entry.focus_set()

        ai_btn = ttk.Button(title_row, text="AI Suggest", command=lambda: _ai_title())
        ai_btn.pack(side=tk.RIGHT, padx=(6, 0))

        status_lbl = ttk.Label(top, text="", font=("Segoe UI", 8), foreground="gray")
        status_lbl.pack(padx=12, anchor="w")

        def _ai_title():
            cfg = load_config()
            if not cfg or cfg.get("api_key", "").strip() in ("", "YOUR_API_KEY_HERE"):
                status_lbl.configure(text="No API configured — set up in left panel", foreground="red")
                return
            ai_btn.configure(state="disabled")
            status_lbl.configure(text="Reading PDF and asking AI...", foreground="gray")
            top.update()
            try:
                from ai.analyzer import extract_paper_text
                from ai.provider import create_client
                text = extract_paper_text(old_path, max_pages=1)
                client = create_client(cfg)
                new_title = client.suggest_title(text)
                if new_title:
                    title_var.set(new_title)
                    status_lbl.configure(text="AI title loaded", foreground="green")
                else:
                    status_lbl.configure(text="AI returned empty — try again", foreground="red")
            except Exception as e:
                status_lbl.configure(text=str(e)[:80], foreground="red")
            finally:
                ai_btn.configure(state="normal")

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=12)

        def do_rename():
            new_title = title_var.get().strip()
            if not new_title:
                messagebox.showwarning("Warning", "Title cannot be empty.", parent=top)
                return
            # Sanitize for filename.
            safe = "".join(c for c in new_title if c.isalnum() or c in " _-()")[:100].strip()
            new_path = old_path.parent / f"{safe}.pdf"
            if new_path.exists() and new_path != old_path:
                ow = messagebox.askyesno("Overwrite",
                                         f"Target exists:\n{new_path.name}\n\nOverwrite?", parent=top)
                if not ow:
                    return
            try:
                if old_path != new_path:
                    old_path.rename(new_path)
                self._db.update_paper(self._current.id, title=new_title,
                                      file_path=str(new_path))
                self._current.title = new_title
                self._current.file_path = str(new_path)
                self._load_paper(self._current)
                top.destroy()
            except Exception as exc:
                messagebox.showerror("Error", f"Failed:\n{exc}", parent=top)

        ttk.Button(btn_frame, text="Rename", command=do_rename).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=top.destroy).pack(side=tk.LEFT, padx=4)

    def _navigate_to(self, paper: Paper) -> None:
        """Ask before navigating to a related paper."""
        ok = messagebox.askyesno(
            "Navigate",
            f"Jump to this paper?\n\n{paper.title[:100]}",
            parent=self._root,
        )
        if ok:
            self._load_paper(paper)

    def _delete_paper(self) -> None:
        if not self._current:
            return
        title = self._current.title
        ok = messagebox.askyesno(
            "Delete Paper",
            f"Delete this paper?\n\n{title}\n\nThis does NOT delete the PDF file.",
            icon="warning",
        )
        if not ok:
            return
        self._db.delete_paper(self._current.id)
        self._current = None
        self._refresh()

    def _import_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder with PDFs")
        if not folder:
            return
        importer = PdfImporter(self._db)
        result = importer.import_folder(folder)
        self._refresh()
        messagebox.showinfo("Import Complete",
                            f"Imported: {result.total_imported}\n"
                            f"Skipped: {result.total_skipped}\n"
                            f"Failed: {result.total_failed}")

    def _analyze(self) -> None:
        if not self._current:
            return

        cfg = load_config()
        if not cfg or cfg.get("api_key", "").strip() in ("", "YOUR_API_KEY_HERE"):
            self._api_status.configure(text="No config — click New Config", foreground="red")
            return

        try:
            from ai.analyzer import analyze_paper
            client = create_client(cfg)
            self._api_status.configure(text="Analyzing...", foreground="gray")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        self._detail_widgets["summary_text"].configure(text="Analyzing...", foreground="gray")
        self._root.update()

        result = analyze_paper(self._current, self._db, client)
        if result.success:
            self._api_status.configure(text="Analysis complete", foreground="green")
            self._load_paper(self._db.get_paper(self._current.id))
        else:
            self._api_status.configure(text="Failed", foreground="red")
            self._detail_widgets["summary_text"].configure(text=f"Failed: {result.error}", foreground="red")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _update_counts(self) -> None:
        all_count = self._db.count_papers()
        unread = self._db.count_papers(status=PaperStatus.UNREAD)
        reading = self._db.count_papers(status=PaperStatus.READING)
        read = self._db.count_papers(status=PaperStatus.READ)

        self._filter_buttons["all"].configure(text=f"All Papers ({all_count})")
        self._filter_buttons["unread"].configure(text=f"Unread ({unread})")
        self._filter_buttons["reading"].configure(text=f"Reading ({reading})")
        self._filter_buttons["read"].configure(text=f"Read ({read})")

    def _load_provider_status(self) -> None:
        """Show the current LLM provider from config file."""
        cfg = load_config()
        if cfg and cfg.get("api_key", "").strip() not in ("", "YOUR_API_KEY_HERE"):
            provider = cfg.get("provider", "?")
            model = cfg.get("model", "?")
            self._provider_label.configure(
                text=f"LLM: {provider} / {model}", foreground="green"
            )
            self._api_status.configure(text="Ready", foreground="green")
        else:
            self._provider_label.configure(text="LLM: not configured", foreground="gray")
            self._api_status.configure(text="Click New Config to set up", foreground="gray")

    def _open_config_file(self) -> None:
        """Open the config file in the system editor."""
        p = config_path()
        if not p.is_file():
            messagebox.showinfo("Info",
                                f"Config file not found.\nClick 'New Config' to create one.\n\nPath: {p}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to open:\n{exc}")

    def _create_config_file(self) -> None:
        """Create a new config file from a template."""
        # Ask which provider.
        p = config_path()
        choice = messagebox.askquestion(
            "New Config",
            f"Create config for Claude?\n\n"
            f"Yes = Claude (Anthropic)\nNo = choose from all providers\n\n"
            f"File: {p}",
        )
        if choice == "yes":
            provider = "claude"
        else:
            # Simple dialog: pick from list via a small popup.
            top = tk.Toplevel(self._root)
            top.title("Choose Provider")
            top.geometry("250x180")
            top.transient(self._root)
            top.grab_set()
            ttk.Label(top, text="Select LLM Provider:", font=FONT_BOLD).pack(pady=8)
            result = {"provider": None}

            def pick(prov):
                result["provider"] = prov
                top.destroy()

            for prov, label in [("claude", "Claude (Anthropic)"), ("openai", "OpenAI (GPT)"),
                                 ("deepseek", "DeepSeek"), ("ollama", "Ollama (local)")]:
                ttk.Button(top, text=label, command=lambda p=prov: pick(p)).pack(fill=tk.X, padx=20, pady=2)
            self._root.wait_window(top)
            provider = result["provider"]
            if not provider:
                return

        cfg = default_config(provider)
        save_config(cfg)
        self._load_provider_status()
        self._open_config_file()
        messagebox.showinfo(
            "Config Created",
            f"Config file created at:\n{p}\n\n"
            f"1. Replace YOUR_API_KEY_HERE with your real key\n"
            f"2. Adjust model if needed\n"
            f"3. Save the file and close it\n"
            f"4. Click 'AI Analyze' to use it",
        )

    def _refresh(self) -> None:
        self._update_counts()
        self._apply_filters()

    def run(self) -> None:
        self._root.mainloop()

"""Graph view — clean grid layout, guaranteed no label overlap.

Papers arranged in a grid with cell sizes computed from label widths.
Edges drawn between connected papers. Force layout removed entirely.
"""

from __future__ import annotations

import math
import tkinter as tk
from collections import defaultdict

from database.models import Paper, PaperStatus
from utils.similarity import jaccard_similarity, _keyword_set

# Theme.
_BG = "#ebecf3"; _TEXT = "#333"; _TEXT_MUTED = "#9d9da1"
_EDGE = "#d0d0d8"; _EDGE_HL = "#279dd5"; _EDGE_DIM = "#e8e8ec"
_NODE = "#d1ceef"; _NODE_BORDER = "#b0add8"
_NODE_SELECT = "#279dd5"; _NODE_HOVER = "#60c0ee"
_NODE_READ = "#8add8a"; _NODE_READING = "#60dce2"
_NODE_DIM = "#ededf0"; _NODE_DIM_BORDER = "#e0e0e4"

_EDGE_MIN = 0.07
_FONT = ("Segoe UI", 9)
_NODE_R = 10
_CELL_PAD_X = 30   # horizontal gap between cells
_CELL_PAD_Y = 30   # vertical gap between rows
_MARGIN = 60
_SCALE = 1.0


def _label_width(text: str) -> int:
    return int(len(text) * _FONT[1] * 0.55) + 10


class GraphView(tk.Canvas):
    """Grid-based paper graph — guaranteed no label overlap."""

    def __init__(self, parent: tk.Widget, **kw: object) -> None:
        kw.setdefault("bg", _BG); kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._papers: dict[int, Paper] = {}
        self._edges: list[tuple[int, int, float]] = []
        self._pos: dict[int, tuple[float, float]] = {}
        self._adj: dict[int, set[int]] = defaultdict(set)
        self._deg: dict[int, int] = defaultdict(int)

        self._sel: int | None = None
        self._hov: int | None = None
        self._active: set[int] = set()
        self._dragging: int | None = None
        self._drag_start = (0.0, 0.0)
        self._scale = 1.0
        self._dirty = True

        self.bind("<Button-1>", self._click)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Double-Button-1>", self._dbl_click)
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Motion>", self._move)
        self.bind("<Configure>", self._resize)
        # Keyboard.
        self.bind("<Control-plus>", lambda e: self._zoom_step(1.1))
        self.bind("<Control-equal>", lambda e: self._zoom_step(1.1))
        self.bind("<Control-minus>", lambda e: self._zoom_step(0.9))
        self.bind("<Control-Up>", lambda e: self._pan(0, 30))
        self.bind("<Control-Down>", lambda e: self._pan(0, -30))
        self.bind("<Control-Left>", lambda e: self._pan(30, 0))
        self.bind("<Control-Right>", lambda e: self._pan(-30, 0))
        self.focus_set()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def set_papers(self, papers: list[Paper]) -> None:
        self._papers = {p.id: p for p in papers}
        self._build_edges()
        self._grid_layout()
        self._sel = None; self._active.clear(); self._dirty = True
        self._render()

    def reselect(self, paper_id: int) -> None:
        self._sel = paper_id; self._update_active(); self._dirty = True
        self._render()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_edges(self) -> None:
        self._adj.clear(); self._deg.clear(); self._edges.clear()
        pids = list(self._papers.keys())
        kw = {pid: _keyword_set(self._papers[pid]) for pid in pids}
        for i in range(len(pids)):
            a = pids[i]
            if not kw[a]: continue
            for j in range(i + 1, len(pids)):
                b = pids[j]
                if not kw[b]: continue
                s = jaccard_similarity(kw[a], kw[b])
                if s >= _EDGE_MIN:
                    self._edges.append((a, b, s))
                    self._adj[a].add(b); self._adj[b].add(a)
                    self._deg[a] += 1; self._deg[b] += 1

    def _grid_layout(self) -> None:
        """Arrange papers in a grid — cells sized to fit labels."""
        self._pos.clear()
        if not self._papers:
            return

        # Sort papers by date for timeline ordering.
        papers = sorted(self._papers.values(),
                        key=lambda p: p.created_time.isoformat() if p.created_time else "2000")

        # Compute cell width per column: max label width in that column.
        # Use a fixed number of columns based on window width.
        w = self.winfo_width() or 1200
        cols = max(3, (w - 2 * _MARGIN) // 250)

        # Group papers into columns.
        col_papers: list[list[Paper]] = [[] for _ in range(cols)]
        for i, p in enumerate(papers):
            col_papers[i % cols].append(p)

        # Compute per-column widths.
        col_widths: list[int] = []
        for ci, cp in enumerate(col_papers):
            max_lw = max((_label_width(p.title[:50]) for p in cp), default=80)
            col_widths.append(max(_NODE_R * 2 + 40, max_lw + 30))

        # Position nodes.
        x_start = _MARGIN
        for ci, cp in enumerate(col_papers):
            cw = col_widths[ci]
            cx = x_start + cw // 2
            cell_h = _NODE_R * 2 + _FONT[1] * 2 + _CELL_PAD_Y + 20
            for ri, paper in enumerate(cp):
                cy = _MARGIN + _NODE_R + 20 + ri * cell_h
                self._pos[paper.id] = (cx, cy)
            x_start += cw + _CELL_PAD_X

    def _update_active(self) -> None:
        if self._sel is None: self._active.clear(); return
        seen = {self._sel}; q = [self._sel]
        for _ in range(2):
            nq = []; [nq.append(nb) for pid in q for nb in self._adj.get(pid, set()) if nb not in seen and not seen.add(nb)]
            q = nq
        self._active = seen

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self) -> None:
        if not self._dirty: return
        self._dirty = False
        self.delete("all")
        if not self._papers:
            w = self.winfo_width() or 900; h = self.winfo_height() or 650
            self.create_text(w // 2, h // 2, text="No papers to graph",
                             fill=_TEXT_MUTED, font=("Segoe UI", 13))
            return
        self._draw_edges(); self._draw_nodes(); self._draw_controls()

    def _draw_edges(self) -> None:
        for a, b, s in self._edges:
            x1, y1 = self._pos[a]; x2, y2 = self._pos[b]
            in_active = (not self._active) or (a in self._active and b in self._active)
            hl = self._sel in (a, b) or self._hov in (a, b)
            if not self._active or in_active:
                w = max(2.0, s * 5) if hl else max(1.0, s * 2)
                color = _EDGE_HL if hl else f"#{min(40+int(s*100),160):02x}{min(40+int(s*100),160):02x}{min(50+int(s*100),170):02x}"
            else:
                w = 0.5; color = _EDGE_DIM
            self.create_line(x1, y1, x2, y2, fill=color, width=w, tags="edge")

    def _draw_nodes(self) -> None:
        for pid, paper in self._papers.items():
            x, y = self._pos[pid]; r = _NODE_R
            is_sel = pid == self._sel; is_hov = pid == self._hov

            if is_sel or is_hov:
                fill = _NODE_SELECT; stroke = "#1a6faa"
            elif self._active and pid not in self._active:
                fill = _NODE_DIM; stroke = _NODE_DIM_BORDER
            elif paper.status == PaperStatus.READ:
                fill = _NODE_READ; stroke = "#5cb868"
            elif paper.status == PaperStatus.READING:
                fill = _NODE_READING; stroke = "#3db8bd"
            else:
                fill = _NODE; stroke = _NODE_BORDER

            if is_sel or is_hov:
                rr = r + (6 if is_sel else 3)
                self.create_oval(x - rr, y - rr, x + rr, y + rr,
                                 fill="", outline=_NODE_SELECT if is_sel else _NODE_HOVER,
                                 width=2.5 if is_sel else 1.5)

            self.create_oval(x - r, y - r, x + r, y + r,
                             fill=fill, outline=stroke, width=1.5)

            # Label — centered below node, with fixed max length.
            title = paper.title[:50]
            if len(paper.title) > 50: title += "..."
            lc = "#fff" if is_sel else (_TEXT_MUTED if (self._active and pid not in self._active) else _TEXT)
            self.create_text(x, y + r + 12, text=title, fill=lc, font=_FONT)

    def _draw_controls(self) -> None:
        w = self.winfo_width() or 900; h = self.winfo_height() or 650
        b = 28; g = 4
        cx = w - 100; cy = h - 120

        def btn(x, y, t, fs=12):
            self.create_rectangle(x, y, x + b, y + b, fill="#fff", outline="#ccc", tags="ctrl")
            self.create_text(x + b // 2, y + b // 2, text=t, fill=_TEXT, font=("Segoe UI", fs, "bold"), tags="ctrl")

        btn(cx, cy - b - g, "▲"); btn(cx - b - g, cy, "◀")
        btn(cx, cy, "⟲", 10); btn(cx + b + g, cy, "▶")
        btn(cx, cy + b + g, "▼")
        zx = cx + 2 * b + 2 * g + 12; zy = cy - b - g
        btn(zx, zy, "+"); btn(zx, zy + b + g, "−")

        self._ctrl = [
            (cx, cy - b - g, "up"), (cx - b - g, cy, "left"),
            (cx + b + g, cy, "right"), (cx, cy + b + g, "down"),
            (cx, cy, "fit"), (zx, zy, "+"), (zx, zy + b + g, "-"),
        ]

    def _hit_ctrl(self, cx: float, cy: float) -> str | None:
        b = 28
        for bx, by, name in getattr(self, "_ctrl", []):
            if bx <= cx <= bx + b and by <= cy <= by + b: return name
        return None

    def _zoom_step(self, f: float) -> None:
        self._scale *= f; self._scale = max(0.3, min(self._scale, 2.5))
        self._dirty = True; self._render()

    def _pan(self, dx: float, dy: float) -> None:
        for pid in self._pos:
            px, py = self._pos[pid]; self._pos[pid] = (px + dx, py + dy)
        self._dirty = True; self._render()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _hit(self, cx: float, cy: float) -> int | None:
        for pid in self._papers:
            px, py = self._pos[pid]; r = _NODE_R + 8
            if abs(cx - px) < r and abs(cy - py) < r and (cx - px) ** 2 + (cy - py) ** 2 < r * r:
                return pid
        return None

    def _click(self, event: tk.Event) -> None:
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        ctrl = self._hit_ctrl(cx, cy)
        if ctrl:
            if ctrl == "+": self._zoom_step(1.1)
            elif ctrl == "-": self._zoom_step(0.9)
            elif ctrl == "up": self._pan(0, 20)
            elif ctrl == "down": self._pan(0, -20)
            elif ctrl == "left": self._pan(20, 0)
            elif ctrl == "right": self._pan(-20, 0)
            elif ctrl == "fit": self._scale = 1.0; self._dirty = True; self._render()
            return
        pid = self._hit(cx, cy)
        if pid is None:
            self._sel = None; self._active.clear(); self._dirty = True
            self.event_generate("<<GraphNodeDeselected>>"); self._render(); return
        self._sel = pid; self._update_active()
        self._dragging = pid; self._drag_start = (self._pos[pid][0], self._pos[pid][1])
        self._dirty = True
        self.event_generate("<<GraphNodeSelected>>", data=str(pid))
        self._render()

    def _drag(self, event: tk.Event) -> None:
        if self._dragging is None: return
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        sx, sy = self._drag_start
        dx = cx - sx; dy = cy - sy
        if abs(dx) < 5 and abs(dy) < 5: return
        self._pos[self._dragging] = (cx, cy)
        self._drag_start = (cx, cy)
        self._dirty = True; self._render()

    def _release(self, _event: tk.Event) -> None:
        self._dragging = None

    def _dbl_click(self, event: tk.Event) -> None:
        if self._sel is not None:
            self.event_generate("<<GraphNodeOpenPDF>>", data=str(self._sel))

    def _move(self, event: tk.Event) -> None:
        if self._dragging is not None: return
        cx, cy = self.canvasx(event.x), self.canvasy(event.y)
        pid = self._hit(cx, cy)
        if pid != self._hov: self._hov = pid; self._dirty = True; self._render()

    def _zoom(self, event: tk.Event) -> None:
        f = 1.08 if event.delta > 0 else 0.92
        self._scale *= f; self._scale = max(0.3, min(self._scale, 2.5))
        self._dirty = True; self._render()

    def _resize(self, _event: tk.Event) -> None:
        if self._papers:
            self._grid_layout(); self._dirty = True; self._render()

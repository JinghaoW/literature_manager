# Paper Notes

Local-first academic paper manager for Windows: import PDFs, organize reading status, write notes, and run AI-assisted analysis.

## What it does

- Import PDFs recursively from a folder with duplicate detection (SHA-256 hash)
- Extract paper titles from PDF metadata/content
- Track reading status: **Unread / Reading / Read**
- Search papers by title, keywords, and notes
- Edit notes (Markdown-style plain text)
- Extract and import PDF annotations/highlights into notes
- Find related papers using keyword similarity
- Run AI analysis (summary + keywords + research area)
- Visualize the library in a graph view

## Current app mode

The default and actively used UI is **Tkinter** (`main.py` -> `ui/tk_app.py`).

There is also an optional Flask API + web UI under `web/` and legacy PySide6 UI files under `ui/`, but the Tkinter app is the primary entrypoint in this project.

## Tech stack

- Python 3.12+
- Tkinter (desktop UI, built into Python)
- SQLAlchemy + SQLite (`papers.db`)
- PyMuPDF (`fitz`) for PDF text/annotation extraction
- Anthropic SDK + OpenAI SDK for AI providers

## Requirements

Install the core dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` currently includes:

- `SQLAlchemy`
- `PyMuPDF`
- `anthropic`
- `openai`

If you want to run the optional web server, install Flask separately:

```bash
pip install flask
```

## Run the desktop app

```bash
python main.py
```

or use:

```bash
run.bat
```

## AI provider configuration

The app reads config from:

- project mode: `.paper_notes_config.json` in the project root
- packaged exe mode: `.paper_notes_config.json` next to the exe

You can create/edit this file from the left panel (**New Config** / **Open Config**).

Example:

```json
{
  "provider": "claude",
  "api_key": "YOUR_API_KEY_HERE",
  "model": "claude-haiku-4-5-20251001",
  "base_url": ""
}
```

Supported presets: `claude`, `openai`, `deepseek`, `ollama`.

## Project structure

```text
main.py                  # Desktop entrypoint
run.bat                  # Windows launcher
database/                # SQLAlchemy models + DB manager
pdf/                     # PDF import/title/annotation logic
ai/                      # AI clients, provider factory, analysis flow
ui/                      # Tkinter app + graph view (+ legacy PySide files)
web/                     # Optional Flask API + static web UI
utils/                   # Logging, hashing, similarity helpers
```

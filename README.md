# Paper Notes

Lightweight desktop application for academic paper management.

## Features

- Import PDFs from local folders with automatic title extraction
- AI-generated summaries and keyword extraction
- Reading status tracking (Unread / Reading / Read)
- Personal markdown notes per paper
- Related paper recommendations via keyword similarity
- Fast real-time search across titles, keywords, and notes

## Tech Stack

- Python 3.12+
- PySide6 (Qt desktop UI)
- SQLAlchemy (ORM, SQLite)
- PyMuPDF (PDF processing)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

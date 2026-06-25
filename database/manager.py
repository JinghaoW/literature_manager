"""DatabaseManager — CRUD operations for Paper records."""

from pathlib import Path

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base, Paper, PaperStatus


class DatabaseManager:
    """Manages the SQLite database for paper storage.

    Provides CRUD operations: add, update, delete, get, and list papers.
    """

    def __init__(self, db_path: str | Path = "papers.db") -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file. Created if missing.
        """
        db_path = str(db_path)
        self._engine: Engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

    def _new_session(self) -> Session:
        """Create a new database session."""
        return self._session_factory()

    def close(self) -> None:
        """Dispose the engine and release all connections."""
        self._engine.dispose()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def add_paper(
        self,
        title: str,
        file_path: str,
        file_hash: str,
        summary: str | None = None,
        keywords: str | None = None,
        notes: str | None = None,
        status: PaperStatus = PaperStatus.UNREAD,
    ) -> Paper:
        """Insert a new paper into the database.

        Args:
            title: Paper title.
            file_path: Absolute path to the PDF file.
            file_hash: SHA-256 hash of the file.
            summary: AI-generated summary (optional).
            keywords: Comma-separated keywords (optional).
            notes: Personal markdown notes (optional).
            status: Reading status.

        Returns:
            The newly created Paper instance.
        """
        paper = Paper(
            title=title,
            file_path=file_path,
            file_hash=file_hash,
            summary=summary,
            keywords=keywords,
            notes=notes,
            status=status,
        )
        with self._new_session() as session:
            session.add(paper)
            session.commit()
            session.refresh(paper)
        return paper

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_paper(self, paper_id: int) -> Paper | None:
        """Retrieve a single paper by its ID.

        Args:
            paper_id: The paper's primary key.

        Returns:
            The Paper instance, or None if not found.
        """
        with self._new_session() as session:
            return session.get(Paper, paper_id)

    def list_papers(
        self,
        status: PaperStatus | None = None,
        order_by: str = "created_time",
        descending: bool = False,
    ) -> list[Paper]:
        """List all papers, optionally filtered by reading status.

        Args:
            status: Filter by reading status. None returns all papers.
            order_by: Column name to sort by.
            descending: Sort descending when True.

        Returns:
            A list of Paper instances.
        """
        with self._new_session() as session:
            query = session.query(Paper)
            if status is not None:
                query = query.filter(Paper.status == status)
            column = getattr(Paper, order_by, Paper.created_time)
            if descending:
                column = column.desc()
            query = query.order_by(column)
            return query.all()

    def get_paper_by_path(self, file_path: str) -> Paper | None:
        """Find a paper by its file path.

        Args:
            file_path: The stored file path to look up.

        Returns:
            The Paper instance, or None if not found.
        """
        with self._new_session() as session:
            return session.query(Paper).filter(Paper.file_path == file_path).first()

    def get_paper_by_hash(self, file_hash: str) -> Paper | None:
        """Find a paper by its SHA-256 file hash.

        Args:
            file_hash: The hash to look up.

        Returns:
            The Paper instance, or None if not found.
        """
        with self._new_session() as session:
            return session.query(Paper).filter(Paper.file_hash == file_hash).first()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_paper(self, paper_id: int, **kwargs: object) -> Paper | None:
        """Update fields on an existing paper.

        Args:
            paper_id: The paper's primary key.
            **kwargs: Field names and new values to set.

        Returns:
            The updated Paper instance, or None if not found.
        """
        with self._new_session() as session:
            paper = session.get(Paper, paper_id)
            if paper is None:
                return None
            for field, value in kwargs.items():
                if hasattr(paper, field):
                    setattr(paper, field, value)
            session.commit()
            session.refresh(paper)
        return paper

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_paper(self, paper_id: int) -> bool:
        """Delete a paper from the database.

        Args:
            paper_id: The paper's primary key.

        Returns:
            True if the paper was deleted, False if it was not found.
        """
        with self._new_session() as session:
            paper = session.get(Paper, paper_id)
            if paper is None:
                return False
            session.delete(paper)
            session.commit()
        return True

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count_papers(self, status: PaperStatus | None = None) -> int:
        """Return the total number of papers, optionally filtered by status.

        Args:
            status: Filter by reading status. None counts all papers.

        Returns:
            Paper count.
        """
        with self._new_session() as session:
            query = session.query(Paper)
            if status is not None:
                query = query.filter(Paper.status == status)
            return query.count()

"""Paper model — SQLAlchemy ORM mapping for academic papers."""

import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class PaperStatus(str, enum.Enum):
    """Reading status of a paper."""
    UNREAD = "Unread"
    READING = "Reading"
    READ = "Read"


class Paper(Base):
    """An academic paper stored in the local library."""

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Untitled")
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PaperStatus] = mapped_column(
        Enum(PaperStatus), nullable=False, default=PaperStatus.UNREAD
    )
    created_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Paper(id={self.id}, title={self.title!r}, status={self.status.value!r})>"

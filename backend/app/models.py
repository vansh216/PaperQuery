from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STATUS_PROCESSING = "processing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # uuid4 hex; also the Qdrant user_id
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Stored encrypted, never returned by the API.
    gemini_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    gemini_key_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)  # last 4 chars, for display
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    """One uploaded PDF. Always belongs to exactly one user; deleting the user deletes their documents."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # uuid4 hex; also the Qdrant doc_id
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))       # original name, for display and citations
    stored_path: Mapped[str] = mapped_column(String(500))    # where the file lives on disk (set in Step 6)
    pages: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    chunks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(16), default=STATUS_PROCESSING, server_default=STATUS_PROCESSING)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
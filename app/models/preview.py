"""Scroll and Subject models for academic preprints."""

from datetime import datetime
from typing import List
import uuid

from sqlalchemy import ARRAY, JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

from app.database import Base
from app.models.user import User


class GUID(TypeDecorator):
    """Cross-platform UUID type that works with both PostgreSQL and SQLite."""

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


class StringArray(TypeDecorator):
    """Cross-platform string array type."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String))
        else:
            return dialect.type_descriptor(JSON)


class Subject(Base):
    """Academic subject categories for scrolls."""

    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    scrolls: Mapped[List["Preview"]] = relationship("Preview", back_populates="subject")

    def __repr__(self):
        return f"<Subject(name='{self.name}')>"


class Preview(Base):
    """Academic scroll/preprint model."""

    __tablename__ = "previews"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    preview_id: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=True
    )  # Short public ID for published scrolls

    # Content fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[str] = mapped_column(String(1000), nullable=False)  # Comma-separated for now
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[List[str]] = mapped_column(StringArray, nullable=True)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)

    # New fields for HTML papers
    content_type: Mapped[str] = mapped_column(String(50), default="html")  # 'html' only for now
    original_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int] = mapped_column(nullable=True)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    external_resources: Mapped[dict] = mapped_column(
        JSON, nullable=True
    )  # Catalog of external assets
    validation_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # 'pending', 'approved', 'rejected'
    sanitization_log: Mapped[dict] = mapped_column(
        JSON, nullable=True
    )  # Record of changes made during processing

    # Metadata
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, published
    version: Mapped[int] = mapped_column(default=1)  # Version number
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("subjects.id"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="scrolls")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="scrolls")

    def __repr__(self):
        return f"<Preview(title='{self.title[:50]}...', status='{self.status}')>"

    def publish(self):
        """Publish the scroll by generating a public ID."""
        if self.status == "published":
            return

        # Generate a short, unique scroll ID
        import secrets
        import string

        # Generate 8-character alphanumeric ID
        self.preview_id = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(8)
        )
        self.status = "published"
        self.published_at = func.now()

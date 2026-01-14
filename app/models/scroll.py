"""Scroll and Subject models for academic preprints."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy import ARRAY, JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
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
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    scrolls: Mapped[List["Scroll"]] = relationship("Scroll", back_populates="subject")

    def __repr__(self):
        return f"<Subject(name='{self.name}')>"


class Scroll(Base):
    """Academic scroll model with content-addressable storage."""

    __tablename__ = "scrolls"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)

    # Content-addressable storage fields
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True
    )  # Full SHA-256 hash
    url_hash: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True
    )  # Shortened hash for URL (12+ chars)

    # Legacy field for backward compatibility
    preview_id: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=True
    )  # Short public ID for scrolls

    # Content fields - for MVP, only HTML content is stored in database
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[str] = mapped_column(String(1000), nullable=False)  # Comma-separated for now
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[List[str]] = mapped_column(StringArray, nullable=True)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)  # Normalized HTML content

    # New fields for HTML scrolls
    content_type: Mapped[str] = mapped_column(String(50), default="html")  # 'html' only for now
    original_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int] = mapped_column(nullable=True)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    external_resources: Mapped[dict] = mapped_column(
        JSON, nullable=True
    )  # Catalog of external assets
    validation_status: Mapped[str] = mapped_column(
        String(20), default="approved"
    )  # 'approved' (no pending/rejected since all are published directly)
    sanitization_log: Mapped[dict] = mapped_column(
        JSON, nullable=True
    )  # Record of changes made during processing

    # License field
    license: Mapped[str] = mapped_column(String(20), nullable=False)  # 'cc-by-4.0' or 'arr'

    # Metadata
    status: Mapped[str] = mapped_column(String(20), default="published")  # published only
    version: Mapped[int] = mapped_column(default=1)  # Version number
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # DOI fields
    doi: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    doi_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # 'pending', 'minted', 'failed'
    doi_minted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    zenodo_deposit_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Foreign keys
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, ForeignKey("users.id"), nullable=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("subjects.id"), nullable=False)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="scrolls")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="scrolls")

    def __repr__(self):
        return f"<Scroll(title='{self.title[:50]}...', status='{self.status}')>"

    @validates("license")
    def validate_license(self, key, license_value):
        """Validate license field to ensure only allowed values."""
        allowed_licenses = ["cc-by-4.0", "arr"]
        if license_value not in allowed_licenses:
            raise ValueError(f"License must be one of: {allowed_licenses}, got: {license_value}")
        return license_value

    def publish(self):
        """Publish the scroll and set published timestamp."""
        # For content-addressable scrolls, ensure they have the required fields
        if not self.content_hash or not self.url_hash:
            raise ValueError("Cannot publish scroll without content hash")

        # Set published status and timestamp
        self.status = "published"
        if not self.published_at:
            self.published_at = datetime.now(timezone.utc)

    @property
    def permanent_url(self) -> str:
        """Get the permanent content-addressable URL for this scroll."""
        if self.url_hash:
            return f"/scroll/{self.url_hash}"
        else:
            # Fall back to legacy URL for backward compatibility
            return f"/scroll/{self.preview_id}"

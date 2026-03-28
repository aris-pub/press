from datetime import datetime, timezone
import re
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates

from app.database import Base

ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def validate_orcid_id(value: str | None) -> str | None:
    """Validate ORCID iD format: XXXX-XXXX-XXXX-XXXX (last char may be X checksum)."""
    if value is None:
        return None
    if not ORCID_PATTERN.match(value):
        raise ValueError(
            f"Invalid ORCID iD format: '{value}'. "
            "Expected format: 0000-0002-1234-5678"
        )
    return value


# Cross-platform UUID type that works with SQLite
class GUID(TypeDecorator):
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
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
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    orcid_id = Column(String(20), nullable=True, unique=True, index=True)

    # Relationships
    scrolls = relationship("Scroll", back_populates="user")
    sessions = relationship("Session", back_populates="user")
    tokens = relationship("Token", back_populates="user")

    @validates("orcid_id")
    def _validate_orcid_id(self, _key: str, value: str | None) -> str | None:
        return validate_orcid_id(value)

    def __repr__(self):
        return f"<User(email='{self.email}', display_name='{self.display_name}')>"

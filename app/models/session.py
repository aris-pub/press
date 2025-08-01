from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.user import GUID


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(255), primary_key=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,  # Index for efficient cleanup queries
    )

    # Relationship
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<Session(session_id='{self.session_id[:8]}...', user_id='{self.user_id}')>"
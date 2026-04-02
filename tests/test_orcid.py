"""Tests for ORCID iD storage on the User model."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User, validate_orcid_id


class TestValidateOrcidId:
    """Tests for the orcid_id format validation function."""

    def test_valid_orcid(self):
        assert validate_orcid_id("0000-0002-1234-5678") == "0000-0002-1234-5678"

    def test_valid_orcid_with_checksum_x(self):
        assert validate_orcid_id("0000-0002-1234-567X") == "0000-0002-1234-567X"

    def test_none_passes_through(self):
        assert validate_orcid_id(None) is None

    def test_rejects_missing_hyphens(self):
        with pytest.raises(ValueError, match="ORCID"):
            validate_orcid_id("0000000212345678")

    def test_rejects_too_short(self):
        with pytest.raises(ValueError, match="ORCID"):
            validate_orcid_id("0000-0002-1234")

    def test_rejects_letters_in_body(self):
        with pytest.raises(ValueError, match="ORCID"):
            validate_orcid_id("000A-0002-1234-5678")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="ORCID"):
            validate_orcid_id("")

    def test_rejects_lowercase_x(self):
        with pytest.raises(ValueError, match="ORCID"):
            validate_orcid_id("0000-0002-1234-567x")


@pytest.mark.asyncio
class TestUserOrcidColumn:
    """Tests for the orcid_id column on the User model."""

    async def test_user_created_without_orcid(self, test_db):
        """Backward compat: users can be created with no orcid_id."""
        from app.auth.utils import get_password_hash

        user = User(
            email="noorcid@example.com",
            password_hash=get_password_hash("password123"),
            display_name="No ORCID User",
            email_verified=True,
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.orcid_id is None

    async def test_user_created_with_valid_orcid(self, test_db):
        from app.auth.utils import get_password_hash

        user = User(
            email="orcid@example.com",
            password_hash=get_password_hash("password123"),
            display_name="ORCID User",
            email_verified=True,
            orcid_id="0000-0002-1234-5678",
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.orcid_id == "0000-0002-1234-5678"

    async def test_orcid_with_checksum_x(self, test_db):
        from app.auth.utils import get_password_hash

        user = User(
            email="orcidx@example.com",
            password_hash=get_password_hash("password123"),
            display_name="ORCID X User",
            email_verified=True,
            orcid_id="0000-0002-1234-567X",
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        assert user.orcid_id == "0000-0002-1234-567X"

    async def test_orcid_uniqueness_constraint(self, test_db):
        """Two users cannot share the same ORCID iD."""
        from app.auth.utils import get_password_hash

        user1 = User(
            email="user1@example.com",
            password_hash=get_password_hash("password123"),
            display_name="User 1",
            email_verified=True,
            orcid_id="0000-0002-1234-5678",
        )
        test_db.add(user1)
        await test_db.commit()

        user2 = User(
            email="user2@example.com",
            password_hash=get_password_hash("password123"),
            display_name="User 2",
            email_verified=True,
            orcid_id="0000-0002-1234-5678",
        )
        test_db.add(user2)

        with pytest.raises(IntegrityError):
            await test_db.commit()

    async def test_multiple_users_with_null_orcid(self, test_db):
        """Multiple users can have NULL orcid_id (no false unique violation)."""
        from app.auth.utils import get_password_hash

        for i in range(3):
            user = User(
                email=f"null_orcid_{i}@example.com",
                password_hash=get_password_hash("password123"),
                display_name=f"Null ORCID {i}",
                email_verified=True,
            )
            test_db.add(user)

        await test_db.commit()

        result = await test_db.execute(select(User).where(User.orcid_id.is_(None)))
        users = result.scalars().all()
        assert len(users) == 3

    async def test_invalid_orcid_rejected_by_validator(self, test_db):
        """The @validates decorator rejects bad formats before hitting the DB."""
        from app.auth.utils import get_password_hash

        with pytest.raises(ValueError, match="ORCID"):
            User(
                email="bad@example.com",
                password_hash=get_password_hash("password123"),
                display_name="Bad ORCID",
                email_verified=True,
                orcid_id="not-an-orcid",
            )

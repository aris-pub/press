import asyncio

from sqlalchemy import text

from app.auth.utils import get_password_hash
from app.database import AsyncSessionLocal, create_tables
from app.models.user import User
from app.models.preview import Subject


async def seed_users():
    """Create mock users with UTC timestamps."""
    async with AsyncSessionLocal() as session:
        # Check if users already exist
        existing_users = await session.execute(text("SELECT COUNT(*) FROM users"))
        if existing_users.scalar() > 0:
            print("Users already exist, skipping seed.")
            return

        # Sample users matching the paper authors
        users_data = [
            {
                "email": "john.smith@university.edu",
                "display_name": "John Smith",
                "password": "password123",
            },
            {
                "email": "li.chen@institute.org",
                "display_name": "Li Chen",
                "password": "password123",
            },
            {
                "email": "maria.garcia@lab.com",
                "display_name": "Maria Garcia",
                "password": "password123",
            },
            {
                "email": "robert.watson@research.edu",
                "display_name": "Robert Watson",
                "password": "password123",
            },
            {
                "email": "sarah.kim@physics.edu",
                "display_name": "Sarah Kim",
                "password": "password123",
            },
            {
                "email": "anita.patel@biolab.org",
                "display_name": "Anita Patel",
                "password": "password123",
            },
            {
                "email": "michael.johnson@med.edu",
                "display_name": "Michael Johnson",
                "password": "password123",
            },
            {
                "email": "takeshi.nakamura@research.jp",
                "display_name": "Takeshi Nakamura",
                "password": "password123",
            },
            {
                "email": "pavel.kowalski@math.edu",
                "display_name": "Pavel Kowalski",
                "password": "password123",
            },
        ]

        # Create users with UTC timestamps
        for user_data in users_data:
            db_user = User(
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                display_name=user_data["display_name"],
                email_verified=True,  # Pre-verify for testing
            )
            session.add(db_user)

        await session.commit()
        print(f"Created {len(users_data)} seed users with UTC timestamps")


async def seed_subjects():
    """Create academic subject categories."""
    async with AsyncSessionLocal() as session:
        # Check if subjects already exist
        existing_subjects = await session.execute("SELECT COUNT(*) FROM subjects")
        if existing_subjects.scalar() > 0:
            print("Subjects already exist, skipping seed.")
            return

        subjects_data = [
            {
                "name": "Computer Science",
                "description": "Computing, algorithms, and software engineering",
            },
            {"name": "Physics", "description": "Theoretical and experimental physics"},
            {"name": "Mathematics", "description": "Pure and applied mathematics"},
            {"name": "Biology", "description": "Life sciences and biological research"},
            {"name": "Chemistry", "description": "Chemical sciences and molecular research"},
            {"name": "Economics", "description": "Economic theory and quantitative analysis"},
            {"name": "Medicine", "description": "Medical research and healthcare"},
            {"name": "Engineering", "description": "Applied engineering and technology"},
            {"name": "Psychology", "description": "Behavioral sciences and cognitive research"},
            {
                "name": "Environmental Science",
                "description": "Climate, ecology, and sustainability research",
            },
            {"name": "Neuroscience", "description": "Brain research and neural systems"},
        ]

        for subject_data in subjects_data:
            db_subject = Subject(
                name=subject_data["name"], description=subject_data["description"]
            )
            session.add(db_subject)

        await session.commit()
        print(f"Created {len(subjects_data)} academic subjects")


async def main():
    """Run the seed script."""
    print("Creating database tables...")
    await create_tables()

    print("Seeding subjects...")
    await seed_subjects()

    print("Seeding users...")
    await seed_users()

    print("Seed completed!")


if __name__ == "__main__":
    asyncio.run(main())

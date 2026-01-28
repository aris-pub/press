import asyncio

from sqlalchemy import text

from app.auth.utils import get_password_hash
from app.database import AsyncSessionLocal, create_tables
from app.models.scroll import Scroll, Subject
from app.models.user import User


async def seed_users(session=None):
    """Create mock users with UTC timestamps."""
    should_close = session is None
    if session is None:
        session = AsyncSessionLocal()

    try:
        # Sample users matching the paper authors
        users_data = [
            {
                "email": "testuser@example.com",
                "display_name": "Test User",
                "password": "testpass",
            },
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
    finally:
        if should_close:
            await session.close()


async def seed_subjects(session=None):
    """Create academic subject categories."""
    should_close = session is None
    if session is None:
        session = AsyncSessionLocal()

    try:
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
    finally:
        if should_close:
            await session.close()


async def delete_existing_data():
    """Delete existing seed data in correct order (respecting foreign keys)."""
    async with AsyncSessionLocal() as session:
        print("Deleting existing seed data...")
        # Delete in order: scrolls first (depends on users & subjects)
        await session.execute(text("DELETE FROM scrolls"))
        # Then tokens and sessions (depend on users)
        await session.execute(text("DELETE FROM tokens"))
        await session.execute(text("DELETE FROM sessions"))
        # Then users and subjects
        await session.execute(
            text(
                "DELETE FROM users WHERE email LIKE '%university.edu' OR email LIKE '%institute.org' OR email LIKE '%lab.com' OR email LIKE '%research.edu' OR email LIKE '%physics.edu' OR email LIKE '%biolab.org' OR email LIKE '%med.edu' OR email LIKE '%research.jp' OR email LIKE '%math.edu' OR email = 'testuser@example.com'"
            )
        )
        await session.execute(text("DELETE FROM subjects"))
        await session.commit()
        print("Existing seed data deleted!")


async def seed_scrolls(session=None):
    """Create seed scrolls from real HTML papers."""
    import json
    from pathlib import Path

    should_close = session is None
    if session is None:
        session = AsyncSessionLocal()

    try:
        # Get users and subjects for foreign keys
        users_result = await session.execute(text("SELECT id, display_name FROM users"))
        users = {row[1]: row[0] for row in users_result}

        subjects_result = await session.execute(text("SELECT id, name FROM subjects"))
        subjects = {row[1]: row[0] for row in subjects_result}

        # Load scrolls metadata from examples-press submodule
        examples_dir = Path(__file__).parent.parent / "examples-press"
        metadata_file = examples_dir / "scrolls.json"

        if not metadata_file.exists():
            print(
                f"Error: {metadata_file} not found. Make sure examples-press submodule is initialized."
            )
            print("Run: git submodule update --init")
            return

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        scrolls_data = metadata["scrolls"]

        # Load HTML content from files and create scrolls
        for scroll_data in scrolls_data:
            html_file = examples_dir / scroll_data["file"]

            if not html_file.exists():
                print(f"Warning: {scroll_data['file']} not found, skipping...")
                continue

            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()

            # Generate content-addressable storage fields
            from app.storage.content_processing import generate_permanent_url

            url_hash, content_hash, tar_data = await generate_permanent_url(html_content)

            db_scroll = Scroll(
                title=scroll_data["title"],
                authors=scroll_data["authors"],
                abstract=scroll_data["abstract"],
                keywords=scroll_data["keywords"],
                html_content=html_content,
                content_hash=content_hash,
                url_hash=url_hash,
                license=scroll_data["license"],
                user_id=users[scroll_data["user"]],
                subject_id=subjects[scroll_data["subject"]],
                status="published",
                version=1,
            )
            session.add(db_scroll)

        await session.commit()
        print(f"Created {len(scrolls_data)} seed papers from real HTML files")
    finally:
        if should_close:
            await session.close()


async def main():
    """Run the seed script."""
    print("Creating database tables...")
    await create_tables()

    print("Deleting existing data...")
    await delete_existing_data()

    print("Seeding subjects...")
    await seed_subjects()

    print("Seeding users...")
    await seed_users()

    print("Seeding scrolls...")
    await seed_scrolls()

    print("Seed completed!")


if __name__ == "__main__":
    asyncio.run(main())

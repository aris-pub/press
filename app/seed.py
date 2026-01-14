import asyncio

from sqlalchemy import text

from app.auth.utils import get_password_hash
from app.database import AsyncSessionLocal, create_tables
from app.models.scroll import Scroll, Subject
from app.models.user import User


async def seed_users():
    """Create mock users with UTC timestamps."""
    async with AsyncSessionLocal() as session:
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
                "DELETE FROM users WHERE email LIKE '%university.edu' OR email LIKE '%institute.org' OR email LIKE '%lab.com' OR email LIKE '%research.edu' OR email LIKE '%physics.edu' OR email LIKE '%biolab.org' OR email LIKE '%med.edu' OR email LIKE '%research.jp' OR email LIKE '%math.edu'"
            )
        )
        await session.execute(text("DELETE FROM subjects"))
        await session.commit()
        print("Existing seed data deleted!")


async def seed_scrolls():
    """Create seed scrolls from real HTML papers."""
    from pathlib import Path

    async with AsyncSessionLocal() as session:
        # Get users and subjects for foreign keys
        users_result = await session.execute(text("SELECT id, display_name FROM users"))
        users = {row[1]: row[0] for row in users_result}

        subjects_result = await session.execute(text("SELECT id, name FROM subjects"))
        subjects = {row[1]: row[0] for row in subjects_result}

        # Define seed papers with their metadata
        seed_papers_dir = Path(__file__).parent.parent / "seed_papers"

        scrolls_data = [
            {
                "file": "spectral_theorem.html",
                "title": "The Spectral Theorem for Symmetric Matrices",
                "authors": "Dr. Victor Frankenstein, Captain Nemo",
                "abstract": "The spectral theorem establishes that symmetric matrices can be diagonalized by orthogonal transformations. This fundamental result connects linear algebra with geometric intuition and enables applications from optimization to quantum mechanics. We present the theorem with proof and demonstrate its power through concrete examples.",
                "keywords": ["mathematics", "linear algebra", "spectral theorem", "Typst"],
                "user": "Pavel Kowalski",
                "subject": "Mathematics",
                "license": "cc-by-4.0",
            },
            {
                "file": "iris_analysis.html",
                "title": "Interactive Analysis of the Iris Dataset",
                "authors": "Sherlock Holmes, Alice Liddell",
                "abstract": "The Iris dataset is a classic multivariate dataset used for classification and visualization. This paper provides an interactive exploratory analysis using Python and Plotly, demonstrating species clustering through petal and sepal measurements. Interactive visualizations enable readers to explore the data patterns that make this dataset ideal for demonstrating machine learning classification algorithms.",
                "keywords": [
                    "data science",
                    "machine learning",
                    "Quarto",
                    "interactive plots",
                    "classification",
                ],
                "user": "Anita Patel",
                "subject": "Computer Science",
                "license": "cc-by-4.0",
            },
            {
                "file": "damped_oscillators.html",
                "title": "Damped Harmonic Oscillators: Three Characteristic Regimes",
                "authors": "Dr. Henry Jekyll, Elizabeth Bennet",
                "abstract": "The damped harmonic oscillator extends the simple harmonic oscillator by incorporating energy dissipation. This paper examines the three characteristic regimes—underdamped, critically damped, and overdamped—and demonstrates how the damping coefficient fundamentally determines system behavior. An interactive simulation enables exploration of parameter space, building intuition for this fundamental physical system.",
                "keywords": ["physics", "oscillators", "damping", "interactive simulation", "RSM"],
                "user": "Sarah Kim",
                "subject": "Physics",
                "license": "cc-by-4.0",
            },
            {
                "file": "graph_traversal.html",
                "title": "Graph Traversal Algorithms: BFS and DFS",
                "authors": "Dorothy Gale, Huckleberry Finn",
                "abstract": "Graph traversal algorithms systematically visit vertices in a graph. This paper examines the two fundamental approaches: Breadth-First Search (BFS) explores level-by-level, while Depth-First Search (DFS) explores as deep as possible before backtracking. Understanding their distinct characteristics is essential for selecting the appropriate algorithm for path-finding, connectivity analysis, and graph-based problem solving.",
                "keywords": ["algorithms", "graph theory", "BFS", "DFS", "Jupyter"],
                "user": "John Smith",
                "subject": "Computer Science",
                "license": "cc-by-4.0",
            },
        ]

        # Load HTML content from files and create scrolls
        for scroll_data in scrolls_data:
            html_file = seed_papers_dir / scroll_data["file"]

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

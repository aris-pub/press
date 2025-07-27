import asyncio

from sqlalchemy import text

from app.auth.utils import get_password_hash
from app.database import AsyncSessionLocal, create_tables
from app.models.preview import Preview, Subject
from app.models.user import User


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
        existing_subjects = await session.execute(text("SELECT COUNT(*) FROM subjects"))
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


async def seed_previews():
    """Create mock previews/papers."""
    async with AsyncSessionLocal() as session:
        # Check if previews already exist
        existing_previews = await session.execute(text("SELECT COUNT(*) FROM previews"))
        if existing_previews.scalar() > 0:
            print("Previews already exist, skipping seed.")
            return

        # Get users and subjects for foreign keys
        users_result = await session.execute(text("SELECT id, display_name FROM users"))
        users = {row[1]: row[0] for row in users_result}

        subjects_result = await session.execute(text("SELECT id, name FROM subjects"))
        subjects = {row[1]: row[0] for row in subjects_result}

        previews_data = [
            {
                "title": "Efficient Algorithms for Large-Scale Graph Neural Networks",
                "authors": "John Smith, Li Chen, Maria Garcia",
                "abstract": "We present a novel approach to scaling graph neural networks for datasets with millions of nodes. Our method reduces computational complexity from O(n²) to O(n log n) while maintaining accuracy comparable to existing approaches. Experimental results on five benchmark datasets demonstrate significant improvements in both training time and memory usage.",
                "keywords": [
                    "machine learning",
                    "graph neural networks",
                    "algorithms",
                    "scalability",
                ],
                "html_content": "<h1>Efficient Algorithms for Large-Scale Graph Neural Networks</h1><p>This paper presents our findings on scaling GNNs.</p><h2>Introduction</h2><p>Graph neural networks are important.</p><h2>Methods</h2><p>We used a novel approach.</p><h2>Results</h2><p>Our method is faster.</p>",
                "user_id": users["John Smith"],
                "subject_id": subjects["Computer Science"],
                "status": "published",
                "preview_id": "gnn2024a",
                "version": 1,
            },
            {
                "title": "Quantum Entanglement in Room-Temperature Superconductors",
                "authors": "Robert Watson, Sarah Kim",
                "abstract": "Recent discoveries in room-temperature superconductivity have opened new avenues for quantum computing applications. This paper investigates the role of quantum entanglement in maintaining superconducting states at ambient conditions. Through theoretical modeling and experimental validation, we demonstrate novel quantum coherence mechanisms.",
                "keywords": [
                    "quantum physics",
                    "superconductivity",
                    "condensed matter",
                    "quantum computing",
                ],
                "html_content": "<h1>Quantum Entanglement in Room-Temperature Superconductors</h1><p>We study quantum effects in superconductors.</p><h2>Background</h2><p>Room temperature superconductors are revolutionary.</p><h2>Experimental Setup</h2><p>We measured quantum entanglement.</p><h2>Conclusions</h2><p>Entanglement is key to superconductivity.</p>",
                "user_id": users["Robert Watson"],
                "subject_id": subjects["Physics"],
                "status": "published",
                "preview_id": "quantum24",
                "version": 1,
            },
            {
                "title": "CRISPR-Cas9 Applications in Treating Hereditary Diseases",
                "authors": "Anita Patel, Michael Johnson, Takeshi Nakamura",
                "abstract": "Gene editing technologies have shown remarkable promise in addressing genetic disorders. This comprehensive review examines recent clinical trials using CRISPR-Cas9 systems to treat sickle cell disease, beta-thalassemia, and Leber congenital amaurosis. We analyze success rates, safety profiles, and future therapeutic potential.",
                "keywords": ["gene editing", "CRISPR", "hereditary diseases", "clinical trials"],
                "html_content": "<h1>CRISPR-Cas9 Applications in Treating Hereditary Diseases</h1><p>Gene editing is transforming medicine.</p><h2>Overview</h2><p>CRISPR can fix genetic diseases.</p><h2>Clinical Trials</h2><p>We reviewed recent studies.</p><h2>Future Directions</h2><p>Gene therapy will expand.</p>",
                "user_id": users["Anita Patel"],
                "subject_id": subjects["Biology"],
                "status": "published",
                "preview_id": "crispr23",
                "version": 2,
            },
            {
                "title": "A New Proof of the Riemann Hypothesis",
                "authors": "Pavel Kowalski",
                "abstract": "This paper presents a novel approach to proving the Riemann Hypothesis using advanced techniques from algebraic geometry and number theory. The proof relies on establishing a deep connection between the zeros of the Riemann zeta function and geometric properties of certain algebraic varieties over finite fields.",
                "keywords": [
                    "number theory",
                    "riemann hypothesis",
                    "algebraic geometry",
                    "zeta functions",
                ],
                "html_content": "<h1>A New Proof of the Riemann Hypothesis</h1><p>We prove the famous Riemann Hypothesis.</p><h2>Introduction</h2><p>The Riemann Hypothesis is unsolved.</p><h2>Our Approach</h2><p>We use algebraic geometry.</p><h2>Proof</h2><p>The zeros have special properties.</p><h2>Conclusion</h2><p>The hypothesis is true.</p>",
                "user_id": users["Pavel Kowalski"],
                "subject_id": subjects["Mathematics"],
                "status": "published",
                "preview_id": "riemann24",
                "version": 1,
            },
        ]

        for preview_data in previews_data:
            db_preview = Preview(
                title=preview_data["title"],
                authors=preview_data["authors"],
                abstract=preview_data["abstract"],
                keywords=preview_data["keywords"],
                html_content=preview_data["html_content"],
                user_id=preview_data["user_id"],
                subject_id=preview_data["subject_id"],
                status=preview_data["status"],
                preview_id=preview_data["preview_id"],
                version=preview_data["version"],
            )
            session.add(db_preview)

        await session.commit()
        print(f"Created {len(previews_data)} preview papers")


async def main():
    """Run the seed script."""
    print("Creating database tables...")
    await create_tables()

    print("Seeding subjects...")
    await seed_subjects()

    print("Seeding users...")
    await seed_users()

    print("Seeding previews...")
    await seed_previews()

    print("Seed completed!")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from sqlalchemy import text

from app.auth.utils import get_password_hash
from app.database import AsyncSessionLocal, create_tables
from app.models.scroll import Scroll, Subject
from app.models.user import User


async def seed_users():
    """Create mock users with UTC timestamps."""
    async with AsyncSessionLocal() as session:
        # Check if our seed users already exist
        existing_seed_users = await session.execute(
            text(
                "SELECT COUNT(*) FROM users WHERE email LIKE '%university.edu' OR email LIKE '%institute.org' OR email LIKE '%lab.com'"
            )
        )
        if existing_seed_users.scalar() > 0:
            print("Seed users already exist, skipping seed.")
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


async def seed_scrolls():
    """Create seed scrolls from real HTML papers."""
    import os
    from pathlib import Path

    async with AsyncSessionLocal() as session:
        # Check if scrolls already exist
        existing_scrolls = await session.execute(text("SELECT COUNT(*) FROM scrolls"))
        if existing_scrolls.scalar() > 0:
            print("Scrolls already exist, skipping seed.")
            return

        # Get users and subjects for foreign keys
        users_result = await session.execute(text("SELECT id, display_name FROM users"))
        users = {row[1]: row[0] for row in users_result}

        subjects_result = await session.execute(text("SELECT id, name FROM subjects"))
        subjects = {row[1]: row[0] for row in subjects_result}

        # Define seed papers with their metadata
        seed_papers_dir = Path(__file__).parent.parent / "seed_papers"

        scrolls_data = [
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
                "file": "iris_analysis.html",
                "title": "Interactive Analysis of the Iris Dataset",
                "authors": "Sherlock Holmes, Alice Liddell",
                "abstract": "The Iris dataset is a classic multivariate dataset used for classification and visualization. This paper provides an interactive exploratory analysis using Python and Plotly, demonstrating species clustering through petal and sepal measurements. Interactive visualizations enable readers to explore the data patterns that make this dataset ideal for demonstrating machine learning classification algorithms.",
                "keywords": ["data science", "machine learning", "Quarto", "interactive plots", "classification"],
                "user": "Anita Patel",
                "subject": "Computer Science",
                "license": "cc-by-4.0",
            },
            {
                "file": "graph_traversal_myst.html",
                "title": "Graph Traversal Algorithms: BFS and DFS",
                "authors": "Dorothy Gale, Huckleberry Finn",
                "abstract": "Graph traversal algorithms systematically visit vertices in a graph. This paper examines the two fundamental approaches: Breadth-First Search (BFS) explores level-by-level, while Depth-First Search (DFS) explores as deep as possible before backtracking. Understanding their distinct characteristics is essential for selecting the appropriate algorithm for path-finding, connectivity analysis, and graph-based problem solving.",
                "keywords": ["algorithms", "graph theory", "BFS", "DFS", "MyST", "computer science"],
                "user": "John Smith",
                "subject": "Computer Science",
                "license": "cc-by-4.0",
            },
            {
                "file": "spectral_theorem.html",
                "title": "The Spectral Theorem for Symmetric Matrices",
                "authors": "Dr. Victor Frankenstein, Captain Nemo",
                "abstract": "The spectral theorem establishes that symmetric matrices can be diagonalized by orthogonal transformations. This fundamental result connects linear algebra with geometric intuition and enables applications from optimization to quantum mechanics. We present the theorem with proof and demonstrate its power through concrete examples.",
                "keywords": ["mathematics", "linear algebra", "spectral theorem", "Typst", "eigenvalues"],
                "user": "Pavel Kowalski",
                "subject": "Mathematics",
                "license": "cc-by-4.0",
            },
        ]

        # Load HTML content from files and create scrolls
        for scroll_data in scrolls_data:
            html_file = seed_papers_dir / scroll_data["file"]

            if not html_file.exists():
                print(f"Warning: {scroll_data['file']} not found, skipping...")
                continue

            with open(html_file, 'r', encoding='utf-8') as f:
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


async def seed_scrolls_old():
    """DEPRECATED: Old seed scrolls with minimal HTML - keeping for reference."""
    async with AsyncSessionLocal() as session:
        scrolls_data = [
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
                "version": 1,
                "license": "cc-by-4.0",
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
                "version": 1,
                "license": "arr",
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
                "version": 2,
                "license": "cc-by-4.0",
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
                "version": 1,
                "license": "arr",
            },
            {
                "title": "Interactive Test Document - Nonce System Demo",
                "authors": "Test User",
                "abstract": "A simple test document with JavaScript to validate the nonce system implementation. This document contains interactive elements that demonstrate script execution through CSP nonces.",
                "keywords": ["test", "nonce", "javascript", "interactive", "csp"],
                "html_content": """<!DOCTYPE html>
<html>
<head>
    <title>Nonce Test Document</title>
    <style>
        .test-container {
            max-width: 600px;
            margin: 40px auto;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .test-button { 
            padding: 12px 24px; 
            background: #007bff; 
            color: white; 
            border: none; 
            border-radius: 6px; 
            cursor: pointer;
            font-size: 16px;
            margin: 10px 5px;
        }
        .test-button:hover {
            background: #0056b3;
        }
        .result { 
            margin-top: 20px; 
            padding: 15px; 
            background: #f8f9fa; 
            border: 1px solid #dee2e6;
            border-radius: 6px;
            display: none;
        }
        .success { background: #d4edda; border-color: #c3e6cb; color: #155724; }
        .info { background: #d1ecf1; border-color: #bee5eb; color: #0c5460; }
    </style>
</head>
<body>
    <div class="test-container">
        <h1>Interactive Test Document</h1>
        <p>This document tests JavaScript execution through the nonce system. It demonstrates that user-uploaded content with scripts can work securely.</p>
        
        <h2>Interactive Tests</h2>
        <p>Click the buttons below to test different JavaScript functionality:</p>
        
        <button class="test-button" id="basicTest">Basic Click Test</button>
        <button class="test-button" id="timeTest">Show Current Time</button>
        <button class="test-button" id="domTest">DOM Manipulation Test</button>
        
        <div id="result" class="result"></div>
        
        <h2>Technical Details</h2>
        <p>This document contains inline JavaScript that should execute only if the nonce system is working correctly. Without proper CSP nonces, the scripts would be blocked.</p>
    </div>
    
    <script>
        // Test 1: Basic event listener
        document.getElementById('basicTest').addEventListener('click', function() {
            const result = document.getElementById('result');
            result.className = 'result success';
            result.style.display = 'block';
            result.innerHTML = '<strong>✓ Success!</strong> Basic JavaScript event handling works correctly. Timestamp: ' + new Date().toLocaleTimeString();
        });
        
        // Test 2: Time display
        document.getElementById('timeTest').addEventListener('click', function() {
            const result = document.getElementById('result');
            result.className = 'result info';
            result.style.display = 'block';
            const now = new Date();
            result.innerHTML = '<strong>⏰ Current Time:</strong> ' + now.toLocaleString() + '<br><small>Timezone: ' + Intl.DateTimeFormat().resolvedOptions().timeZone + '</small>';
        });
        
        // Test 3: DOM manipulation
        document.getElementById('domTest').addEventListener('click', function() {
            const result = document.getElementById('result');
            result.className = 'result info';
            result.style.display = 'block';
            
            // Create dynamic content
            const testDiv = document.createElement('div');
            testDiv.innerHTML = '<strong>🔧 DOM Test:</strong> Created new element dynamically';
            testDiv.style.marginTop = '10px';
            testDiv.style.padding = '10px';
            testDiv.style.background = '#fff3cd';
            testDiv.style.border = '1px solid #ffeaa7';
            testDiv.style.borderRadius = '4px';
            
            result.innerHTML = '';
            result.appendChild(testDiv);
        });
        
        // Auto-initialize - log successful load
        console.log('✓ Nonce test document JavaScript loaded successfully at', new Date().toISOString());
        
        // Additional test: Verify document is interactive
        document.addEventListener('DOMContentLoaded', function() {
            console.log('✓ DOM content loaded, document is fully interactive');
        });
    </script>
</body>
</html>""",
                "user_id": users["John Smith"],
                "subject_id": subjects["Computer Science"],
                "status": "published",
                "version": 1,
                "license": "cc-by-4.0",
            },
        ]

        for scroll_data in scrolls_data:
            # Generate content-addressable storage fields using proper function
            from app.storage.content_processing import generate_permanent_url

            url_hash, content_hash, tar_data = await generate_permanent_url(
                scroll_data["html_content"]
            )

            db_scroll = Scroll(
                title=scroll_data["title"],
                authors=scroll_data["authors"],
                abstract=scroll_data["abstract"],
                keywords=scroll_data["keywords"],
                html_content=scroll_data["html_content"],
                content_hash=content_hash,
                url_hash=url_hash,
                license=scroll_data.get("license", "cc-by-4.0"),  # Default to CC BY 4.0
                user_id=scroll_data["user_id"],
                subject_id=scroll_data["subject_id"],
                status=scroll_data["status"],
                version=scroll_data["version"],
            )
            session.add(db_scroll)

        await session.commit()
        print(f"Created {len(scrolls_data)} scroll papers")


async def main():
    """Run the seed script."""
    print("Creating database tables...")
    await create_tables()

    print("Seeding subjects...")
    await seed_subjects()

    print("Seeding users...")
    await seed_users()

    print("Seeding scrolls...")
    await seed_scrolls()

    print("Seed completed!")


if __name__ == "__main__":
    asyncio.run(main())

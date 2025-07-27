"""Tests for export data functionality."""

from httpx import AsyncClient

from app.models.preview import Preview, Subject


async def test_dashboard_has_export_button(authenticated_client: AsyncClient, test_db, test_user):
    """Test that dashboard page contains export data button when user has papers."""
    # Create subject and published preview
    subject = Subject(name="Test Subject")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Preview",
        authors="Test Author",
        abstract="Test abstract",
        html_content="<h1>Test Content</h1>",
        status="draft",
        user_id=test_user.id,
        subject_id=subject.id,
    )
    test_db.add(preview)
    await test_db.commit()
    await test_db.refresh(preview)

    # Publish preview
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert 'id="export-data-btn"' in response.text
    assert "Export Data" in response.text


async def test_dashboard_has_export_modal(authenticated_client: AsyncClient):
    """Test that dashboard page contains export modal elements."""
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert 'id="export-modal"' in response.text
    assert "Export Your Data" in response.text
    assert 'name="format"' in response.text
    assert 'name="include_content"' in response.text


async def test_export_modal_format_options(authenticated_client: AsyncClient):
    """Test that export modal contains all format options."""
    response = await authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert 'value="csv"' in response.text
    assert 'value="json"' in response.text
    assert 'value="bibtex"' in response.text
    assert "Include HTML content" in response.text


async def test_export_data_requires_authentication(client: AsyncClient):
    """Test that export endpoint requires authentication."""
    export_data = {"format": "csv", "include_content": "false"}
    response = await client.post("/export-data", data=export_data, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_export_csv_metadata_only(authenticated_client: AsyncClient, test_db, test_user):
    """Test exporting CSV with metadata only."""
    # Create subject and published preview
    subject = Subject(name="Test Subject")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Preview",
        authors="Test Author",
        abstract="Test abstract",
        keywords=["test", "preview"],
        html_content="<h1>Test Content</h1>",
        status="draft",
        user_id=test_user.id,
        subject_id=subject.id,
    )
    test_db.add(preview)
    await test_db.commit()
    await test_db.refresh(preview)

    # Publish preview
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    # Export CSV
    export_data = {"format": "csv", "include_content": "false"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert "Test Preview" in response.text
    assert "Test Author" in response.text
    assert "<h1>Test Content</h1>" not in response.text  # HTML content excluded


async def test_export_json_metadata_only(authenticated_client: AsyncClient, test_db, test_user):
    """Test exporting JSON with metadata only."""
    # Create subject and published preview
    subject = Subject(name="Test Subject")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Preview",
        authors="Test Author",
        abstract="Test abstract",
        keywords=["test", "preview"],
        html_content="<h1>Test Content</h1>",
        status="draft",
        user_id=test_user.id,
        subject_id=subject.id,
    )
    test_db.add(preview)
    await test_db.commit()
    await test_db.refresh(preview)

    # Publish preview
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    # Export JSON
    export_data = {"format": "json", "include_content": "false"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Preview"
    assert data[0]["authors"] == "Test Author"
    assert "html_content" not in data[0]  # HTML content excluded


async def test_export_json_with_content(authenticated_client: AsyncClient, test_db, test_user):
    """Test exporting JSON with HTML content included."""
    # Create subject and published preview
    subject = Subject(name="Test Subject")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Test Preview",
        authors="Test Author",
        abstract="Test abstract",
        keywords=["test", "preview"],
        html_content="<h1>Test Content</h1>",
        status="draft",
        user_id=test_user.id,
        subject_id=subject.id,
    )
    test_db.add(preview)
    await test_db.commit()
    await test_db.refresh(preview)

    # Publish preview
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    # Export JSON with content
    export_data = {"format": "json", "include_content": "true"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Preview"
    assert data[0]["html_content"] == "<h1>Test Content</h1>"  # HTML content included


async def test_export_csv_with_content_not_allowed(authenticated_client: AsyncClient):
    """Test that CSV export with content returns error."""
    export_data = {"format": "csv", "include_content": "true"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 400
    assert "CSV format does not support HTML content" in response.text


async def test_export_bibtex_with_content_not_allowed(authenticated_client: AsyncClient):
    """Test that BibTeX export with content returns error."""
    export_data = {"format": "bibtex", "include_content": "true"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 400
    assert "BIBTEX format does not support HTML content" in response.text


async def test_export_bibtex_metadata_only(authenticated_client: AsyncClient, test_db, test_user):
    """Test exporting BibTeX with metadata only."""
    # Create subject and published preview
    subject = Subject(name="Computer Science")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    preview = Preview(
        title="Machine Learning Research",
        authors="John Doe, Jane Smith",
        abstract="This is a test abstract about machine learning.",
        keywords=["machine learning", "AI"],
        html_content="<h1>Test Content</h1>",
        status="draft",
        user_id=test_user.id,
        subject_id=subject.id,
    )
    test_db.add(preview)
    await test_db.commit()
    await test_db.refresh(preview)

    # Publish preview
    preview.publish()
    await test_db.commit()
    await test_db.refresh(preview)

    # Export BibTeX
    export_data = {"format": "bibtex", "include_content": "false"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert "@misc{" in response.text
    assert "Machine Learning Research" in response.text
    assert "John Doe and Jane Smith" in response.text


async def test_export_empty_dataset(authenticated_client: AsyncClient):
    """Test exporting when user has no published papers."""
    export_data = {"format": "csv", "include_content": "false"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 200
    # Should return empty CSV with headers only
    assert "title,authors" in response.text


async def test_export_invalid_format(authenticated_client: AsyncClient):
    """Test export with invalid format parameter."""
    export_data = {"format": "xml", "include_content": "false"}
    response = await authenticated_client.post("/export-data", data=export_data)
    assert response.status_code == 400
    assert "Invalid format" in response.text

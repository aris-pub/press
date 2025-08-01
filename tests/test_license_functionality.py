"""Tests for license functionality."""

from httpx import AsyncClient
import pytest

from app.models.scroll import Scroll, Subject


class TestLicenseValidation:
    """Test license field validation."""

    async def test_scroll_model_validates_license_values(self, test_db, test_user):
        """Test that Scroll model only accepts valid license values."""
        # Create subject
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        # Valid license should work
        valid_scroll = Scroll(
            title="Test Scroll",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test</h1>",
            license="cc-by-4.0",
            user_id=test_user.id,
            subject_id=subject.id,
        )
        test_db.add(valid_scroll)
        await test_db.commit()

        # Invalid license should raise ValueError
        with pytest.raises(ValueError, match="License must be one of"):
            invalid_scroll = Scroll(
                title="Invalid Scroll",
                authors="Test Author",
                abstract="Test abstract",
                html_content="<h1>Test</h1>",
                license="invalid-license",
                user_id=test_user.id,
                subject_id=subject.id,
            )
            test_db.add(invalid_scroll)
            await test_db.flush()  # Trigger validation

    async def test_upload_form_requires_license(self, authenticated_client: AsyncClient, test_db):
        """Test that upload form requires license field."""
        # Create subject
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        # Set content-type header for form submission
        upload_data = {
            "title": "Test Scroll",
            "authors": "Test Author",
            "subject_id": str(subject.id),
            "abstract": "Test abstract",
            "html_content": "<h1>Test Content</h1>",
            "confirm_rights": "true",
            # Missing license field
        }

        response = await authenticated_client.post(
            "/upload-form",
            data=upload_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 422
        # Check for HTML error response from the form
        assert "License must be selected" in response.text or "Field required" in response.text

    async def test_upload_form_accepts_valid_licenses(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test that upload form accepts valid license values."""
        # Create subject
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        for license_value in ["cc-by-4.0", "arr"]:
            upload_data = {
                "title": f"Test Scroll {license_value}",
                "authors": "Test Author",
                "subject_id": str(subject.id),
                "abstract": "Test abstract",
                "html_content": "<h1>Test Content</h1>",
                "license": license_value,
                "confirm_rights": "true",
            }

            response = await authenticated_client.post("/upload-form", data=upload_data)
            assert response.status_code == 200
            assert "Success!" in response.text


class TestLicenseDisplay:
    """Test license information display."""

    async def test_scroll_page_shows_cc_by_license(self, client: AsyncClient, test_db, test_user):
        """Test that CC BY license is displayed correctly."""
        # Create subject and scroll
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        scroll = Scroll(
            title="CC BY Test Scroll",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test Content</h1>",
            license="cc-by-4.0",
            status="published",
            preview_id="ccby123",
            user_id=test_user.id,
            subject_id=subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()

        # Check scroll page
        response = await client.get(f"/scroll/{scroll.preview_id}")
        assert response.status_code == 200

        # Should contain CC BY link and metadata
        assert "CC BY 4.0" in response.text
        assert "https://creativecommons.org/licenses/by/4.0/" in response.text
        assert 'rel="license"' in response.text

    async def test_scroll_page_shows_arr_license(self, client: AsyncClient, test_db, test_user):
        """Test that All Rights Reserved license is displayed correctly."""
        # Create subject and scroll
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        scroll = Scroll(
            title="ARR Test Scroll",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test Content</h1>",
            license="arr",
            status="published",
            preview_id="arr123",
            user_id=test_user.id,
            subject_id=subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()

        # Check scroll page
        response = await client.get(f"/scroll/{scroll.preview_id}")
        assert response.status_code == 200

        # Should contain ARR text but no CC license link
        assert "All Rights Reserved" in response.text
        assert "https://creativecommons.org/licenses/by/4.0/" not in response.text
        assert 'rel="license"' not in response.text


class TestLicenseExport:
    """Test license information in exports."""

    async def test_csv_export_includes_license(
        self, authenticated_client: AsyncClient, test_db, test_user
    ):
        """Test that CSV export includes license field."""
        # Create subject and scroll
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        scroll = Scroll(
            title="Export Test Scroll",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test Content</h1>",
            license="cc-by-4.0",
            status="published",
            preview_id="export123",
            user_id=test_user.id,
            subject_id=subject.id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()

        # Test CSV export
        response = await authenticated_client.post(
            "/export-data", data={"format": "csv", "include_content": "false"}
        )
        assert response.status_code == 200
        assert "cc-by-4.0" in response.text
        assert "license" in response.text  # Header

    async def test_json_export_includes_license(
        self, authenticated_client: AsyncClient, test_db, test_user
    ):
        """Test that JSON export includes license field."""
        # Create subject and scroll
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        scroll = Scroll(
            title="JSON Export Test",
            authors="Test Author",
            abstract="Test abstract",
            html_content="<h1>Test Content</h1>",
            license="arr",
            status="published",
            preview_id="json123",
            user_id=test_user.id,
            subject_id=subject.id,
        )
        scroll.publish()
        test_db.add(scroll)
        await test_db.commit()

        # Test JSON export
        response = await authenticated_client.post(
            "/export-data", data={"format": "json", "include_content": "false"}
        )
        assert response.status_code == 200
        assert '"license": "arr"' in response.text


class TestLicenseUploadForm:
    """Test license selection in upload form."""

    async def test_upload_form_shows_license_options(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test that upload form displays license selection options."""
        # Create subject for form
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()

        # Get upload form
        response = await authenticated_client.get("/upload")
        assert response.status_code == 200

        # Should contain license fieldset and options
        assert "License:" in response.text
        assert "Open Access (CC BY 4.0)" in response.text
        assert "All Rights Reserved" in response.text
        assert 'name="license"' in response.text
        assert 'value="cc-by-4.0"' in response.text
        assert 'value="arr"' in response.text

    async def test_upload_form_cc_by_default_selected(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test that CC BY 4.0 is selected by default."""
        # Create subject for form
        subject = Subject(name="Test Subject")
        test_db.add(subject)
        await test_db.commit()

        # Get upload form
        response = await authenticated_client.get("/upload")
        assert response.status_code == 200

        # CC BY should be checked by default - look for the specific pattern in the Jinja template
        assert 'id="license-cc-by"' in response.text
        # The template uses a conditional that results in 'checked' appearing for CC BY by default
        assert "checked" in response.text and "cc-by-4.0" in response.text

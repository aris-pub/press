"""Unit tests for Scroll model preview status validation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scroll import Scroll


@pytest.mark.asyncio
async def test_scroll_status_accepts_preview(test_db: AsyncSession, test_subject):
    """Test that scroll model accepts 'preview' status."""
    scroll = Scroll(
        title="Test Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="test123",
        url_hash="test123",
        status="preview",
    )

    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    assert scroll.status == "preview"
    assert scroll.published_at is None


@pytest.mark.asyncio
async def test_scroll_status_accepts_published(test_db: AsyncSession, test_subject):
    """Test that scroll model accepts 'published' status."""
    scroll = Scroll(
        title="Test Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="test456",
        url_hash="test456",
        status="published",
    )

    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)

    assert scroll.status == "published"


@pytest.mark.asyncio
async def test_scroll_status_rejects_invalid_status(test_db: AsyncSession, test_subject):
    """Test that scroll model rejects invalid status values."""
    with pytest.raises(ValueError, match="Status must be one of"):
        Scroll(
            title="Test Paper",
            authors="Test Author",
            subject_id=test_subject.id,
            abstract="Test abstract with sufficient length",
            html_content="<html><body><h1>Test</h1></body></html>",
            license="cc-by-4.0",
            content_hash="test789",
            url_hash="test789",
            status="draft",  # Invalid status
        )


@pytest.mark.asyncio
async def test_scroll_is_preview_method(test_db: AsyncSession, test_subject):
    """Test the is_preview() helper method."""
    preview_scroll = Scroll(
        title="Preview Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="prev123",
        url_hash="prev123",
        status="preview",
    )

    published_scroll = Scroll(
        title="Published Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="pub123",
        url_hash="pub123",
        status="published",
    )

    assert preview_scroll.is_preview() is True
    assert published_scroll.is_preview() is False


@pytest.mark.asyncio
async def test_publish_method_transitions_from_preview(test_db: AsyncSession, test_subject):
    """Test that publish() method transitions scroll from preview to published."""
    scroll = Scroll(
        title="Test Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        content_hash="trans123",
        url_hash="trans123",
        status="preview",
    )

    test_db.add(scroll)
    await test_db.commit()

    assert scroll.status == "preview"
    assert scroll.published_at is None

    # Publish the scroll
    scroll.publish()
    await test_db.commit()
    await test_db.refresh(scroll)

    assert scroll.status == "published"
    assert scroll.published_at is not None


@pytest.mark.asyncio
async def test_publish_method_requires_content_hash(test_db: AsyncSession, test_subject):
    """Test that publish() raises error without content_hash."""
    scroll = Scroll(
        title="Test Paper",
        authors="Test Author",
        subject_id=test_subject.id,
        abstract="Test abstract with sufficient length",
        html_content="<html><body><h1>Test</h1></body></html>",
        license="cc-by-4.0",
        status="preview",
    )

    with pytest.raises(ValueError, match="Cannot publish scroll without content hash"):
        scroll.publish()

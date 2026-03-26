"""Tests for Scroll.storage_type field."""

from app.models.scroll import Scroll
from app.storage.content_processing import generate_permanent_url


async def test_storage_type_defaults_to_inline(test_db, test_user, test_subject):
    url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Test</h1>")
    scroll = Scroll(
        title="Test",
        authors="Author",
        abstract="Abstract",
        html_content="<h1>Test</h1>",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=url_hash,
        status="published",
        user_id=test_user.id,
        subject_id=test_subject.id,
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    assert scroll.storage_type == "inline"


async def test_storage_type_can_be_archive(test_db, test_user, test_subject):
    url_hash, content_hash, _ = await generate_permanent_url(test_db, "<h1>Archive</h1>")
    scroll = Scroll(
        title="Archive Scroll",
        authors="Author",
        abstract="Abstract",
        html_content="<h1>Archive</h1>",
        license="cc-by-4.0",
        content_hash=content_hash,
        url_hash=url_hash,
        status="published",
        storage_type="archive",
        user_id=test_user.id,
        subject_id=test_subject.id,
    )
    test_db.add(scroll)
    await test_db.commit()
    await test_db.refresh(scroll)
    assert scroll.storage_type == "archive"

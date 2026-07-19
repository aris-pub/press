"""Tests for showcase scroll distinction on the homepage."""

from httpx import AsyncClient

from app.models.scroll import Subject
from tests.conftest import create_content_addressable_scroll


async def test_showcase_column_defaults_to_false(test_db, test_user, test_subject):
    """New scrolls should have is_showcase=False by default."""
    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Regular Scroll",
        html_content="<h1>Regular</h1>",
    )
    assert scroll.is_showcase is False


async def test_showcase_column_can_be_set_true(test_db, test_user, test_subject):
    """Scrolls can be explicitly marked as showcase."""
    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Showcase Scroll",
        html_content="<h1>Showcase</h1>",
    )
    scroll.is_showcase = True
    await test_db.commit()
    await test_db.refresh(scroll)
    assert scroll.is_showcase is True


async def test_homepage_example_scroll_band(client: AsyncClient, test_db, test_user):
    """A curated showcase scroll with a preview appears in the Example scrolls band."""
    subject = Subject(name="Mathematics", description="Math research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Title must match a curated entry in EXAMPLE_PREVIEWS to earn a figure preview.
    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Interactive Analysis of the Iris Dataset",
        html_content="<h1>Iris</h1>",
    )
    scroll.is_showcase = True
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    assert "Example scrolls" in response.text
    assert 'class="example-tag"' in response.text
    assert "/static/images/examples/iris.png" in response.text
    assert "Interactive Analysis of the Iris Dataset" in response.text


async def test_homepage_showcase_without_preview_goes_to_recent(
    client: AsyncClient, test_db, test_user
):
    """A showcase scroll with no curated preview falls through to the recent grid."""
    subject = Subject(name="Physics", description="Physics research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    # Real scroll
    real = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Real Research Paper",
        html_content="<h1>Real research</h1>",
    )
    assert real.is_showcase is False

    # Showcase scroll with a title that is NOT a curated example (no figure preview)
    showcase = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Demo Showcase Paper",
        html_content="<h1>Demo content</h1>",
    )
    showcase.is_showcase = True
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    assert "Recent Scrolls" in response.text
    assert "Real Research Paper" in response.text
    assert "Demo Showcase Paper" in response.text
    # Keeps its meta label in the recent grid
    assert '<span class="showcase-label">Showcase</span>' in response.text
    # The old separate Showcase section and its subtitles are gone
    assert "Curated scrolls demonstrating" not in response.text
    assert "Showcasing what's possible" not in response.text


async def test_homepage_no_showcase_subtitle_when_only_real(
    client: AsyncClient, test_db, test_user
):
    """When there are only real scrolls, no showcase section appears."""
    subject = Subject(name="Biology", description="Bio research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Real Biology Paper",
        html_content="<h1>Biology</h1>",
    )

    response = await client.get("/")
    assert response.status_code == 200
    assert "Real Biology Paper" in response.text
    assert "Showcase" not in response.text
    assert "Showcasing" not in response.text


async def test_showcase_label_in_card_meta(client: AsyncClient, test_db, test_user):
    """Showcase cards should show 'Showcase' instead of 'Submitted X ago' in meta."""
    subject = Subject(name="CS", description="CS research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    scroll = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Showcase Card Test",
        html_content="<h1>Test</h1>",
    )
    scroll.is_showcase = True
    await test_db.commit()

    response = await client.get("/")
    assert response.status_code == 200
    assert '<span class="showcase-label">Showcase</span>' in response.text


async def test_real_card_shows_submitted(client: AsyncClient, test_db, test_user):
    """Real (non-showcase) cards should show 'Submitted' in meta, not 'Showcase'."""
    subject = Subject(name="Chemistry", description="Chem research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Real Chem Paper",
        html_content="<h1>Chemistry</h1>",
    )

    response = await client.get("/")
    assert response.status_code == 200
    assert "Submitted recently" in response.text
    assert "showcase-label" not in response.text


async def test_partials_endpoint_splits_showcase(client: AsyncClient, test_db, test_user):
    """The HTMX partial endpoint should also split real vs showcase scrolls."""
    subject = Subject(name="Economics", description="Econ research")
    test_db.add(subject)
    await test_db.commit()
    await test_db.refresh(subject)

    await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Real Econ Paper",
        html_content="<h1>Economics</h1>",
    )

    showcase = await create_content_addressable_scroll(
        test_db,
        test_user,
        subject,
        title="Demo Econ Paper",
        html_content="<h1>Demo Econ</h1>",
    )
    showcase.is_showcase = True
    await test_db.commit()

    response = await client.get("/partials/scrolls")
    assert response.status_code == 200
    assert "Real Econ Paper" in response.text
    assert "Demo Econ Paper" in response.text
    assert "showcase-label" in response.text

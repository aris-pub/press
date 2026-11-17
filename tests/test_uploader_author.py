"""Only authors may post a paper (prs-e2v).

When the uploader's account name ("Test User" for test_user) is not in the author list,
the upload form asks which author they are. "None of the above" blocks the upload. The
chosen name is stored as scroll.uploader_author and places the uploader's ORCID.
"""

import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import select

from app.integrations.doi_service import attach_uploader_orcid
from app.models.scroll import Scroll
from app.models.user import User
from app.upload.authorship import (
    NONE_OF_THE_ABOVE,
    NOT_AN_AUTHOR,
    UploaderNotFoundError,
    resolve_uploader_author,
)

ORCID = "0000-0002-1825-0097"


class TestResolveUploaderAuthor:
    def test_account_name_in_list(self):
        assert resolve_uploader_author("Ada Lovelace, test  user", "Test User") == "test  user"

    def test_last_first_account_name_matches(self):
        assert resolve_uploader_author("Ada Lovelace, Test User", "User, Test") == "Test User"

    def test_chosen_name_wins(self):
        assert resolve_uploader_author("Ada Lovelace, T. User", "Test User", "T. User") == (
            "T. User"
        )

    def test_none_of_the_above_blocks(self):
        with pytest.raises(ValueError, match=NOT_AN_AUTHOR):
            resolve_uploader_author("Test User", "Test User", NONE_OF_THE_ABOVE)

    def test_no_match_and_no_choice_asks(self):
        with pytest.raises(UploaderNotFoundError, match="Test User"):
            resolve_uploader_author("Ada Lovelace, Alan Turing", "Test User")

    def test_choice_no_longer_in_list_asks_again(self):
        """The author list was edited after the choice was made."""
        with pytest.raises(UploaderNotFoundError):
            resolve_uploader_author("Ada Lovelace", "Test User", "T. User")


def _upload_data(subject, authors, **extra):
    return {
        "title": f"Paper {uuid.uuid4().hex[:8]}",
        "authors": authors,
        "subject_id": str(subject.id),
        "abstract": "An abstract with enough words to pass the validation checks.",
        "keywords": "",
        "license": "cc-by-4.0",
        "confirm_rights": "true",
        "action": "publish",
        **extra,
    }


def _html():
    return (
        "<!DOCTYPE html><html><head><title>P</title></head>"
        f"<body><h1>Paper {uuid.uuid4().hex}</h1><p>Enough words here.</p></body></html>"
    )


async def _post(client: AsyncClient, data):
    return await client.post(
        "/upload-form",
        data=data,
        files={"file": ("paper.html", _html(), "text/html")},
        follow_redirects=False,
    )


async def _scroll(test_db, title) -> Scroll:
    return (await test_db.execute(select(Scroll).where(Scroll.title == title))).scalar_one()


class TestUploadForm:
    @pytest.mark.asyncio
    async def test_account_name_in_list_stores_it(
        self, authenticated_client, test_db, test_subject
    ):
        data = _upload_data(test_subject, "Ada Lovelace, Test User")
        response = await _post(authenticated_client, data)
        assert response.status_code == 303
        assert (await _scroll(test_db, data["title"])).uploader_author == "Test User"

    @pytest.mark.asyncio
    async def test_no_match_returns_form_with_the_question(
        self, authenticated_client, test_subject
    ):
        response = await _post(authenticated_client, _upload_data(test_subject, "Ada, Alan"))
        assert response.status_code == 422
        assert "Which author are you?" in response.text
        group = response.text.split('id="uploader-author-group"')[1].split(">")[0]
        assert "hidden" not in group
        assert '<option value="Ada">Ada</option>' in response.text
        assert '<option value="__none__"' in response.text

    @pytest.mark.asyncio
    async def test_chosen_author_is_stored(self, authenticated_client, test_db, test_subject):
        data = _upload_data(test_subject, "Ada Lovelace, T. User", uploader_author="T. User")
        response = await _post(authenticated_client, data)
        assert response.status_code == 303
        assert (await _scroll(test_db, data["title"])).uploader_author == "T. User"

    @pytest.mark.asyncio
    async def test_none_of_the_above_is_refused(self, authenticated_client, test_subject):
        data = _upload_data(test_subject, "Ada Lovelace", uploader_author=NONE_OF_THE_ABOVE)
        response = await _post(authenticated_client, data)
        assert response.status_code == 422
        assert NOT_AN_AUTHOR in response.text

    @pytest.mark.asyncio
    async def test_question_hidden_when_name_matches(self, authenticated_client):
        response = await authenticated_client.get("/upload")
        group = response.text.split('id="uploader-author-group"')[1].split(">")[0]
        assert "hidden" in group


class TestOrcidPlacement:
    def test_zenodo_uses_the_chosen_author(self):
        uploader = User(email="u@example.com", password_hash="x", display_name="Test User")
        uploader.orcid_id = ORCID
        creators = [{"name": "Ada Lovelace"}, {"name": "T. User"}]
        result = attach_uploader_orcid(creators, uploader, "T. User")
        assert result == [{"name": "Ada Lovelace"}, {"name": "T. User", "orcid": ORCID}]

    @pytest.mark.asyncio
    async def test_details_modal_uses_the_chosen_author(
        self, authenticated_client, test_db, test_user, test_subject
    ):
        test_user.orcid_id = ORCID
        data = _upload_data(test_subject, "T. User, Ada Lovelace", uploader_author="T. User")
        await _post(authenticated_client, data)
        scroll = await _scroll(test_db, data["title"])
        scroll.status = "published"
        await test_db.commit()

        response = await authenticated_client.get(f"/scroll/{scroll.url_hash}")
        authors = response.text.split('class="details-authors">')[1].split("</div>")[0]
        assert authors.index("T. User") < authors.index("orcid.org") < authors.index("Ada")

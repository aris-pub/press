"""Tests for the Zenodo link back to Press, uploader ORCIDs, and the metadata backfill."""

import copy
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.doi_service import (
    DOIService,
    attach_uploader_orcid,
    is_valid_orcid,
    merge_backfill_metadata,
    mint_doi_async,
)
from app.integrations.zenodo import ZenodoClient, ZenodoConfig, ZenodoDeposit
from app.models.user import User
from scripts.backfill_zenodo_metadata import backfill
from tests.conftest import create_content_addressable_scroll

VALID_ORCID = "0000-0002-1825-0097"
BASE_URL = "https://scroll.press"


def _user(display_name="Test User", orcid_id=VALID_ORCID):
    return User(
        email="u@example.com", password_hash="x", display_name=display_name, orcid_id=orcid_id
    )


def _mock_client(handler):
    client = ZenodoClient(ZenodoConfig(api_token="token", base_url="https://zenodo.test"))
    client.client = httpx.AsyncClient(
        base_url="https://zenodo.test", transport=httpx.MockTransport(handler)
    )
    return client


def _related(url_hash):
    return {
        "identifier": f"{BASE_URL}/scroll/{url_hash}",
        "relation": "isIdenticalTo",
        "resource_type": "publication-preprint",
    }


class TestCreateDepositPayload:
    @pytest.mark.asyncio
    async def test_related_identifiers_sent_in_metadata(self):
        sent = {}

        def handler(request):
            sent["body"] = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "metadata": {"prereserve_doi": {"doi": "10.5281/zenodo.1"}},
                    "links": {"bucket": "https://zenodo.test/bucket"},
                },
            )

        client = _mock_client(handler)
        related = [_related("abc123")]
        await client.create_deposit(
            title="T",
            creators=[{"name": "A"}],
            description="D",
            publication_date="2026-01-01",
            keywords=[],
            related_identifiers=related,
        )
        metadata = sent["body"]["metadata"]
        assert metadata["related_identifiers"] == related
        assert metadata["upload_type"] == "publication"
        assert metadata["publication_type"] == "preprint"

    @pytest.mark.asyncio
    async def test_no_related_identifiers_key_when_not_given(self):
        sent = {}

        def handler(request):
            sent["body"] = json.loads(request.content)
            return httpx.Response(
                201,
                json={
                    "id": 1,
                    "metadata": {"prereserve_doi": {"doi": "10.5281/zenodo.1"}},
                    "links": {"bucket": "https://zenodo.test/bucket"},
                },
            )

        client = _mock_client(handler)
        await client.create_deposit(
            title="T",
            creators=[{"name": "A"}],
            description="D",
            publication_date="2026-01-01",
            keywords=[],
        )
        assert "related_identifiers" not in sent["body"]["metadata"]


class TestEditClientMethods:
    @pytest.mark.asyncio
    async def test_edit_update_discard_hit_deposit_api(self):
        calls = []

        def handler(request):
            body = json.loads(request.content) if request.content else None
            calls.append((request.method, request.url.path, body))
            return httpx.Response(200, json={"id": 7})

        client = _mock_client(handler)
        await client.get_deposit(7)
        await client.edit_deposit(7)
        await client.update_deposit_metadata(7, {"title": "T"})
        await client.discard_deposit_edit(7)
        assert calls == [
            ("GET", "/api/deposit/depositions/7", None),
            ("POST", "/api/deposit/depositions/7/actions/edit", None),
            ("PUT", "/api/deposit/depositions/7", {"metadata": {"title": "T"}}),
            ("POST", "/api/deposit/depositions/7/actions/discard", None),
        ]

    @pytest.mark.asyncio
    async def test_publish_without_bucket_link(self):
        def handler(request):
            return httpx.Response(
                202,
                json={"id": 7, "doi": "10.5281/zenodo.7", "doi_url": "https://doi.org/x"},
            )

        client = _mock_client(handler)
        deposit = await client.publish_deposit(7)
        assert deposit.doi == "10.5281/zenodo.7"


class TestAttachUploaderOrcid:
    def test_attached_on_exact_match(self):
        result = attach_uploader_orcid([{"name": "Test User"}], _user())
        assert result == [{"name": "Test User", "orcid": VALID_ORCID}]

    def test_match_ignores_case_and_whitespace(self):
        result = attach_uploader_orcid([{"name": "  test   USER "}], _user())
        assert result[0]["orcid"] == VALID_ORCID

    def test_match_handles_family_comma_given(self):
        result = attach_uploader_orcid([{"name": "User, Test"}], _user())
        assert result[0]["orcid"] == VALID_ORCID

    def test_never_attached_to_coauthor(self):
        result = attach_uploader_orcid(
            [{"name": "Ada Lovelace"}, {"name": "Test User"}, {"name": "Alan Turing"}], _user()
        )
        assert "orcid" not in result[0]
        assert result[1]["orcid"] == VALID_ORCID
        assert "orcid" not in result[2]

    def test_none_when_uploader_not_in_authors(self):
        result = attach_uploader_orcid([{"name": "Ada Lovelace"}], _user())
        assert result == [{"name": "Ada Lovelace"}]

    def test_none_when_uploader_has_no_orcid(self):
        result = attach_uploader_orcid([{"name": "Test User"}], _user(orcid_id=None))
        assert result == [{"name": "Test User"}]

    def test_none_when_no_uploader(self):
        assert attach_uploader_orcid([{"name": "Test User"}], None) == [{"name": "Test User"}]

    def test_none_when_name_is_ambiguous(self):
        creators = [{"name": "Test User"}, {"name": "test user"}]
        assert attach_uploader_orcid(creators, _user()) == creators

    def test_existing_different_orcid_kept(self):
        creators = [{"name": "Test User", "orcid": "0000-0001-5109-3700"}]
        assert attach_uploader_orcid(creators, _user()) == creators

    def test_bad_checksum_not_sent(self):
        assert not is_valid_orcid("0000-0002-1825-0098")
        assert is_valid_orcid("0000-0001-5109-3700")
        assert is_valid_orcid("0000-0002-1694-233X")
        result = attach_uploader_orcid(
            [{"name": "Test User"}], _user(orcid_id="0000-0002-1825-0098")
        )
        assert "orcid" not in result[0]


class TestMintDoi:
    def _zenodo(self):
        zenodo = AsyncMock()
        zenodo.create_deposit.return_value = ZenodoDeposit(
            deposit_id=1, doi="10.5281/zenodo.1", doi_url="u", bucket_url="b", status="draft"
        )
        zenodo.publish_deposit.return_value = ZenodoDeposit(
            deposit_id=1, doi="10.5281/zenodo.1", doi_url="u", bucket_url="b", status="published"
        )
        return zenodo

    @pytest.mark.asyncio
    async def test_deposit_gets_hash_url_and_uploader_orcid(
        self, test_db, test_user, test_subject
    ):
        test_user.orcid_id = VALID_ORCID
        scroll = await create_content_addressable_scroll(
            test_db, test_user, test_subject, authors="Ada Lovelace, Test User"
        )
        zenodo = self._zenodo()

        assert await DOIService(zenodo).mint_doi_for_scroll(scroll, test_db, uploader=test_user)

        kwargs = zenodo.create_deposit.call_args.kwargs
        assert kwargs["related_identifiers"] == [_related(scroll.url_hash)]
        assert kwargs["creators"] == [
            {"name": "Ada Lovelace"},
            {"name": "Test User", "orcid": VALID_ORCID},
        ]

    @pytest.mark.asyncio
    async def test_no_orcid_when_uploader_has_none(self, test_db, test_user, test_subject):
        scroll = await create_content_addressable_scroll(
            test_db, test_user, test_subject, authors="Test User"
        )
        zenodo = self._zenodo()

        await DOIService(zenodo).mint_doi_for_scroll(scroll, test_db, uploader=test_user)

        assert zenodo.create_deposit.call_args.kwargs["creators"] == [{"name": "Test User"}]

    @pytest.mark.asyncio
    async def test_background_task_loads_uploader(self, test_db, test_user, test_subject):
        test_user.orcid_id = VALID_ORCID
        scroll = await create_content_addressable_scroll(
            test_db, test_user, test_subject, authors="Test User"
        )
        scroll_id = str(scroll.id)
        test_db.expunge_all()
        zenodo = self._zenodo()

        # The task closes its session, which would break the fixture's own session.
        with (
            patch("app.database.AsyncSessionLocal", return_value=test_db),
            patch.object(test_db, "close", AsyncMock()),
            patch("app.integrations.doi_service.get_zenodo_client", return_value=zenodo),
        ):
            await mint_doi_async(scroll_id)

        creators = zenodo.create_deposit.call_args.kwargs["creators"]
        assert creators == [{"name": "Test User", "orcid": VALID_ORCID}]


def _published_metadata():
    metadata = {
        "title": "Old title",
        "upload_type": "publication",
        "publication_type": "preprint",
        "description": "Abstract",
        "creators": [{"name": "Ada Lovelace"}, {"name": "Test User"}],
        "publication_date": "2026-01-01",
        "keywords": ["k"],
        "access_right": "open",
        "license": "cc-by-4.0",
        "communities": [{"identifier": "scrollpress"}],
        "doi": "10.5281/zenodo.1",
        "related_identifiers": [{"identifier": "10.1234/other", "relation": "cites"}],
    }
    return metadata


class FakeZenodo:
    """Stands in for ZenodoClient and keeps one record per deposit in memory."""

    def __init__(self, records):
        self.records = records
        self.writes = []

    async def get_deposit(self, deposit_id):
        return {"id": deposit_id, "metadata": copy.deepcopy(self.records[deposit_id])}

    async def edit_deposit(self, deposit_id):
        self.writes.append(("edit", deposit_id))

    async def update_deposit_metadata(self, deposit_id, metadata):
        self.writes.append(("update", deposit_id))
        self.records[deposit_id] = copy.deepcopy(metadata)

    async def publish_deposit(self, deposit_id):
        self.writes.append(("publish", deposit_id))

    async def discard_deposit_edit(self, deposit_id):
        self.writes.append(("discard", deposit_id))


async def _minted_scroll(test_db, test_user, test_subject, deposit_id=42):
    test_user.orcid_id = VALID_ORCID
    scroll = await create_content_addressable_scroll(
        test_db, test_user, test_subject, authors="Ada Lovelace, Test User"
    )
    scroll.doi_status = "minted"
    scroll.doi = "10.5281/zenodo.1"
    scroll.zenodo_deposit_id = deposit_id
    await test_db.commit()
    return scroll


class TestBackfill:
    @pytest.mark.asyncio
    async def test_dry_run_writes_nothing(self, test_db, test_user, test_subject):
        await _minted_scroll(test_db, test_user, test_subject)
        original = _published_metadata()
        zenodo = FakeZenodo({42: copy.deepcopy(original)})
        lines = []

        counts = await backfill(test_db, zenodo, BASE_URL, apply=False, out=lines.append)

        assert counts["would_update"] == 1
        assert zenodo.writes == []
        assert zenodo.records[42] == original
        assert any("New related_identifiers" in line for line in lines)

    @pytest.mark.asyncio
    async def test_apply_merges_and_is_idempotent(self, test_db, test_user, test_subject):
        scroll = await _minted_scroll(test_db, test_user, test_subject)
        original = _published_metadata()
        zenodo = FakeZenodo({42: copy.deepcopy(original)})

        counts = await backfill(test_db, zenodo, BASE_URL, apply=True, out=lambda _: None)

        assert counts["updated"] == 1
        assert zenodo.writes == [("edit", 42), ("update", 42), ("publish", 42)]
        new = zenodo.records[42]
        for key, value in original.items():
            if key not in ("related_identifiers", "creators"):
                assert new[key] == value
        assert new["related_identifiers"] == [
            {"identifier": "10.1234/other", "relation": "cites"},
            _related(scroll.url_hash),
        ]
        assert new["creators"] == [
            {"name": "Ada Lovelace"},
            {"name": "Test User", "orcid": VALID_ORCID},
        ]

        zenodo.writes.clear()
        counts = await backfill(test_db, zenodo, BASE_URL, apply=True, out=lambda _: None)
        assert counts["skipped"] == 1
        assert zenodo.writes == []

    @pytest.mark.asyncio
    async def test_failed_update_discards_edit(self, test_db, test_user, test_subject):
        from app.integrations.zenodo import ZenodoError

        await _minted_scroll(test_db, test_user, test_subject)
        zenodo = FakeZenodo({42: _published_metadata()})

        async def fail(deposit_id, metadata):
            raise ZenodoError("bad metadata", status_code=400)

        zenodo.update_deposit_metadata = fail

        counts = await backfill(test_db, zenodo, BASE_URL, apply=True, out=lambda _: None)

        assert counts["failed"] == 1
        assert zenodo.writes == [("edit", 42), ("discard", 42)]

    @pytest.mark.asyncio
    async def test_skips_scrolls_without_minted_doi(self, test_db, test_user, test_subject):
        scroll = await create_content_addressable_scroll(test_db, test_user, test_subject)
        scroll.doi_status = "failed"
        scroll.zenodo_deposit_id = 99
        await test_db.commit()
        zenodo = FakeZenodo({})

        counts = await backfill(test_db, zenodo, BASE_URL, apply=True, out=lambda _: None)

        assert counts == {"would_update": 0, "updated": 0, "skipped": 0, "failed": 0}


def test_merge_returns_none_when_nothing_to_change():
    class S:
        url_hash = "abc"

    metadata = {
        "creators": [{"name": "Test User", "orcid": VALID_ORCID}],
        "related_identifiers": [_related("abc")],
    }
    assert merge_backfill_metadata(metadata, S(), _user(), BASE_URL) is None

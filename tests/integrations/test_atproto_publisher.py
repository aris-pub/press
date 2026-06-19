"""Tests for the AtprotoPublisher orchestrator.

The publisher converts a Scroll to a Lexicon record, calls the AtprotoClient
to upsert it, and writes the resulting at:// URI / CID / status / timestamp
back onto the Scroll row. Tests use a fake client (in-process, no SDK, no
network) and the real async test DB so the writeback behavior is exercised.
"""

import pytest
import pytest_asyncio

from tests.conftest import create_content_addressable_scroll


class FakeAtprotoClient:
    """In-process fake for AtprotoClient that records put_record calls and
    returns canned responses. Used so publisher tests can assert on the full
    Scroll -> client.put_record -> DB-writeback flow without an SDK or PDS.
    """

    def __init__(self):
        self.did = "did:plc:fake"
        self.put_record_calls: list[dict] = []
        self.next_uri = "at://did:plc:fake/pub.aris.scroll/abcdef123456"
        self.next_cid = "bafy_test_cid"
        self.should_fail = False
        self.fail_with = RuntimeError("simulated SDK failure")

    def put_record(self, collection, rkey, record):
        self.put_record_calls.append(
            dict(collection=collection, rkey=rkey, record=record)
        )
        if self.should_fail:
            raise self.fail_with

        class _Resp:
            def __init__(self, uri, cid):
                self.uri = uri
                self.cid = cid

        # Derive URI from rkey so the DB's unique constraint on atproto_uri is
        # satisfied when multiple scrolls are published in the same test.
        return _Resp(f"at://{self.did}/{collection}/{rkey}", f"{self.next_cid}-{rkey}")


@pytest_asyncio.fixture
async def published_scroll(test_db, test_user, test_subject):
    return await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Test Publishable Scroll",
        authors="Leo Torres, Alice Liddell",
        abstract="An abstract.",
    )


@pytest.mark.asyncio
async def test_publisher_writes_uri_cid_status_on_success(test_db, published_scroll):
    from app.integrations.atproto.publisher import AtprotoPublisher

    fake = FakeAtprotoClient()
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    result = await publisher.publish_scroll(published_scroll, test_db)

    assert result is True
    await test_db.refresh(published_scroll)
    expected_uri = f"at://did:plc:fake/pub.aris.scroll/{published_scroll.url_hash}"
    assert published_scroll.atproto_uri == expected_uri
    assert published_scroll.atproto_cid.startswith("bafy_test_cid-")
    assert published_scroll.atproto_status == "published"
    assert published_scroll.atproto_published_at is not None


@pytest.mark.asyncio
async def test_publisher_uses_url_hash_as_rkey(test_db, published_scroll):
    """Idempotency hinges on rkey = url_hash: a repeat publish becomes an
    upsert at the same atproto URI rather than a duplicate record.
    """
    from app.integrations.atproto.publisher import AtprotoPublisher

    fake = FakeAtprotoClient()
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    await publisher.publish_scroll(published_scroll, test_db)

    assert len(fake.put_record_calls) == 1
    assert fake.put_record_calls[0]["rkey"] == published_scroll.url_hash
    assert fake.put_record_calls[0]["collection"] == "pub.aris.scroll"


@pytest.mark.asyncio
async def test_publisher_sends_lexicon_shaped_record(test_db, published_scroll):
    """The record passed to put_record must match the Lexicon shape; this is
    the integration point between the converter and the client.
    """
    from app.integrations.atproto.publisher import AtprotoPublisher

    fake = FakeAtprotoClient()
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    await publisher.publish_scroll(published_scroll, test_db)

    record = fake.put_record_calls[0]["record"]
    assert record["title"] == "Test Publishable Scroll"
    assert record["urlHash"] == published_scroll.url_hash
    assert record["contentHash"] == published_scroll.content_hash
    assert record["arch"] == "1.0"
    assert record["format"] == "interactive_html"
    assert len(record["authors"]) == 2


@pytest.mark.asyncio
async def test_publisher_marks_failed_on_sdk_error(test_db, published_scroll):
    """When the client raises, the publisher writes status=failed and returns
    False; the row is left in a state that allows retry from the CLI.
    """
    from app.integrations.atproto.publisher import AtprotoPublisher

    fake = FakeAtprotoClient()
    fake.should_fail = True
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    result = await publisher.publish_scroll(published_scroll, test_db)

    assert result is False
    await test_db.refresh(published_scroll)
    assert published_scroll.atproto_status == "failed"
    assert published_scroll.atproto_uri is None
    assert published_scroll.atproto_cid is None


@pytest.mark.asyncio
async def test_publisher_is_idempotent_across_two_calls(test_db, published_scroll):
    """Two publish_scroll calls produce two put_record calls (the SDK level
    upsert is what makes the result idempotent), with the same rkey, and the
    Scroll row ends up in the same published state.
    """
    from app.integrations.atproto.publisher import AtprotoPublisher

    fake = FakeAtprotoClient()
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    await publisher.publish_scroll(published_scroll, test_db)
    await publisher.publish_scroll(published_scroll, test_db)

    assert len(fake.put_record_calls) == 2
    assert (
        fake.put_record_calls[0]["rkey"]
        == fake.put_record_calls[1]["rkey"]
        == published_scroll.url_hash
    )
    await test_db.refresh(published_scroll)
    assert published_scroll.atproto_status == "published"


@pytest.mark.asyncio
async def test_publish_all_iterates_published_scrolls(test_db, test_user, test_subject):
    """publish_all walks every published scroll. Demo seed scrolls included by
    design (Leo: 'the four demo scrolls are intended to be published').
    """
    from app.integrations.atproto.publisher import AtprotoPublisher

    s1 = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="First",
        authors="A B",
        html_content="<h1>First scroll</h1>",
    )
    s2 = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Second",
        authors="C D",
        html_content="<h1>Second scroll</h1>",
    )

    fake = FakeAtprotoClient()
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    count = await publisher.publish_all(test_db)

    assert count == 2
    assert len(fake.put_record_calls) == 2
    rkeys = {c["rkey"] for c in fake.put_record_calls}
    assert rkeys == {s1.url_hash, s2.url_hash}


@pytest.mark.asyncio
async def test_publish_all_continues_after_per_scroll_failure(
    test_db, test_user, test_subject
):
    """One scroll failing must not abort the whole batch; publish_all reports
    partial success.
    """
    from app.integrations.atproto.publisher import AtprotoPublisher

    s1 = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="First",
        authors="A B",
        html_content="<h1>First scroll</h1>",
    )
    s2 = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="Second",
        authors="C D",
        html_content="<h1>Second scroll</h1>",
    )

    call_count = [0]

    class FailFirst(FakeAtprotoClient):
        def put_record(self, collection, rkey, record):
            call_count[0] += 1
            if call_count[0] == 1:
                self.put_record_calls.append(
                    dict(collection=collection, rkey=rkey, record=record)
                )
                raise RuntimeError("first fails")
            return super().put_record(collection, rkey, record)

    fake = FailFirst()
    publisher = AtprotoPublisher(client=fake, base_url="https://scroll.press")

    count = await publisher.publish_all(test_db)

    assert count == 1
    await test_db.refresh(s1)
    await test_db.refresh(s2)
    statuses = {s1.atproto_status, s2.atproto_status}
    assert statuses == {"failed", "published"}

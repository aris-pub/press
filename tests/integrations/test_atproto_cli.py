"""Smoke tests for the publish_atproto CLI script.

End-to-end at the CLI level: invoke main() with a fake SDK injected through
the AtprotoClient factory, assert it walks the published scrolls.
"""

import sys

import pytest
import pytest_asyncio

from tests.conftest import create_content_addressable_scroll


class FakeSDKClient:
    """Reused from test_atproto_client.py shape but inlined to keep this file
    self-contained.
    """

    def __init__(self):
        self.put_record_calls = []
        self.login_calls = []

    def login(self, handle, app_password):
        self.login_calls.append((handle, app_password))

    class _Repo:
        def __init__(self, parent):
            self._parent = parent

        def put_record(self, data):
            self._parent.put_record_calls.append(
                dict(repo=data.repo, collection=data.collection, rkey=data.rkey)
            )

            class _Resp:
                pass

            r = _Resp()
            r.uri = f"at://{data.repo}/{data.collection}/{data.rkey}"
            r.cid = f"bafy-{data.rkey}"
            return r

    @property
    def com(self):
        return type(
            "Com",
            (),
            {"atproto": type("Atproto", (), {"repo": FakeSDKClient._Repo(self)})()},
        )()


@pytest_asyncio.fixture
async def two_published_scrolls(test_db, test_user, test_subject):
    s1 = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="GLEE",
        authors="Leo Torres, Kevin Chan",
        html_content="<h1>GLEE content</h1>",
    )
    s2 = await create_content_addressable_scroll(
        test_db,
        test_user,
        test_subject,
        title="The rich are loopy",
        authors="Leo Torres",
        html_content="<h1>Loops content</h1>",
    )
    return s1, s2


def _patch_cli(monkeypatch, fake_sdk, test_db):
    """Wire up the env, SDK, and test-DB session for CLI tests.

    Returns the imported scripts.publish_atproto module ready to use.
    """
    monkeypatch.setenv("ATPROTO_HANDLE", "aris-pub.bsky.social")
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "test-pw")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:fake")
    monkeypatch.setenv("ATPROTO_PDS_URL", "https://example.host.bsky.network")
    monkeypatch.setenv("BASE_URL", "https://scroll.press")

    import app.integrations.atproto.client as client_mod

    monkeypatch.setattr(client_mod, "_default_sdk_factory", lambda pds_url: fake_sdk)

    import scripts.publish_atproto as cli

    class _SessionManager:
        async def __aenter__(self_):
            return test_db

        async def __aexit__(self_, *a):
            return False

    monkeypatch.setattr(cli, "AsyncSessionLocal", lambda: _SessionManager())
    return cli


@pytest.mark.asyncio
async def test_cli_publish_all_async_path(
    monkeypatch, capsys, two_published_scrolls, test_db
):
    """The async entry point publish_all() walks every scroll. Called directly
    (not through main()) because pytest-asyncio already owns the loop.
    """
    fake_sdk = FakeSDKClient()
    cli = _patch_cli(monkeypatch, fake_sdk, test_db)

    rc = await cli.publish_all()
    out = capsys.readouterr()

    assert rc == 0
    assert "published 2 scrolls" in out.out
    assert len(fake_sdk.put_record_calls) == 2


@pytest.mark.asyncio
async def test_cli_publish_one_async_path(
    monkeypatch, capsys, two_published_scrolls, test_db
):
    s1, _ = two_published_scrolls
    fake_sdk = FakeSDKClient()
    cli = _patch_cli(monkeypatch, fake_sdk, test_db)

    rc = await cli.publish_one(s1.url_hash)
    out = capsys.readouterr()

    assert rc == 0
    assert s1.url_hash in out.out
    assert len(fake_sdk.put_record_calls) == 1
    assert fake_sdk.put_record_calls[0]["rkey"] == s1.url_hash


def test_cli_unknown_command_exits_64(capsys):
    import scripts.publish_atproto as cli

    rc = cli.main(["publish_atproto.py", "totally-not-a-command"])
    err = capsys.readouterr().err
    assert rc == 64
    assert "unknown command" in err


def test_cli_no_args_prints_usage(capsys):
    import scripts.publish_atproto as cli

    rc = cli.main(["publish_atproto.py"])
    out = capsys.readouterr().out
    assert rc == 64
    assert "publish-all" in out


@pytest.mark.asyncio
async def test_cli_publish_one_missing_url_hash_returns_1(
    monkeypatch, capsys, test_db
):
    fake_sdk = FakeSDKClient()
    cli = _patch_cli(monkeypatch, fake_sdk, test_db)

    rc = await cli.publish_one("nonexistent-hash-xyz")
    err = capsys.readouterr().err
    assert rc == 1
    assert "no scroll" in err

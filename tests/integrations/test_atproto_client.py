"""Tests for the atproto SDK client wrapper.

The wrapper exists so the publisher does not depend on the SDK directly.
Tests pin the wrapper's behavior (login, idempotent put_record) using a
fake-protocol stand-in for the SDK; the SDK itself is exercised only by the
single manual integration step Leo runs against bsky.social before shipping.
"""

import pytest


class FakeSDKClient:
    """Stand-in for atproto.Client. Records calls and lets tests assert on them."""

    def __init__(self):
        self.login_calls: list[tuple[str, str]] = []
        self.put_record_calls: list[dict] = []
        self.login_should_fail = False
        self.put_record_should_fail = False
        self.put_record_response = type(
            "PutRecordResponse",
            (),
            {"uri": "at://did:plc:fake/pub.aris.scroll/abc123", "cid": "bafytestcid"},
        )()

    def login(self, handle, app_password):
        self.login_calls.append((handle, app_password))
        if self.login_should_fail:
            raise RuntimeError("auth failed")

    class _Repo:
        def __init__(self, parent):
            self._parent = parent

        def put_record(self, data):
            self._parent.put_record_calls.append(
                dict(
                    repo=data.repo,
                    collection=data.collection,
                    rkey=data.rkey,
                    record=data.record,
                )
            )
            if self._parent.put_record_should_fail:
                raise RuntimeError("put_record failed")
            return self._parent.put_record_response

    @property
    def com(self):
        return type(
            "Com",
            (),
            {
                "atproto": type(
                    "Atproto",
                    (),
                    {"repo": FakeSDKClient._Repo(self)},
                )()
            },
        )()


@pytest.fixture
def fake_sdk(monkeypatch):
    fake = FakeSDKClient()
    return fake


def test_client_logs_in_with_credentials(fake_sdk):
    from app.integrations.atproto.client import AtprotoClient

    client = AtprotoClient(
        handle="aris-pub.bsky.social",
        app_password="xxxx-xxxx-xxxx-xxxx",
        did="did:plc:abc",
        pds_url="https://example.host.bsky.network",
        sdk_client_factory=lambda pds_url: fake_sdk,
    )
    client.login()

    assert fake_sdk.login_calls == [("aris-pub.bsky.social", "xxxx-xxxx-xxxx-xxxx")]


def test_put_record_logs_in_once_then_calls_sdk(fake_sdk):
    from app.integrations.atproto.client import AtprotoClient

    client = AtprotoClient(
        handle="aris-pub.bsky.social",
        app_password="xxxx",
        did="did:plc:abc",
        pds_url="https://example.host.bsky.network",
        sdk_client_factory=lambda pds_url: fake_sdk,
    )

    result = client.put_record(
        collection="pub.aris.scroll",
        rkey="9bf73ea5ee86",
        record={"title": "GLEE", "urlHash": "9bf73ea5ee86"},
    )

    assert len(fake_sdk.login_calls) == 1
    assert len(fake_sdk.put_record_calls) == 1
    call = fake_sdk.put_record_calls[0]
    assert call["repo"] == "did:plc:abc"
    assert call["collection"] == "pub.aris.scroll"
    assert call["rkey"] == "9bf73ea5ee86"
    assert call["record"]["title"] == "GLEE"
    assert result.uri == "at://did:plc:fake/pub.aris.scroll/abc123"
    assert result.cid == "bafytestcid"


def test_put_record_does_not_re_login_on_second_call(fake_sdk):
    """Login is a one-shot per AtprotoClient instance; subsequent put_record
    calls reuse the session.
    """
    from app.integrations.atproto.client import AtprotoClient

    client = AtprotoClient(
        handle="aris-pub.bsky.social",
        app_password="xxxx",
        did="did:plc:abc",
        pds_url="https://example.host.bsky.network",
        sdk_client_factory=lambda pds_url: fake_sdk,
    )
    client.put_record(collection="pub.aris.scroll", rkey="a", record={"x": 1})
    client.put_record(collection="pub.aris.scroll", rkey="b", record={"x": 2})

    assert len(fake_sdk.login_calls) == 1
    assert len(fake_sdk.put_record_calls) == 2


def test_put_record_raises_on_sdk_failure(fake_sdk):
    """SDK errors propagate to the caller; the publisher catches at its layer."""
    from app.integrations.atproto.client import AtprotoClient

    fake_sdk.put_record_should_fail = True
    client = AtprotoClient(
        handle="aris-pub.bsky.social",
        app_password="xxxx",
        did="did:plc:abc",
        pds_url="https://example.host.bsky.network",
        sdk_client_factory=lambda pds_url: fake_sdk,
    )

    with pytest.raises(RuntimeError, match="put_record failed"):
        client.put_record(collection="pub.aris.scroll", rkey="x", record={})


def test_login_failure_surfaces_to_caller(fake_sdk):
    from app.integrations.atproto.client import AtprotoClient

    fake_sdk.login_should_fail = True
    client = AtprotoClient(
        handle="aris-pub.bsky.social",
        app_password="bad",
        did="did:plc:abc",
        pds_url="https://example.host.bsky.network",
        sdk_client_factory=lambda pds_url: fake_sdk,
    )

    with pytest.raises(RuntimeError, match="auth failed"):
        client.login()


def test_from_env_reads_fly_secrets(monkeypatch):
    """The CLI/publisher constructs AtprotoClient.from_env() to pick up the
    handle/password/did/pds-url from Fly secrets without threading them through
    every call.
    """
    from app.integrations.atproto.client import AtprotoClient

    monkeypatch.setenv("ATPROTO_HANDLE", "aris-pub.bsky.social")
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "secret-pw")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:7i46wjtdwxov7vxxlkfnafbd")
    monkeypatch.setenv("ATPROTO_PDS_URL", "https://agrocybe.us-west.host.bsky.network")

    client = AtprotoClient.from_env(sdk_client_factory=lambda pds_url: FakeSDKClient())
    assert client.handle == "aris-pub.bsky.social"
    assert client.did == "did:plc:7i46wjtdwxov7vxxlkfnafbd"
    assert client.pds_url == "https://agrocybe.us-west.host.bsky.network"


def test_from_env_raises_when_credentials_missing(monkeypatch):
    """If a deploy is missing one of the four required secrets, from_env must
    fail loudly rather than silently producing a half-configured client.
    """
    from app.integrations.atproto.client import AtprotoClient

    monkeypatch.delenv("ATPROTO_HANDLE", raising=False)
    monkeypatch.setenv("ATPROTO_APP_PASSWORD", "x")
    monkeypatch.setenv("ATPROTO_DID", "did:plc:abc")
    monkeypatch.setenv("ATPROTO_PDS_URL", "https://x")

    with pytest.raises(RuntimeError, match="ATPROTO_HANDLE"):
        AtprotoClient.from_env(sdk_client_factory=lambda pds_url: FakeSDKClient())

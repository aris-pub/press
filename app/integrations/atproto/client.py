"""Thin wrapper around the community atproto SDK.

The wrapper exists so the publisher does not depend on the SDK directly: that
keeps the publisher unit-testable with a fake client (see tests/integrations/
test_atproto_client.py) and lets us swap the SDK for a minimal httpx-based
client later if needed without touching call sites.

This wrapper is intentionally small. Anything beyond auth + put_record belongs
in the publisher or in a separate SDK-aware module.
"""

import os
from typing import Callable, Optional

from atproto import Client


def _default_sdk_factory(pds_url: str) -> Client:
    """Build a real atproto SDK client pointed at the given PDS URL.

    Bluesky accounts now sit on per-user PDS endpoints (e.g.
    https://agrocybe.us-west.host.bsky.network) rather than the default
    bsky.social. The PDS URL must come from the DID document, not be assumed.
    """
    return Client(base_url=pds_url)


class AtprotoClient:
    """Authenticated client for writing pub.aris.scroll records to a PDS.

    Lazily logs in on the first call that requires a session. Reuses the
    session across subsequent calls within the same instance.
    """

    def __init__(
        self,
        handle: str,
        app_password: str,
        did: str,
        pds_url: str,
        sdk_client_factory: Callable[[str], object] = _default_sdk_factory,
    ):
        self.handle = handle
        self.app_password = app_password
        self.did = did
        self.pds_url = pds_url
        self._sdk_client_factory = sdk_client_factory
        self._sdk: Optional[object] = None
        self._logged_in = False

    @classmethod
    def from_env(
        cls,
        sdk_client_factory: Optional[Callable[[str], object]] = None,
    ) -> "AtprotoClient":
        """Construct from ATPROTO_* env vars. Used by the CLI/publisher so call
        sites do not pass credentials around.

        The sdk_client_factory default resolves at call time via a module-level
        lookup so monkeypatch on the module attribute reaches this path during
        tests.
        """
        if sdk_client_factory is None:
            import app.integrations.atproto.client as _self_mod

            sdk_client_factory = _self_mod._default_sdk_factory

        required = {
            "ATPROTO_HANDLE": os.getenv("ATPROTO_HANDLE"),
            "ATPROTO_APP_PASSWORD": os.getenv("ATPROTO_APP_PASSWORD"),
            "ATPROTO_DID": os.getenv("ATPROTO_DID"),
            "ATPROTO_PDS_URL": os.getenv("ATPROTO_PDS_URL"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(f"missing atproto env vars: {', '.join(missing)}")

        return cls(
            handle=required["ATPROTO_HANDLE"],
            app_password=required["ATPROTO_APP_PASSWORD"],
            did=required["ATPROTO_DID"],
            pds_url=required["ATPROTO_PDS_URL"],
            sdk_client_factory=sdk_client_factory,
        )

    @property
    def sdk(self):
        if self._sdk is None:
            self._sdk = self._sdk_client_factory(self.pds_url)
        return self._sdk

    def login(self):
        """Authenticate with handle + app password. Idempotent within an instance."""
        self.sdk.login(self.handle, self.app_password)
        self._logged_in = True

    def _ensure_session(self):
        if not self._logged_in:
            self.login()

    def put_record(self, collection: str, rkey: str, record: dict):
        """Upsert a record. Returns the SDK's response object with .uri and .cid.

        Using put_record (upsert) over create_record means republish is automatic:
        first call creates, subsequent calls update at the same at:// URI.
        """
        self._ensure_session()
        from atproto import models

        return self.sdk.com.atproto.repo.put_record(
            models.ComAtprotoRepoPutRecord.Data(
                repo=self.did,
                collection=collection,
                rkey=rkey,
                record=record,
            )
        )

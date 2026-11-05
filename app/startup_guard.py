"""Refuse to start when test-only switches are set on a deployed server.

TESTING turns off rate limiting. E2E_TESTING also turns off the HTTPS redirect and the
signup and upload rate limits, and opens /test-verify-user, which marks any email as
verified. Set on Fly by mistake (for example with `fly secrets set`), they would weaken
production with no warning. Failing at startup makes the deploy fail its health check,
so the previous release keeps running.
"""

from collections.abc import Mapping
import os

TEST_SWITCHES = ("TESTING", "E2E_TESTING")


def _is_on(value: str | None) -> bool:
    return (value or "").strip().lower() in ("true", "1", "yes")


def check_test_switches(env: Mapping[str, str] | None = None) -> None:
    """Raise RuntimeError if a test switch is on in a deployed environment."""
    env = os.environ if env is None else env
    deployed = bool(env.get("FLY_APP_NAME")) or env.get("ENVIRONMENT") == "production"
    if not deployed:
        return
    enabled = [name for name in TEST_SWITCHES if _is_on(env.get(name))]
    if enabled:
        raise RuntimeError(
            f"Test switches {', '.join(enabled)} are set on a deployed server. Refusing to start."
        )

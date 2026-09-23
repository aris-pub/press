"""Sentry configuration: event filtering and abuse pattern reporting.

Provides the before_send filter for Sentry event processing and helper functions
to report abuse patterns (rate limit hits, rapid uploads, storage thresholds)
via sentry_sdk.capture_message.

Note on cost: capture_message bills as an error in Sentry whatever level it
carries, so everything reported here counts against the error quota.
"""

from dataclasses import dataclass, field
import time

import sentry_sdk

# Reporting one event per blocked request consumed a full month of error quota in
# two weeks (2026-09). A public site is swept continuously by scanners probing for
# /.env, /settings.py, /stripe.yaml and similar, and each blocked request became
# its own billable event. Reporting once per IP per day keeps the useful signal,
# which is that an IP is scanning and how hard, at a few hundred events a month:
# roughly 15 scanning IPs over a fortnight is 210 events at this interval against
# more than 5,000 at one per request.
RATE_LIMIT_REPORT_INTERVAL_SECONDS = 86_400

# Cap on tracked IPs so a distributed sweep cannot grow the map without bound.
_MAX_TRACKED_IPS = 10_000


@dataclass
class _BlockedWindow:
    """What one IP has done since it was last reported to Sentry."""

    opened_at: float
    blocked: int = 0
    paths: set[str] = field(default_factory=set)


# Process-local. Each worker keeps its own map, and a restart clears it, so the
# real ceiling is one event per IP per day per worker per restart. That is still
# three orders of magnitude below one per request.
_blocked_windows: dict[str, _BlockedWindow] = {}


def reset_rate_limit_reporting() -> None:
    """Clear the suppression state. For tests."""
    _blocked_windows.clear()


def _prune_blocked_windows(now: float) -> None:
    """Drop expired entries, and if still at the cap, the oldest half."""
    if len(_blocked_windows) < _MAX_TRACKED_IPS:
        return
    for ip in [
        ip
        for ip, window in _blocked_windows.items()
        if now - window.opened_at >= RATE_LIMIT_REPORT_INTERVAL_SECONDS
    ]:
        del _blocked_windows[ip]
    if len(_blocked_windows) >= _MAX_TRACKED_IPS:
        by_age = sorted(_blocked_windows, key=lambda ip: _blocked_windows[ip].opened_at)
        for ip in by_age[: len(by_age) // 2]:
            del _blocked_windows[ip]


def before_send(event: dict, hint: dict, environment: str = "production") -> dict | None:
    """Filter Sentry events before sending.

    Drops events from the test environment and filters out 404 errors
    which are expected noise, not actionable errors.
    """
    if environment == "testing":
        return None

    # Filter out 404 errors (expected behavior, not bugs)
    if event.get("level") == "error":
        for exc in event.get("exception", {}).get("values", []):
            exc_value = str(exc.get("value", ""))
            if "404" in exc_value:
                return None

    return event


def report_rate_limit_hit(
    client_ip: str, path: str, method: str, now: float | None = None
) -> None:
    """Report an IP hitting rate limits, at most once per RATE_LIMIT_REPORT_INTERVAL_SECONDS.

    Hits inside an open window are counted, not sent. The next event that IP earns
    carries the totals for the window that just closed, so the volume is visible
    without paying for every request. Every hit is still logged by the rate-limit
    middleware regardless.
    """
    now = time.time() if now is None else now
    window = _blocked_windows.get(client_ip)

    if window is not None and now - window.opened_at < RATE_LIMIT_REPORT_INTERVAL_SECONDS:
        window.blocked += 1
        window.paths.add(path)
        return

    _prune_blocked_windows(now)
    _blocked_windows[client_ip] = _BlockedWindow(opened_at=now, blocked=1, paths={path})

    context: dict = {"client_ip": client_ip, "latest_path": path, "latest_method": method}
    if window is not None:
        context["blocked_since_last_report"] = window.blocked
        context["distinct_paths_since_last_report"] = len(window.paths)
        context["paths_sample"] = sorted(window.paths)[:20]
        context["window_seconds"] = round(now - window.opened_at)

    sentry_sdk.set_context("rate_limit_abuse", context)
    # The fingerprint is the IP alone, so one issue tracks one scanner across every
    # path it tries. The message says "latest" because the path in an issue title is
    # only the first one seen, which reads as if the IP hit one path repeatedly.
    sentry_sdk.capture_message(
        f"Rate limit hit: {client_ip} (latest: {method} {path})",
        level="warning",
        fingerprint=["rate-limit-abuse", client_ip],
    )


def report_rapid_uploads(user_id: str, upload_count: int, window_seconds: int) -> None:
    """Report a user uploading at a rapid rate to Sentry for abuse monitoring."""
    sentry_sdk.set_user({"id": user_id})
    sentry_sdk.set_context(
        "rapid_uploads",
        {
            "upload_count": upload_count,
            "window_seconds": window_seconds,
        },
    )
    sentry_sdk.capture_message(
        f"Rapid upload rate limit: user {user_id} hit {upload_count} uploads in {window_seconds}s",
        level="warning",
        fingerprint=["rapid-uploads", user_id],
    )


def report_storage_threshold(user_id: str, total_bytes: int, scroll_count: int) -> None:
    """Report a user exceeding storage consumption thresholds."""
    total_mb = total_bytes / (1024 * 1024)
    sentry_sdk.set_user({"id": user_id})
    sentry_sdk.set_context(
        "storage_threshold",
        {
            "total_bytes": total_bytes,
            "total_mb": round(total_mb, 2),
            "scroll_count": scroll_count,
        },
    )
    sentry_sdk.capture_message(
        f"Storage threshold: user {user_id} using {total_mb:.1f} MB across {scroll_count} scrolls",
        level="warning",
        fingerprint=["storage-threshold", user_id],
    )

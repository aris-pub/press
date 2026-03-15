"""Sentry configuration: event filtering and abuse pattern reporting.

Provides the before_send filter for Sentry event processing and helper functions
to report abuse patterns (rate limit hits, rapid uploads, storage thresholds)
via sentry_sdk.capture_message.
"""

import sentry_sdk


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


def report_rate_limit_hit(client_ip: str, path: str, method: str) -> None:
    """Report an IP hitting rate limits to Sentry for abuse monitoring."""
    sentry_sdk.set_context(
        "rate_limit_abuse",
        {"client_ip": client_ip, "path": path, "method": method},
    )
    sentry_sdk.capture_message(
        f"Rate limit hit: {client_ip} on {method} {path}",
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

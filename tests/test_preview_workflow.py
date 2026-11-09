"""PR preview apps must not get production secrets. See docs/DEPLOYMENT.md, "Environments"."""

from pathlib import Path

PREVIEW_WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "preview.yml"

PRODUCTION_ONLY = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ENDPOINT_URL_S3",
    "BUCKET_NAME",
    "ORCID_CLIENT_ID",
    "ORCID_CLIENT_SECRET",
    "RESEND_API_KEY",
    "ZENODO_API_TOKEN",
    "SENTRY_DSN",
    "TURNSTILE_SECRET_KEY",
    "ATPROTO_APP_PASSWORD",
]


def test_preview_apps_get_no_production_secrets():
    text = PREVIEW_WORKFLOW.read_text()
    leaked = [name for name in PRODUCTION_ONLY if name in text]
    assert leaked == []

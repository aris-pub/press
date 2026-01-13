from functools import lru_cache
import os


@lru_cache()
def get_base_url() -> str:
    """Get the base URL for the application."""
    base_url = os.getenv("BASE_URL", "https://scroll.press")

    # Validation: ensure base_url is a valid URL without trailing slash
    if not base_url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid BASE_URL: {base_url}. Must start with http:// or https://")

    # Remove trailing slash if present
    base_url = base_url.rstrip("/")

    return base_url

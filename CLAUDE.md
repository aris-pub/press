# Press

Python web app (FastAPI + Jinja2 + Playwright for E2E).

## Testing

Run **only** the unit tests relevant to your changes:

```
uv run pytest -m "not e2e" tests/path/to/test_file.py
```

Do NOT run `just test`, `uv run pytest` with no arguments, or any E2E/playwright tests. E2E tests require a running server and are validated by CI after you push.

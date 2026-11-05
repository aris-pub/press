"""The e2e suite must launch the browser CI asks for.

CI's mobile-webkit job passes `--browser webkit`, but every test used to call
`p.chromium.launch`, so WebKit never ran. Marked desktop and mobile so it runs in the
desktop, mobile-webkit and mobile-chromium jobs.
"""

from playwright.async_api import async_playwright
import pytest

from tests.e2e.conftest import launch_browser

pytestmark = [pytest.mark.e2e, pytest.mark.desktop, pytest.mark.mobile]


def _requested(config) -> str:
    browsers = config.getoption("browser") or []
    return browsers[0] if browsers else "chromium"


async def test_launches_the_browser_given_on_the_command_line(request):
    async with async_playwright() as p:
        browser = await launch_browser(p)
        try:
            assert browser.browser_type.name == _requested(request.config)
        finally:
            await browser.close()


async def test_no_test_file_hardcodes_chromium():
    """Any direct `p.chromium.launch` would silently ignore `--browser` again."""
    from pathlib import Path

    offenders = [
        path.name
        for path in Path(__file__).parent.glob("*.py")
        if path.name not in {"test_browser_selection.py", "conftest_new.py", "conftest_simple.py"}
        and "chromium.launch(" in path.read_text()
        and path.name != "conftest.py"
    ]
    assert offenders == []

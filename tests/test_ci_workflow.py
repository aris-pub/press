"""The browser-test CI jobs must download almost nothing from Ubuntu's mirror.

Every job used to run `playwright install-deps`, which downloads about 181 packages
from Ubuntu's mirror. On 2026-11-05 seven jobs stalled there for 33 to 57 minutes. The
jobs now run inside Playwright's own image, which already has the browsers and every
library they need. The one package added on top is libmagic1, which Press itself needs.
"""

from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
E2E = WORKFLOW["jobs"]["e2e"]


def _locked_playwright_version() -> str:
    lock = (ROOT / "uv.lock").read_text()
    match = re.search(r'name = "playwright"\nversion = "([^"]+)"', lock)
    assert match, "playwright not found in uv.lock"
    return match.group(1)


def test_e2e_runs_in_the_playwright_image_matching_the_locked_version():
    """The image's browsers must be the builds the locked Python package expects."""
    image = E2E["container"]["image"]
    assert image == f"mcr.microsoft.com/playwright:v{_locked_playwright_version()}-noble"


def _apt_packages(command: str) -> list[str]:
    packages = []
    for line in command.splitlines():
        if "apt-get install" in line:
            words = line.split("apt-get install", 1)[1].split()
            packages += [w for w in words if not w.startswith("-") and w not in ("&&", "\\")]
    return packages


def test_e2e_never_installs_browsers():
    for step in E2E["steps"]:
        assert "playwright install" not in step.get("run", ""), step.get("name")


def test_e2e_installs_only_libmagic_from_the_mirror():
    """python-magic needs libmagic, which the Playwright image lacks (run 42126413342).

    One small package is the only download allowed from Ubuntu's mirror.
    """
    installed = [p for step in E2E["steps"] for p in _apt_packages(step.get("run", ""))]
    assert installed == ["libmagic1"]


def test_libmagic_is_installed_before_the_server_starts():
    names = [step.get("name", "") for step in E2E["steps"]]
    install = next(i for i, step in enumerate(E2E["steps"]) if "libmagic1" in step.get("run", ""))
    assert install < names.index("Start server")


def test_e2e_jobs_have_a_time_limit():
    assert 0 < E2E["timeout-minutes"] <= 30


def test_e2e_reaches_postgres_by_service_name():
    """Inside a container job, services are reached by name, not localhost."""
    urls = []
    for step in E2E["steps"]:
        url = step.get("env", {}).get("DATABASE_URL")
        if url:
            urls.append(url)
    assert urls
    for url in urls:
        assert "@postgres:5432/" in url, url

"""Inject the latest CHANGELOG.md entry into roadmap.html between markers."""

import re
import sys


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <version>")
        sys.exit(1)

    version = sys.argv[1]

    with open("CHANGELOG.md") as f:
        changelog = f.read()

    pattern = rf"^## \[{re.escape(version)}\].*?\n(.*?)(?=^## \[|\Z)"
    match = re.search(pattern, changelog, re.MULTILINE | re.DOTALL)
    if not match:
        print(f"Warning: no changelog entry found for {version}")
        sys.exit(0)

    entry = match.group(1).strip()

    # Build HTML from markdown
    lines = []
    lines.append("    <section>")
    lines.append(
        '      <h2><svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" style="display: inline; vertical-align: middle; '
        'margin-right: 0.5rem; color: #f59e0b;"><path d="M12 2v4M12 18v4M4.93 '
        "4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83"
        'M16.24 7.76l2.83-2.83"/></svg>'
        f"Recent Changes (v{version})</h2>"
    )

    in_list = False
    for line in entry.splitlines():
        if line.startswith("### "):
            if in_list:
                lines.append("      </ul>")
                in_list = False
            lines.append(f"      <h3>{line[4:]}</h3>")
            lines.append("      <ul>")
            in_list = True
        elif line.startswith("- "):
            lines.append(f"        <li>{line[2:]}</li>")

    if in_list:
        lines.append("      </ul>")

    lines.append(
        '      <p><a href="https://github.com/aris-pub/press/releases" '
        'class="page-link">Full changelog on GitHub</a></p>'
    )
    lines.append("    </section>")

    html_block = "\n".join(lines)

    with open("app/templates/roadmap.html") as f:
        content = f.read()

    content = re.sub(
        r"    <!-- CHANGELOG_START -->.*?    <!-- CHANGELOG_END -->",
        f"    <!-- CHANGELOG_START -->\n{html_block}\n    <!-- CHANGELOG_END -->",
        content,
        flags=re.DOTALL,
    )

    with open("app/templates/roadmap.html", "w") as f:
        f.write(content)

    print(f"==> Roadmap updated with v{version} changes")


if __name__ == "__main__":
    main()

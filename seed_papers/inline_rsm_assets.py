#!/usr/bin/env python3
"""Inline all RSM static assets into the HTML file to make it self-contained."""

import re
from pathlib import Path

def read_file(path, binary=False):
    """Read file as text or binary."""
    mode = 'rb' if binary else 'r'
    with open(path, mode, encoding=None if binary else 'utf-8') as f:
        return f.read()

def inline_rsm_assets(html_content, static_dir):
    """Replace /static/ references with inline content."""

    # Inline CSS files
    def replace_css(match):
        filename = match.group(1)
        css_path = static_dir / filename

        if not css_path.exists():
            print(f"Warning: CSS not found: {css_path}")
            return match.group(0)

        css_content = read_file(css_path)
        return f'<style type="text/css">\n{css_content}\n</style>'

    # Inline regular JS files (not modules)
    def replace_js(match):
        filename = match.group(1) + '.js'
        js_path = static_dir / filename

        if not js_path.exists():
            print(f"Warning: JS not found: {js_path}")
            return match.group(0)

        js_content = read_file(js_path)
        return f'<script>\n{js_content}\n</script>'

    # Replace module import with standalone bundle
    def replace_module_import(match):
        # Use the standalone bundle instead of module imports
        standalone_path = static_dir / 'rsm-standalone.js'
        if not standalone_path.exists():
            print(f"Warning: Standalone bundle not found: {standalone_path}")
            return match.group(0)

        js_content = read_file(standalone_path)
        # Replace the entire module script with standalone bundle
        return f'''<script>
{js_content}
// Initialize RSM on load
window.addEventListener('load', (ev) => {{
  if (typeof RSM !== 'undefined' && RSM.onload) {{
    RSM.onload();
  }}
}});
</script>'''

    # Replace CSS links
    html_content = re.sub(
        r'<link[^>]*href="/static/([^"]+\.css)"[^>]*/?>',
        replace_css,
        html_content
    )

    # Replace regular script tags (jQuery, tooltipster)
    html_content = re.sub(
        r'<script[^>]*src="/static/(jquery-3\.6\.0|tooltipster\.bundle)\.js"[^>]*></script>',
        replace_js,
        html_content
    )

    # Replace the module script that imports onload.js
    html_content = re.sub(
        r'<script type="module">.*?from\s+[\'"]\/static\/onload\.js[\'"].*?<\/script>',
        replace_module_import,
        html_content,
        flags=re.DOTALL
    )

    return html_content

def main():
    # Paths
    html_file = Path('/Users/leo.torres/aris/press/seed_papers/damped_oscillators.html')
    static_dir = Path('/Users/leo.torres/aris/rsm/rsm/static')
    output_file = Path('/Users/leo.torres/aris/press/seed_papers/damped_oscillators_inlined.html')

    print("Reading RSM HTML file...")
    html_content = read_file(html_file)

    print("Inlining RSM static assets...")
    html_content = inline_rsm_assets(html_content, static_dir)

    print(f"Writing self-contained HTML to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print("Done!")
    print(f"Output size: {output_file.stat().st_size / 1024:.1f} KB")

if __name__ == '__main__':
    main()

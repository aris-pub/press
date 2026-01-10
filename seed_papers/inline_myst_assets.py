#!/usr/bin/env python3
"""Inline all _static assets into the MyST HTML file to make it self-contained."""

import re
import base64
from pathlib import Path
from urllib.parse import urlparse

def read_file(path, binary=False):
    """Read file as text or binary."""
    mode = 'rb' if binary else 'r'
    with open(path, mode) as f:
        return f.read()

def inline_css(html_content, static_dir):
    """Replace CSS link tags with inline style tags."""

    def replace_css(match):
        href = match.group(1)
        # Remove query string
        href_clean = href.split('?')[0]
        css_path = static_dir / href_clean

        if not css_path.exists():
            print(f"Warning: CSS not found: {css_path}")
            return match.group(0)

        css_content = read_file(css_path)

        # Handle font references in CSS (pass the CSS file's directory as base)
        css_dir = css_path.parent
        css_content = inline_fonts_in_css(css_content, css_dir, static_dir)

        return f'<style type="text/css">\n{css_content}\n</style>'

    # Match link tags with _static CSS files
    pattern = r'<link[^>]*href="_static/([^"]+\.css[^"]*)"[^>]*>'
    return re.sub(pattern, replace_css, html_content)

def inline_fonts_in_css(css_content, css_dir, static_dir):
    """Convert font file references to data URIs in CSS."""

    def replace_font(match):
        font_path_str = match.group(1)
        # Remove quotes if present
        font_path_str = font_path_str.strip('\'"')

        # Resolve relative path from CSS file location
        if font_path_str.startswith('../'):
            # Resolve relative to CSS file directory
            font_path = (css_dir / font_path_str).resolve()
        else:
            # Absolute path from static dir
            font_path = static_dir / font_path_str

        if not font_path.exists():
            print(f"Warning: Font not found: {font_path}")
            return match.group(0)

        font_data = read_file(font_path, binary=True)
        font_b64 = base64.b64encode(font_data).decode('utf-8')

        # Determine MIME type based on extension
        ext = font_path.suffix.lower()
        mime_types = {
            '.woff2': 'font/woff2',
            '.woff': 'font/woff',
            '.ttf': 'font/ttf',
            '.otf': 'font/otf'
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')

        return f'url(data:{mime_type};base64,{font_b64})'

    # Match url() references to font files
    pattern = r'url\(([^)]+\.(?:woff2?|ttf|otf))\)'
    return re.sub(pattern, replace_font, css_content)

def inline_js(html_content, static_dir):
    """Replace script src tags with inline script tags."""

    def replace_js(match):
        src = match.group(1)
        # Remove query string
        src_clean = src.split('?')[0]
        js_path = static_dir / src_clean

        if not js_path.exists():
            print(f"Warning: JS not found: {js_path}")
            return match.group(0)

        js_content = read_file(js_path)
        return f'<script>\n{js_content}\n</script>'

    # Match script tags with _static JS files
    pattern = r'<script[^>]*src="_static/([^"]+\.js[^"]*)"[^>]*></script>'
    return re.sub(pattern, replace_js, html_content)

def remove_preload_links(html_content):
    """Remove preload link tags for _static resources since they're now inlined."""
    pattern = r'<link[^>]*rel="preload"[^>]*href="_static/[^"]*"[^>]*/>\s*'
    return re.sub(pattern, '', html_content)

def add_mathjax(html_content):
    """Add MathJax CDN script to head for math rendering."""

    # First, remove any existing MathJax configuration
    html_content = re.sub(
        r'<script>\s*MathJax\s*=\s*\{.*?</script>\s*<script[^>]*mathjax[^>]*></script>',
        '',
        html_content,
        flags=re.DOTALL | re.IGNORECASE
    )

    mathjax_script = '''<script>
  MathJax = {
    tex: {
      inlineMath: [['$', '$']],
      displayMath: [['$$', '$$'], ['\\[', '\\]']]
    },
    startup: {
      ready: () => {
        MathJax.startup.defaultReady();
        MathJax.startup.promise.then(() => {
          // Initial typesetting of all content including summary elements
          MathJax.typesetPromise();

          // Re-typeset when details elements are opened
          document.addEventListener('toggle', (event) => {
            if (event.target.tagName === 'DETAILS' && event.target.hasAttribute('open')) {
              MathJax.typesetPromise([event.target]);
            }
          }, true);
        });
      }
    }
  };
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>'''

    # Insert before closing </head> tag
    return html_content.replace('</head>', f'{mathjax_script}\n</head>')

def main():
    # Paths
    html_file = Path('/Users/leo.torres/aris/press/seed_papers/graph_traversal_myst.html')
    static_dir = Path('/Users/leo.torres/aris/press/seed_papers/myst_build/_build/_static')
    output_file = Path('/Users/leo.torres/aris/press/seed_papers/graph_traversal_myst_inlined.html')

    print("Reading HTML file...")
    html_content = read_file(html_file)

    print("Inlining CSS files...")
    html_content = inline_css(html_content, static_dir)

    print("Inlining JS files...")
    html_content = inline_js(html_content, static_dir)

    print("Removing preload hints...")
    html_content = remove_preload_links(html_content)

    print("Adding MathJax for math rendering...")
    html_content = add_mathjax(html_content)

    print(f"Writing self-contained HTML to {output_file}...")
    with open(output_file, 'w') as f:
        f.write(html_content)

    print("Done!")
    print(f"Output size: {output_file.stat().st_size / 1024:.1f} KB")

if __name__ == '__main__':
    main()

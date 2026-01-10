# MyST configuration for building graph traversal paper
project = 'Graph Traversal Algorithms'
author = 'Dorothy Gale, Huckleberry Finn'
release = '2025-01-05'

extensions = [
    'myst_parser',
    'sphinx.ext.mathjax',
    'sphinx_design',
    'sphinx_togglebutton',
]

# MyST configuration
myst_enable_extensions = [
    "colon_fence",  # ::: admonitions
    "deflist",
    "fieldlist",
    "html_admonition",
    "html_image",
    "substitution",
    "tasklist",
]

# Allow executable code cells (even if not executing in this build)
myst_fence_as_directive = ["code-cell"]

# HTML output options
html_theme = 'sphinx_book_theme'
html_title = 'Graph Traversal Algorithms: BFS and DFS'
html_static_path = []
templates_path = []

# Book theme options for clean academic look
html_theme_options = {
    "show_toc_level": 2,
    "repository_url": "https://github.com/aris/press",
    "use_repository_button": False,
    "use_edit_page_button": False,
    "use_download_button": False,
}

# Disable unnecessary Sphinx features
html_use_index = False
html_use_modindex = False
html_copy_source = False
html_show_sourcelink = False
html_show_sphinx = False

# MathJax configuration
mathjax_path = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js'

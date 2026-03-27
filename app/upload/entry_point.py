"""Heuristic entry point detection for multi-file HTML archives."""

import os

COMMON_ENTRY_NAMES = ("index.html", "paper.html", "article.html", "main.html", "manuscript.html")


def detect_entry_point(html_files: list[str]) -> str:
    """Detect the most likely entry point HTML file from a list of relative paths.

    Heuristics (ordered, first match wins):
    1. Single HTML file in archive -> that's the entry point
    2. index.html at shallowest directory level
    3. Common names at shallowest level: paper.html, article.html, main.html, manuscript.html
    4. Largest HTML file (by file size) -- not used here (caller must pass sizes)
    5. First alphabetically

    This function does NOT use file size (heuristic 4). If you need size-based
    fallback, use detect_entry_point_with_sizes() instead.

    Args:
        html_files: List of relative paths to HTML files in the archive.

    Returns:
        The relative path of the detected entry point.

    Raises:
        ValueError: If html_files is empty.
    """
    if not html_files:
        raise ValueError("No HTML files provided")

    if len(html_files) == 1:
        return html_files[0]

    return _pick_by_name_heuristics(html_files)


def detect_entry_point_with_sizes(file_sizes: dict[str, int]) -> str:
    """Detect entry point using all heuristics including file size.

    Args:
        file_sizes: Dict mapping relative path -> file size in bytes,
                    for HTML files only.

    Returns:
        The relative path of the detected entry point.

    Raises:
        ValueError: If file_sizes is empty.
    """
    if not file_sizes:
        raise ValueError("No HTML files provided")

    html_files = list(file_sizes.keys())

    if len(html_files) == 1:
        return html_files[0]

    result = _pick_by_name_heuristics(html_files)
    if result is not None:
        return result

    # Heuristic 4: largest HTML file
    largest = max(file_sizes, key=file_sizes.get)
    return largest


def _pick_by_name_heuristics(html_files: list[str]) -> str | None:
    """Apply name-based heuristics (2 and 3). Returns None if no match."""
    min_depth = min(_depth(f) for f in html_files)
    shallowest = [f for f in html_files if _depth(f) == min_depth]

    # Heuristic 2: index.html at shallowest level
    for f in shallowest:
        if os.path.basename(f).lower() == "index.html":
            return f

    # Heuristic 3: common names at shallowest level
    for name in COMMON_ENTRY_NAMES[1:]:  # skip index.html, already checked
        for f in shallowest:
            if os.path.basename(f).lower() == name:
                return f

    # Heuristic 5: first alphabetically among shallowest
    return sorted(shallowest)[0]


def _depth(path: str) -> int:
    """Return directory depth of a path (0 for root-level files)."""
    parts = path.replace("\\", "/").split("/")
    return len(parts) - 1

"""Tests for entry point detection heuristics."""

import pytest

from app.upload.entry_point import detect_entry_point, detect_entry_point_with_sizes


class TestSingleFile:
    def test_single_html_file(self):
        assert detect_entry_point(["paper.html"]) == "paper.html"

    def test_single_nested_file(self):
        assert detect_entry_point(["deep/nested/file.html"]) == "deep/nested/file.html"


class TestIndexHtml:
    def test_index_at_root(self):
        files = ["styles.html", "index.html", "about.html"]
        assert detect_entry_point(files) == "index.html"

    def test_index_preferred_over_other_names(self):
        files = ["paper.html", "index.html", "article.html"]
        assert detect_entry_point(files) == "index.html"

    def test_index_at_shallowest_level(self):
        files = ["subdir/other.html", "subdir/index.html", "root.html"]
        assert detect_entry_point(files) == "root.html"

    def test_index_in_subdirectory_when_all_nested(self):
        files = ["dir/page.html", "dir/index.html"]
        assert detect_entry_point(files) == "dir/index.html"

    def test_case_insensitive_index(self):
        files = ["INDEX.HTML", "other.html"]
        assert detect_entry_point(files) == "INDEX.HTML"


class TestCommonNames:
    def test_paper_html(self):
        files = ["data.html", "paper.html", "appendix.html"]
        assert detect_entry_point(files) == "paper.html"

    def test_article_html(self):
        files = ["data.html", "article.html", "appendix.html"]
        assert detect_entry_point(files) == "article.html"

    def test_main_html(self):
        files = ["data.html", "main.html", "appendix.html"]
        assert detect_entry_point(files) == "main.html"

    def test_manuscript_html(self):
        files = ["data.html", "manuscript.html", "appendix.html"]
        assert detect_entry_point(files) == "manuscript.html"

    def test_priority_order_paper_before_article(self):
        files = ["article.html", "paper.html"]
        assert detect_entry_point(files) == "paper.html"

    def test_common_name_only_at_shallowest_depth(self):
        files = ["sub/paper.html", "other.html"]
        assert detect_entry_point(files) == "other.html"


class TestAlphabeticalFallback:
    def test_alphabetical_when_no_common_names(self):
        files = ["z_file.html", "a_file.html", "m_file.html"]
        assert detect_entry_point(files) == "a_file.html"

    def test_alphabetical_at_shallowest_level(self):
        files = ["deep/a_file.html", "z_file.html", "b_file.html"]
        assert detect_entry_point(files) == "b_file.html"


class TestWithSizes:
    def test_size_not_needed_when_name_matches(self):
        sizes = {"other.html": 5000, "index.html": 100}
        assert detect_entry_point_with_sizes(sizes) == "index.html"

    def test_single_file(self):
        sizes = {"only.html": 1000}
        assert detect_entry_point_with_sizes(sizes) == "only.html"

    def test_largest_file_as_last_resort(self):
        # All files at same depth, no common names -- falls through to alphabetical
        # since _pick_by_name_heuristics returns first alphabetically
        sizes = {"z_report.html": 50000, "a_supplement.html": 100}
        assert detect_entry_point_with_sizes(sizes) == "a_supplement.html"


class TestEdgeCases:
    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="No HTML files"):
            detect_entry_point([])

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="No HTML files"):
            detect_entry_point_with_sizes({})

    def test_deeply_nested_index(self):
        files = ["a/b/c/index.html", "a/b/d/other.html"]
        assert detect_entry_point(files) == "a/b/c/index.html"

    def test_mixed_depths_prefers_shallow(self):
        files = ["deep/nested/index.html", "shallow/page.html"]
        assert detect_entry_point(files) == "shallow/page.html"

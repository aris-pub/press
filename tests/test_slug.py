"""Tests for slug utility functions."""

import pytest

from app.utils.slug import generate_unique_slug, slugify_title


class TestSlugifyTitle:
    def test_basic_title(self):
        assert slugify_title("Machine Learning Approaches") == "machine-learning-approaches"

    def test_removes_stop_words(self):
        assert slugify_title("The Impact of AI on the Future") == "impact-ai-future"

    def test_all_stop_words_removed(self):
        for word in [
            "the",
            "a",
            "an",
            "of",
            "for",
            "in",
            "on",
            "with",
            "and",
            "or",
            "to",
            "is",
            "by",
        ]:
            title = f"Something {word} Else"
            result = slugify_title(title)
            assert word not in result.split("-"), f"Stop word '{word}' not removed"

    def test_special_characters_stripped(self):
        assert slugify_title("What's New? A Review!") == "whats-new-review"

    def test_unicode_normalization(self):
        assert slugify_title("Résumé of Naïve Bayesian") == "resume-naive-bayesian"

    def test_truncation_on_word_boundary(self):
        long_title = "Comprehensive Analysis of Very Long Academic Paper Titles That Exceed the Maximum Character Limit"
        result = slugify_title(long_title)
        assert len(result) <= 60
        assert not result.endswith("-")

    def test_truncation_does_not_split_words(self):
        # Build a title where naive truncation at 60 would cut a word
        title = "abcdefghij " * 7  # 77 chars of words
        result = slugify_title(title)
        assert len(result) <= 60
        for part in result.split("-"):
            assert part == "abcdefghij"

    def test_empty_after_stop_word_removal(self):
        result = slugify_title("The A An Of")
        assert result == ""

    def test_numbers_preserved(self):
        assert slugify_title("COVID 19 Vaccine Trials 2024") == "covid-19-vaccine-trials-2024"

    def test_hyphens_and_dashes(self):
        assert slugify_title("Self-Supervised Learning") == "self-supervised-learning"

    def test_multiple_spaces(self):
        assert slugify_title("Too   Many    Spaces") == "too-many-spaces"

    def test_leading_trailing_whitespace(self):
        assert slugify_title("  Trimmed Title  ") == "trimmed-title"

    def test_mixed_case(self):
        assert slugify_title("UPPER lower MiXeD") == "upper-lower-mixed"

    def test_only_special_chars(self):
        assert slugify_title("!@#$%^&*()") == ""

    def test_accented_stop_words_still_removed(self):
        # "the" after normalization should still be caught
        assert slugify_title("The café in Paris") == "cafe-paris"


@pytest.mark.skipif(
    not hasattr(__import__("app.models.scroll", fromlist=["Scroll"]).Scroll, "slug"),
    reason="Scroll.slug column not yet added (prs-8na)",
)
class TestGenerateUniqueSlug:
    @pytest.mark.asyncio
    async def test_basic_unique_slug(self, test_db):
        slug = await generate_unique_slug(test_db, "Machine Learning Survey", 2024)
        assert slug == "machine-learning-survey"

    @pytest.mark.asyncio
    async def test_collision_appends_suffix(self, test_db, test_user, test_subject):
        from app.models.scroll import Scroll

        # Create a scroll with the slug that will be generated
        scroll = Scroll(
            title="Existing",
            authors="Author",
            abstract="Abstract",
            html_content="<p>Content</p>",
            license="cc-by-4.0",
            status="published",
            slug="machine-learning-survey",
            publication_year=2024,
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()

        slug = await generate_unique_slug(test_db, "Machine Learning Survey", 2024)
        assert slug == "machine-learning-survey-2"

    @pytest.mark.asyncio
    async def test_multiple_collisions(self, test_db, test_user, test_subject):
        from app.models.scroll import Scroll

        # Create scrolls with slug and slug-2
        for s in ["machine-learning-survey", "machine-learning-survey-2"]:
            scroll = Scroll(
                title="Existing",
                authors="Author",
                abstract="Abstract",
                html_content="<p>Content</p>",
                license="cc-by-4.0",
                status="published",
                slug=s,
                publication_year=2024,
                user_id=test_user.id,
                subject_id=test_subject.id,
            )
            test_db.add(scroll)
        await test_db.commit()

        slug = await generate_unique_slug(test_db, "Machine Learning Survey", 2024)
        assert slug == "machine-learning-survey-3"

    @pytest.mark.asyncio
    async def test_same_slug_different_year_no_collision(self, test_db, test_user, test_subject):
        from app.models.scroll import Scroll

        scroll = Scroll(
            title="Existing",
            authors="Author",
            abstract="Abstract",
            html_content="<p>Content</p>",
            license="cc-by-4.0",
            status="published",
            slug="machine-learning-survey",
            publication_year=2023,
            user_id=test_user.id,
            subject_id=test_subject.id,
        )
        test_db.add(scroll)
        await test_db.commit()

        slug = await generate_unique_slug(test_db, "Machine Learning Survey", 2024)
        assert slug == "machine-learning-survey"

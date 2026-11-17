"""Math in abstracts is marked for MathJax on Press pages (prs-58a).

abstract_html escapes the abstract and wraps only real math in <span class="math-tex">
as \\(...\\) or \\[...\\], so MathJax typesets those spans and nothing else. A dollar
sign used for money stays text.
"""

from app.abstract_math import abstract_html

INLINE = '<span class="math-tex">\\({}\\)</span>'
DISPLAY = '<span class="math-tex math-display">\\[{}\\]</span>'


class TestFindsMath:
    def test_inline_dollars(self):
        assert abstract_html("with $n$ points") == f"with {INLINE.format('n')} points"

    def test_inline_with_commands(self):
        html = abstract_html(r"distortion $O(\log n)$.")
        expected = INLINE.format(r"O(\log n)")
        assert html == f"distortion {expected}."

    def test_display_dollars(self):
        assert abstract_html("see $$x^2$$ here") == f"see {DISPLAY.format('x^2')} here"

    def test_parenthesis_delimiters(self):
        assert abstract_html(r"a \(x+y\) b") == f"a {INLINE.format('x+y')} b"

    def test_bracket_delimiters(self):
        assert abstract_html(r"a \[x+y\] b") == f"a {DISPLAY.format('x+y')} b"

    def test_several_in_one_abstract(self):
        html = abstract_html(r"$\log n/\log\log n$ and $O(\sqrt{\log n})$")
        assert html.count('class="math-tex"') == 2

    def test_escaped_dollar_is_text(self):
        assert abstract_html(r"costs \$5 and $x$") == f"costs $5 and {INLINE.format('x')}"


class TestMoneyStaysText:
    def test_two_prices(self):
        assert abstract_html("between $5 and $10 per run") == "between $5 and $10 per run"

    def test_one_price(self):
        assert abstract_html("costs $5.") == "costs $5."

    def test_space_after_opening(self):
        assert abstract_html("a $ x$ b") == "a $ x$ b"

    def test_space_before_closing(self):
        assert abstract_html("a $x $ b") == "a $x $ b"

    def test_closing_followed_by_digit(self):
        assert abstract_html("from $x$5") == "from $x$5"

    def test_no_math_means_no_span(self):
        assert "math-tex" not in abstract_html("A plain abstract, no formulas.")


class TestEscaping:
    def test_html_outside_math_is_escaped(self):
        assert abstract_html("<script>alert(1)</script>") == (
            "&lt;script&gt;alert(1)&lt;/script&gt;"
        )

    def test_html_inside_math_is_escaped(self):
        assert abstract_html("$a<b$") == INLINE.format("a&lt;b")

    def test_quotes_and_ampersands(self):
        assert abstract_html('Tom & "Jerry"') == "Tom &amp; &quot;Jerry&quot;"

    def test_empty(self):
        assert abstract_html("") == ""
        assert abstract_html(None) == ""


class TestSearchHighlighting:
    def test_highlights_outside_math(self):
        assert abstract_html("metric spaces", terms=["metric"]) == ("<mark>metric</mark> spaces")

    def test_never_highlights_inside_math(self):
        html = abstract_html(r"metric $\mathrm{metric}$", terms=["metric"])
        assert html == f"<mark>metric</mark> {INLINE.format(chr(92) + 'mathrm{metric}')}"

    def test_case_insensitive(self):
        assert abstract_html("Metric", terms=["metric"]) == "<mark>Metric</mark>"

    def test_a_term_never_matches_inside_inserted_tags(self):
        assert abstract_html("mark a", terms=["mark", "a"]) == "<mark>mark</mark> <mark>a</mark>"

    def test_term_with_html_characters(self):
        assert abstract_html("a < b", terms=["<"]) == "a <mark>&lt;</mark> b"


class TestEmphasis:
    """*text* in an abstract showed as literal stars in the Details modal (prs-jm5)."""

    def test_star_pair_becomes_em(self):
        assert abstract_html("the *cycle core* of") == "the <em>cycle core</em> of"

    def test_pair_can_hold_math(self):
        out = abstract_html("the *$k$-blocking operator* is")
        assert out == ('the <em><span class="math-tex">\\(k\\)</span>-blocking operator</em> is')

    def test_stars_inside_math_are_left_alone(self):
        out = abstract_html("at $k^*$ and $H_{k^*}$")
        assert "<em>" not in out
        assert "k^*" in out

    def test_arithmetic_and_lone_stars_stay_stars(self):
        assert abstract_html("2 * 3 * 4") == "2 * 3 * 4"
        assert abstract_html("a lone * star") == "a lone * star"

    def test_unclosed_star_stays_a_star(self):
        assert abstract_html("an *open phrase") == "an *open phrase"

    def test_emphasised_text_is_still_escaped(self):
        assert abstract_html("*a <b> c*") == "<em>a &lt;b&gt; c</em>"

    def test_search_terms_inside_emphasis_are_marked(self):
        assert abstract_html("*cycle core*", terms=["core"]) == "<em>cycle <mark>core</mark></em>"

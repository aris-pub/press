// Typesets the math in abstracts (prs-58a). The server marks each formula as
// <span class="math-tex">\(...\)</span> (app/abstract_math.py). MathJax, the same
// build RSM uses, is fetched only when a page has such a span, and only those spans
// are typeset, so a dollar sign anywhere else on the page stays text.
(function () {
  "use strict";
  var SRC = "/static/vendor/mathjax-3.2.2/tex-chtml-full.js";
  var loading = null;

  function load() {
    if (loading) return loading;
    window.MathJax = {
      tex: { inlineMath: [["\\(", "\\)"]], displayMath: [["\\[", "\\]"]] },
      startup: { typeset: false },
    };
    loading = new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = SRC;
      script.async = true;
      script.onload = function () {
        window.MathJax.startup.promise.then(resolve, reject);
      };
      script.onerror = reject;
      document.head.appendChild(script);
    });
    return loading;
  }

  function typeset(root) {
    var spans = (root || document).querySelectorAll(".math-tex");
    if (!spans.length) return;
    load()
      .then(function () {
        return window.MathJax.typesetPromise(Array.prototype.slice.call(spans));
      })
      .catch(function () {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      typeset(document);
    });
  } else {
    typeset(document);
  }
  // Subject filtering and boosted links swap new cards in without a page load.
  document.addEventListener("htmx:afterSettle", function (event) {
    typeset(event.target);
  });
})();

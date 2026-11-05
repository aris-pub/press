# Frequently Asked Questions

## What formats does Press accept?

Press accepts HTML files from any source:

- **Quarto** - Export with `quarto render document.qmd --to html`
- **Typst** - Export to HTML when available
- **Jupyter** - Convert with `jupyter nbconvert --to html notebook.ipynb`
- **MyST** - Build with `myst build --html`
- **Hand-coded HTML** - Upload your HTML file directly

Maximum file size is 50MB.

**Looking for examples?** Check out our [examples repository](https://github.com/aris-pub/examples-press) with working samples from each format.

## How do I prepare my upload?

**Single HTML file:** if your work is one self-contained `.html` file (all CSS/JS inlined), just upload it directly.

**HTML with local assets:** if your HTML references external files (images, stylesheets, scripts, data), put everything in a folder and zip it. The zip should contain your HTML file alongside its assets with relative paths preserved. Press will auto-detect the main HTML file.

**Tool-specific tips:**

- **Quarto**: `quarto render` with `self-contained: false` produces an HTML file plus a `_files/` directory, so zip the whole output folder
- **Observable**: Export produces `index.html` plus asset directories, so zip as-is
- **R Markdown**: `rmarkdown::render()` with `self_contained: FALSE`, then zip the HTML and its `_files/` folder
- **Jupyter**: `nbconvert --to html` usually produces a single file, but if you have local images, zip them together

**Allowed file types in zip archives:** HTML, CSS, JavaScript, images (PNG, JPG, GIF, WebP, SVG), fonts (WOFF, WOFF2, TTF, OTF), and data files (JSON, CSV, TSV, TXT).

## What is a "Scroll"?

A scroll is what we call each document on Press. The name reflects how HTML research is meant to be experienced: you scroll through it on your screen, rather than flipping through static pages like a PDF.

It's also a nod to ancient scrolls, the original format for sharing knowledge before bound books existed. Just as scrolls were designed to be unrolled and read continuously, web-native research is designed to flow naturally on screens of any size.

## Is Press free?

Yes, forever. Posting and hosting on Press is completely free with no paywalls or subscriptions.

There are no paid tiers and no premium features.

## Does Press review scrolls before they are posted?

No. Press does not review scrolls before posting for quality, novelty, or correctness. We are infrastructure for research, not a gatekeeper of it.

We do run automated checks at upload time (spam detection, content structure validation, security scanning), and we will remove content that violates our [Content Policy](/content-policy): things like spam, plagiarism, or malicious code. But we do not judge whether your research is good enough to publish. That is for the research community to decide.

For full details, see our [Content Policy](/content-policy).

## Who owns my content?

You do, 100%. You retain full ownership and copyright of your work.

When you post a scroll, you choose a license:

- **CC BY 4.0** - Open access with attribution (recommended for research)
- **All Rights Reserved** - Traditional copyright

Press simply hosts and archives your work. You can request deletion at any time.

## How long do links last?

Permanently. Once posted, your scroll receives a permanent URL and a DOI. Content is immutable: what you post is what stays archived.

We're integrating with DataCite to issue DOIs (Digital Object Identifiers) for long-term citability and discoverability.

## Can I update a scroll after posting?

Yes, by posting a new version. On your dashboard, click "Upload New Version" on the scroll. Each version gets its own URL and its own DOI, and earlier versions stay readable, as on arXiv (v1, v2, v3...).

## Is my scroll private before I post it?

Yes. Uploaded drafts are only visible to you until you click "Post scroll." After that, anyone can read them.

## How do I cite a scroll from Press?

Use the DOI shown on the scroll page, with the authors and title. Example:

> Torres, L. (2026). *Title of Scroll*. Scroll Press. https://doi.org/10.5281/zenodo.XXXXXXXX

## How does Press work with AI research tools?

Your research on Press is discoverable through both traditional search (Google Scholar) and modern AI research assistants (Claude, ChatGPT, Scite, Consensus, Elicit).

**Why this matters:** Researchers increasingly discover papers by asking AI tools "What's the latest research on X?" rather than browsing publisher websites. Press's semantic HTML structure makes your work easy for AI tools to understand, cite, and synthesize accurately.

**What you get:**
- Your work reaches readers through direct browsing AND AI-assisted discovery
- AI tools can properly cite your work with correct attribution
- Semantic structure means accurate extraction (not heuristic PDF parsing)

**No AI slop:** Press doesn't use AI to generate, summarize, or alter your content. Your words are your words. We just make sure AI tools can find and cite them properly.

## Can I delete a scroll?

No, but you can withdraw it. Email hello@aris.pub. A withdrawn scroll stays at its URL, marked as withdrawn, so citations and its DOI keep working. We remove a scroll entirely only for legal reasons, such as a copyright claim or personal data.

## What if I find a bug or have feedback?

Press is under active development. Please report issues or share feedback:

- Email: hello@aris.pub
- GitHub: [github.com/aris-pub/press](https://github.com/aris-pub/press)

Your feedback helps make Press better for everyone.

## Is Press open source?

Yes, always and forever. Press is fully open source and community-managed.

The entire codebase is available on [GitHub](https://github.com/aris-pub/press) under an open source license. We believe research infrastructure should be transparent, collaborative, and owned by the community it serves.

Anyone can contribute code, report issues, or fork the project. Press will never be closed-source or controlled by a single entity.

## What's next on the roadmap?

Check our [roadmap](/roadmap) to see upcoming features including:

- Advanced search and filtering
- Custom themes
- And more...

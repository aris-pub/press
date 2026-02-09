# Frequently Asked Questions

## What formats does Press accept?

Press accepts HTML files from any source:

- **Quarto** - Export with `quarto render document.qmd --to html`
- **Typst** - Export to HTML when available
- **Jupyter** - Convert with `jupyter nbconvert --to html notebook.ipynb`
- **MyST** - Build with `myst build --html`
- **Hand-coded HTML** - Upload your HTML file directly

You can upload a single HTML file with inlined assets (images, CSS, JavaScript). Maximum file size is 50MB.

**Looking for examples?** Check out our [examples repository](https://github.com/aris-pub/examples-press) with working samples from each format.

## What is a "Scroll"?

A scroll is what we call a preprint on Press. The name reflects how HTML research is meant to be experienced: you scroll through it on your screen, rather than flipping through static pages like a PDF.

It's also a nod to ancient scrolls—the original format for sharing knowledge before bound books existed. Just as scrolls were designed to be unrolled and read continuously, web-native research is designed to flow naturally on screens of any size.

## Is Press free?

Yes, forever. Publishing and hosting on Press is completely free with no paywalls or subscriptions.

We may introduce optional premium features in the future (custom domains, advanced analytics), but core publishing will always remain free.

## Who owns my content?

You do, 100%. You retain full ownership and copyright of your work.

When you publish, you choose a license:

- **CC BY 4.0** - Open access with attribution (recommended for research)
- **All Rights Reserved** - Traditional copyright

Press simply hosts and archives your work. You can request deletion at any time.

## How long do links last?

Permanently. Once published, your paper receives a permanent URL that will never break. Content is immutable - what you publish is what stays archived.

We're integrating with DataCite to issue DOIs (Digital Object Identifiers) for long-term citability and discoverability.

## Can I update a paper after publishing?

Not yet. Currently, published papers are immutable to ensure archival integrity.

We're building a versioning system that will allow you to publish new versions while preserving the original. This will work similar to arXiv's versioning (v1, v2, v3...).

## Is my content private before publishing?

Yes. Uploaded drafts are only visible to you until you click "Publish." Once published, papers become publicly accessible.

## How do I cite a paper from Press?

Use the permanent URL and author/title information. Example:

> Torres, L. (2026). *Title of Paper*. Scroll Press. https://press.aris.pub/scroll/abc123

DOI-based citations will be available once DataCite integration is complete.

## Can I delete my paper?

Yes. Contact us at hello@aris.pub to request removal. We'll take down the public-facing content, though we may retain archival copies for legal/administrative purposes.

## What if I find a bug or have feedback?

We're in closed beta and actively improving the platform. Please report issues or share feedback:

- Email: hello@aris.pub
- GitHub: [github.com/aris-pub/press](https://github.com/aris-pub/press)

Your feedback helps make Press better for everyone.

## Is Press open source?

Yes, always and forever. Press is fully open source and community-managed.

The entire codebase is available on [GitHub](https://github.com/aris-pub/press) under an open source license. We believe research infrastructure should be transparent, collaborative, and owned by the community it serves.

Anyone can contribute code, report issues, or fork the project. Press will never be closed-source or controlled by a single entity.

## What's next on the roadmap?

Check our [roadmap](/roadmap) to see upcoming features including:

- DOI integration via DataCite
- Versioning system
- Advanced search and filtering
- Custom themes
- And more...

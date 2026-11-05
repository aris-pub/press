# Quick Start Guide

Get from signup to a permanent URL and DOI in 5 minutes.

## 1. Create Account

[Sign up](/register) with your email address. Check your inbox for a verification email and click the link to activate your account.

## 2. Upload Your Work

Once logged in, go to your [dashboard](/dashboard) and click "Upload New Scroll." Each document on Press is called a scroll.

**What to upload:**

- A single `.html` file with everything inlined, OR
- A `.zip` archive containing your HTML file and its assets (images, CSS, JS, data files)

**Size limit:** 50MB maximum.

**How to create HTML files:**

- **[RSM](https://rsm-lang.readthedocs.io/en/latest/):** `rsm build paper.rsm --standalone` (single file), or zip the output folder
- **[Quarto](https://quarto.org/docs/output-formats/html-basics.html):** `quarto render document.qmd --to html` (single file or zip the output folder)
- **[Typst](https://typst.app/docs/reference/html/):** HTML export (experimental)
- **[Jupyter](https://nbconvert.readthedocs.io/en/latest/):** `jupyter nbconvert --to html notebook.ipynb`
- **[MyST](https://myst-parser.readthedocs.io/en/latest/):** Use MyST-Parser HTML export
- **Hand-coded:** Write HTML directly

If your tool produces an HTML file plus a `_files/` or assets directory, zip the whole output folder and upload the zip. Press will auto-detect the entry point.

**Need examples?** Check out our [examples repository](https://github.com/aris-pub/examples-press) with sample scrolls from Quarto, Typst, Jupyter, and more.

## 3. Add Metadata

Fill in the required fields:

- **Title** - The title of your work
- **Authors** - Author names (one per line or comma-separated)
- **Abstract** - Brief summary of your work
- **Subject** - Primary research area
- **Keywords** - Searchable tags (optional)

Choose a license:

- **CC BY 4.0** (recommended for open research)
- **All Rights Reserved**

## 4. Preview

Review how your scroll will look on the platform. Check that:

- Images and media load correctly
- Formatting looks right
- Interactive elements work (if applicable)

## 5. Post

Click "Post scroll" to make your scroll public. You'll receive:

- A permanent URL
- A DOI

Your scroll is now public and archived.

---

**Need help?** Contact hello@aris.pub or check the [FAQ](/docs/faq).

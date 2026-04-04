# URL Redesign — Showcase Launch Architecture

**Scope:** Minimum changes to support `scroll.press/2026/slug` URLs for the showcase
launch. No slug editing UI, no word-pill interface, no keyword extraction from
abstracts. Those come later.

---

## What Changes

### New URL Scheme

```
scroll.press/2025/glee-graph-learning          <- NEW: year/slug (primary sharing URL)
scroll.press/scroll/9bf73ea5ee86                <- UNCHANGED: hash URL (verification)
scroll.press/scroll/9bf73ea5ee86/paper          <- UNCHANGED: raw HTML in iframe
```

Year/slug URLs render the same scroll page (Press chrome + iframe). Hash URLs
continue to work exactly as before. Both are permanent.

### Slug Generation

Derive the slug from the scroll title at publish time:

```
"Graph Learning: Efficient Embedding Estimation" -> "graph-learning-efficient-embedding-estimation"
```

Rules:
- Lowercase, strip non-alphanumeric (keep hyphens)
- Remove stop words (the, a, an, of, for, in, on, with, and, or, to, is, by)
- Truncate to 60 chars on a word boundary
- Collision within same year: append `-2`, `-3`, etc.

No keyword extraction, no TF-IDF, no abstract parsing. Just slugify the title.

### Publication Year

Use the year from `published_at`. For scrolls published in preview/draft state,
use the current year at publish time.

---

## Database Changes

### New Columns on `scroll` Table

```sql
ALTER TABLE scroll ADD COLUMN slug VARCHAR(60);
ALTER TABLE scroll ADD COLUMN publication_year INTEGER;

CREATE UNIQUE INDEX uq_scroll_year_slug ON scroll (publication_year, slug)
  WHERE status = 'published';
```

- `slug`: nullable (existing scrolls get backfilled, new scrolls get it at publish)
- `publication_year`: nullable (derived from `published_at`)
- Unique constraint scoped to published scrolls only

### Alembic Migration

Single migration that:
1. Adds `slug` and `publication_year` columns
2. Backfills existing published scrolls (generate slug from title, year from published_at)
3. Creates the unique index

### Model Changes

**File:** `app/models/scroll.py`

Add to the Scroll model:

```python
slug = Column(String(60), nullable=True)
publication_year = Column(Integer, nullable=True)
```

Add a property:

```python
@property
def canonical_url(self) -> str:
    if self.publication_year and self.slug:
        return f"/{self.publication_year}/{self.slug}"
    return self.permanent_url
```

---

## Routing Changes

### New Route

**File:** `app/routes/scrolls.py`

```python
@router.get("/{year:int}/{slug:str}")
async def view_scroll_by_slug(year: int, slug: str, ...):
    scroll = await db.execute(
        select(Scroll).where(
            Scroll.publication_year == year,
            Scroll.slug == slug,
            Scroll.status == "published"
        )
    )
    # ... same rendering logic as view_scroll()
```

The existing `/scroll/{identifier}` route stays unchanged.

### Paper Route

No change needed. The iframe still loads `/scroll/{url_hash}/paper`. The
year/slug route renders the same `scroll.html` template, which references
`scroll.url_hash` for the iframe src.

### OG Image Route

No change needed. OG image URL in meta tags will use the hash-based path since
the image is generated from content.

---

## Publish Flow Changes

**File:** `app/routes/scrolls.py`, `confirm_preview()` handler

At publish time (when user confirms preview):

1. Generate slug from title (new utility function)
2. Set `publication_year` from current year
3. Check uniqueness of `(year, slug)`, append suffix if collision
4. Save slug and year to scroll
5. Redirect to `/{year}/{slug}` instead of `/scroll/{url_hash}`

---

## Template Changes

### scroll.html

Update meta tags to use canonical year/slug URL:

```html
<meta property="og:url" content="{{ base_url }}/{{ scroll.publication_year }}/{{ scroll.slug }}" />
<link rel="canonical" href="{{ base_url }}/{{ scroll.publication_year }}/{{ scroll.slug }}" />
```

Keep hash-based URLs for iframe src and verification links.

### scroll_card.html

Update card links to use `canonical_url`:

```html
<a href="{{ scroll.canonical_url }}">
```

### dashboard_content.html

Pass `scroll.canonical_url` instead of raw `url_hash` to scroll_card.

---

## Utility Function

**New file:** `app/utils/slug.py`

```python
import re
from unicodedata import normalize

STOP_WORDS = {"the", "a", "an", "of", "for", "in", "on", "with", "and", "or", "to", "is", "by"}

def slugify_title(title: str, max_length: int = 60) -> str:
    text = normalize("NFKD", title).encode("ascii", "ignore").decode()
    text = text.lower()
    words = re.findall(r"[a-z0-9]+", text)
    words = [w for w in words if w not in STOP_WORDS]
    slug = "-".join(words)
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug


async def generate_unique_slug(db, title: str, year: int) -> str:
    base = slugify_title(title)
    slug = base
    suffix = 2
    while await slug_exists(db, year, slug):
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
```

---

## What Does NOT Change

- Hash URL routing (`/scroll/{hash}`)
- Hash URL generation (content-addressable, SHA-256)
- Paper serving (`/scroll/{hash}/paper`)
- Upload flow (still creates preview with hash URL)
- Preview flow (`/preview/{hash}`)
- OG image generation
- Raw HTML download
- DOI minting
- iframe isolation / CSP

---

## Migration for Existing Scrolls

Run once after deploying the schema migration:

```python
for scroll in published_scrolls:
    scroll.publication_year = scroll.published_at.year
    scroll.slug = await generate_unique_slug(db, scroll.title, scroll.publication_year)
```

This can be part of the Alembic migration's `upgrade()` using a data migration step.

---

## Implementation Order

1. `app/utils/slug.py` — slugify function + unique slug generator
2. Alembic migration — add columns, backfill, create index
3. `app/models/scroll.py` — add fields + `canonical_url` property
4. `app/routes/scrolls.py` — add `/{year}/{slug}` route
5. `app/routes/scrolls.py` — update `confirm_preview()` to set slug/year at publish
6. Templates — update meta tags and card links to use canonical URL
7. Tests

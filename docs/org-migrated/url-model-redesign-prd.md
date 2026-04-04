# Press URL Model Redesign - Lean PRD

**Date:** February 15, 2026
**Product:** Press
**Feature:** Human-Readable URL Model (`scroll.press/YYYY/slug`)

---

## Overview

Add human-readable year/slug URLs (`scroll.press/2026/quantum-entanglement`) alongside existing hash URLs (`scroll.press/hash/<hash>`) to improve accessibility, shareability, and citation stability. Make readable URLs the primary sharing mechanism while preserving hash URLs for verification purposes.

**Why:** Hash URLs create accessibility barriers (screen readers, mobile sharing, verbal communication) but are essential for content verification. Solution: Two URL schemes serving different purposes—year/slug for sharing, hash for verification.

**Impact:** Repositions Press as accessible, permanent infrastructure with built-in verification, designed for researchers not technical abstraction.

---

## RX Specifications

### Two URL Schemes, Two Purposes

**Year/Slug URLs** (`scroll.press/2026/quantum-entanglement`):
- **Purpose:** Sharing, citing, discovering papers
- **Renders:** Press chrome (navigation, metadata, version switcher, comments)
- **Characteristics:** Human-readable, screen-reader friendly, speakable, memorable
- **Primary use:** Citations, social sharing, conference slides, verbal communication

**Hash URLs** (`scroll.press/hash/abc123...`):
- **Purpose:** Content verification
- **Renders:** Raw HTML exactly as uploaded (no Press chrome)
- **Verification:** `curl scroll.press/hash/HASH | md5` outputs HASH prefix
- **Primary use:** Integrity checking, archival validation, forensic audit

### User Flows

**Publishing Flow:**
1. Author uploads manuscript → system extracts 4-8 keywords from title/abstract
2. System suggests slug (e.g., `quantum-entanglement-photonic-systems`)
3. Preview: `scroll.press/2026/[suggested-slug]` shown in URL card
4. Two options:
   - **"Adopt this URL"** → slug locked, publishing continues
   - **"Edit URL"** → word-pill interface appears (see UI specs)
5. Publish → Both URLs active (`/2026/slug` for sharing, `/hash/HASH` for verification)

**Sharing Flow:**
- Researchers share year/slug URLs verbally (conferences), mobile email, projected slides
- Human-readable slugs reduce cognitive load, increase trust signals
- Hash URL available in metadata for verification (not primary sharing mechanism)

**Versioning Flow:**
- Canonical URL (`/2026/slug`) resolves to latest version (with Press chrome)
- Version-specific URLs (`/2026/slug/v/1`, `/v/2`) frozen with Press chrome
- Hash URLs remain unchanged per version (each version has unique hash)

**Verification Flow:**
- Researcher wants to verify paper integrity
- Accesses hash URL (`/hash/HASH`) → gets raw HTML
- Runs `curl scroll.press/hash/HASH | md5` → compares with HASH
- No Press chrome interference with verification

### Success Metrics

- **Adoption rate:** 70%+ authors adopt suggested slug (= good keyword extraction)
- **Customization rate:** 10-30% authors use Edit URL (= defaults work but flexibility exists)
- **Citation usage:** 80%+ citations use year/slug URL (not hash) after 6 months
- **Author satisfaction:** 80%+ prefer year/slug URLs for sharing
- **Verification availability:** 100% hash URLs remain functional (no degradation)

### Accessibility Requirements

- **Screen readers:** Human-readable year/slug URLs (not character-by-character hash)
- **WCAG compliance:** URL readability is accessibility requirement (blind researchers, dyslexia)
- **Mobile sharing:** Year/slug URLs work in constrained channels (autocomplete, verbal)
- **Keyboard navigation:** Word-pill click-to-add fully keyboard-accessible (arrow keys, space to select)

---

## Technical Specifications

### System Architecture

**Dual URL Scheme:**
```
scroll.press/YYYY/slug              → Canonical (latest version, Press chrome)
scroll.press/YYYY/slug/v/N          → Version-specific (frozen, Press chrome)
scroll.press/hash/HASH              → Raw HTML verification (no chrome, permanent)
```

**Critical:** Hash URLs are NOT legacy—they are permanent verification URLs. No redirects.

**Slug Generation (Keyword Extraction):**
- Extract 4-8 meaningful words from title and abstract (TF-IDF, keyword extraction algorithm)
- Filter: Remove stop words ("the", "a", "of"), keep nouns and domain terms
- Suggest slug: Top 3-5 keywords joined by hyphens
- Max length: 60 chars (truncate intelligently if needed)
- Collision handling: Auto-append numeric suffix (`slug-2`, `slug-3`) within same year

**Data Model Changes:**
- Add fields: `slug` (varchar 60, nullable initially), `publication_year` (int), `version_number` (int), `is_canonical` (bool), `slug_keywords` (text[], stores extracted keywords for word-pill UI)
- Unique constraints: `(publication_year, slug, version_number)`, `(publication_year, slug) WHERE is_canonical`
- Hash URLs remain unchanged: `content_hash` field stays, hash routing unchanged
- Indexes: Canonical lookup `(publication_year, slug, is_canonical)`, hash lookup `(content_hash)`

**Version Management:**
- Each version has unique hash URL (`/hash/HASH_V1`, `/hash/HASH_V2`)
- Year/slug URLs with Press chrome: Canonical (`/2026/slug`) = latest, versions (`/2026/slug/v/N`) frozen
- Hash URLs with raw HTML: Each version hash permanent, no "canonical" concept

**Migration Strategy (Not Really Migration):**
- Phase 1: Add slug fields to database schema (including `slug_keywords TEXT[]` for storing extracted keywords)
- Phase 2: Generate slugs for existing papers (keyword extraction)
- Phase 3: Deploy year/slug routing (hash routing unchanged)
- Phase 4: Update UI to show both URLs (year/slug primary, hash for verification)
- **No redirects:** Both URL schemes coexist permanently
- Estimated timeline: 4 weeks implementation (includes word-pill UI with click-to-add interaction)

### Security & Privacy

- **Slug validation:** Multi-layer (format, length, reserved words, profanity filter)
- **Collision attacks:** No pre-registration (first-to-publish wins), auto-suffix for conflicts
- **Word-pill constraints:** User can only use words extracted by system (no free-text injection)
- **Verification integrity:** Hash URLs must render raw HTML unchanged (no Press chrome injection)

### Infrastructure

**No CDN or Redis at this stage:**
- Database indexes for fast slug lookup (<10ms target)
- PostgreSQL full-text search for keyword extraction (built-in, no external deps)
- Simple caching via HTTP headers (browser caching sufficient for MVP)

**Deferred to post-MVP:**
- CDN edge caching (add when traffic justifies)
- Redis application cache (add if database becomes bottleneck)

### Tech Stack

- **Keyword extraction:** PostgreSQL `ts_rank` + custom TF-IDF scoring (no external library)
- **Slug validation:** Custom validation (format, profanity filter via `better-profanity`)
- **Routing:** FastAPI path parameters (already in stack)
- **Migrations:** Alembic (incremental, rollback-safe)
- **Monitoring:** Sentry (already in stack) for errors, no Prometheus initially

---

## Design Specifications

### Slug Customization Interface (Click-to-Add + Arrow Buttons)

**Location:** Publishing workflow, step 3 (after upload, before final publish)

**Initial State (Suggested Slug):**

```
┌─ URL Preview ─────────────────────────────────────┐
│                                                    │
│  Your paper will be published at:                 │
│                                                    │
│  scroll.press/2026/                               │
│  ┌──────────────────────────────────────────┐    │
│  │ quantum-entanglement-photonic-systems    │    │
│  └──────────────────────────────────────────┘    │
│     ^^ Monospace textarea (NOT editable yet)      │
│                                                    │
│  [Adopt this URL]  [Edit URL]                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Component Spec:**
- URL display: `scroll.press/2026/` in regular font (permanent)
- Slug: Monospace textarea (read-only in initial state)
- Two buttons: "Adopt this URL" (primary) and "Edit URL" (secondary)

**Edit Mode (Word-Pill Interface - Click-to-Add + Arrow Buttons):**

```
┌─ Edit URL ────────────────────────────────────────┐
│                                                    │
│  scroll.press/2026/                               │
│  ┌──────────────────────────────────────────┐    │
│  │ [quantum] [↑↓] [entanglement] [↑↓]       │    │
│  │ [photonic] [↑↓]                          │    │
│  └──────────────────────────────────────────┘    │
│     ^^ URL composition (click × to remove)        │
│                                                    │
│  Available words (click to add):                  │
│  [systems] [coherence] [measurement]              │
│                                                    │
│  ⓘ Click words to add, use arrows to reorder     │
│                                                    │
│  [Save URL]  [Cancel]                             │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Component Spec - Edit Mode:**

**URL composition area:**
- Monospace font
- Pills displayed with hyphens between them visually
- Each pill has: word text + [↑↓] arrow buttons + [×] remove button
- Max 5-6 pills (enforce reasonable slug length)
- Click-to-add from available words (no drag-and-drop)

**Word-pill visual design:**
- Background: Light blue (`#dbeafe`)
- Border: 1px solid blue (`#3b82f6`)
- Border-radius: 16px (pill shape)
- Padding: 10px 14px (44px minimum touch target height on mobile)
- Font: 14px, medium weight
- Cursor: pointer (clickable, not draggable)
- Hover: Slightly darker background (`#bfdbfe`)
- Focus: 2px blue outline (`#2563eb`), 2px offset (WCAG 2.4.7)

**Arrow buttons (reordering):**
- Size: 32px × 32px (adequate touch target)
- Icon: Up/down arrows (heroicon or similar)
- Position: Right of each pill
- Click up → move pill left one position
- Click down → move pill right one position
- Disabled state: Gray out if pill is first/last

**Remove button:**
- Size: 24px × 24px (×  icon)
- Position: Top-right of pill (slightly overlapping)
- Hover: Red tint
- Click: Remove pill from composition

**Available words panel:**
- 4-8 word-pills extracted from title/abstract (stored in `slug_keywords` field)
- Keywords already in composition are dimmed (low opacity)
- Click to add to composition (appends to end)
- Words can be used multiple times if needed

**Async validation:**
- On every composition change, check uniqueness (debounced 500ms)
- If conflict: Auto-append suffix (`-2`, `-3`) and show notification
- Notification: "URL taken, using `slug-2` instead" (dismissible banner)

**Keyboard accessibility:**
- Tab to focus pills, arrow buttons, remove buttons
- Arrow keys: Navigate between interactive elements
- Space/Enter: Activate buttons (add word, move up/down, remove)
- Delete key: Remove focused pill
- Screen reader announces: "quantum, pill 1 of 3, reorder up button, reorder down button, remove button"

**Mobile responsive:**
- Touch targets: 44px minimum height (WCAG 2.5.5)
- Arrow buttons stack vertically on <375px width if needed
- Available words wrap to multiple rows

### Version Navigation UI

**Location:** Paper header (top of scroll page, only on year/slug URLs)

**Component:** Version Dropdown
- Trigger: "Version: v3 (latest) ▾" button
- Panel: List of versions with:
  - Year/slug URL for each version (`/2026/slug/v/1`, `/v/2`)
  - Hash URL for verification (`/hash/HASH_V1`)
  - Copy buttons for both URLs
- Current version indicator: ● (green filled) vs ○ (gray empty)

**Mobile Responsive:**
- Dropdown width: 90vw (mobile), 400px (desktop)
- Touch targets: 44px minimum
- URL text wraps (no truncation)

### URL Display Components

**Paper Page (Year/Slug URLs):**
- Prominent "Permanent URL" display: Year/slug URL with copy button
- Secondary "Verification URL": Hash URL with copy button + explanation ("Verify integrity")
- Share options: Email, Twitter, LinkedIn (use year/slug URL)

**Paper Page (Hash URLs):**
- No Press chrome (raw HTML only)
- Minimal footer: "Verification URL: scroll.press/hash/HASH" + link to Press chrome version

**Published Confirmation:**
- Success screen shows BOTH URLs:
  - Primary: Year/slug URL (for sharing)
  - Secondary: Hash URL (for verification)
- Copy buttons for each

---

## Positioning & Launch

### Messaging

**Core value proposition:** "Share with Confidence, Verify with Proof"

**Key messages:**
1. **Shareability:** URLs you can speak, email, and cite without cognitive load (screen readers, mobile, verbal)
2. **Accessibility:** Screen-reader friendly URLs for every researcher, not just sighted users
3. **Integrity:** Built-in verification for reproducibility advocates and institutional archivists
4. **Equity:** Readable URLs for everyone, not premium tier—accessibility is a right, not a feature

**Framing:** Not choosing between readability and verification—offering both.

### Competitive Positioning

- **arXiv:** Hash-only URLs (verification exists but not human-friendly)
- **Zenodo/OSF:** Generic hashes, no semantic URLs
- **Press:** Dual scheme (human-readable + verifiable)

**Differentiator:** "Share with year/slug, verify with hash—best of both worlds"

### Launch Strategy

**Timing:** Public launch with Press (not separate rollout)

**Communication:**
- Blog post: "Share with Confidence, Verify with Proof: Designing URLs for Researchers"
- Bluesky thread: "Press: Open Source Preprint Server with Human-Readable + Verifiable URLs"
- Docs: Clear explanation of when to use which URL (year/slug for sharing, hash for verification)
- Sustainability transparency: Add funding model to Press landing page (grants, donations, free forever)

**Post-Launch:**
- Monitor adoption rate (% using "Adopt this URL" vs "Edit URL")
- Track citation patterns (year/slug vs hash in citations)
- Gather feedback on word-pill UI (friction points, missing keywords)

---

## Documentation Requirements

### User-Facing

1. **Two URL schemes explained:** When to use year/slug (sharing) vs hash (verification)
2. **How slug generation works:** Keyword extraction transparency
3. **How to customize slugs:** Word-pill click-to-add guide (with video)
4. **Verification guide:** How to verify content integrity using hash URL

### Technical Docs

1. **Hash URL specification:** Raw HTML rendering requirements (no chrome)
2. **Keyword extraction algorithm:** For transparency (researchers should understand how slugs are generated)

---

## Assumptions

1. **Keyword extraction quality:** Algorithm extracts meaningful words 70%+ of the time
2. **Word-pill UX:** Researchers can understand click-to-add without training
3. **Dual URL clarity:** Researchers understand purpose distinction (sharing vs verification)
4. **Hash URL usage:** <5% of citations use hash URL (most use year/slug)
5. **Solo founder capacity:** 4 weeks implementation fits 20-30 hrs/week constraint

---

## Open Questions

1. **Keyword extraction source:** Title only vs title + abstract? → **Resolve via:** Test both, measure slug quality
2. **Word-pill limit:** Max 5-6 pills reasonable? → **Resolve via:** Beta testing, measure customization patterns
3. **Hash URL visibility:** Prominent or secondary on paper page? → **Resolve via:** Test with researchers who care about verification
4. **Year/slug for verification:** Should hash also be in year/slug URL metadata? → **Resolve via:** Check if verification tools need it
5. **Slug conflict UX:** Show all conflicts upfront or handle async? → **Resolve via:** Test responsiveness vs clarity trade-off

---

**Next Steps:**

1. **CRXO approval:** Dual URL scheme (year/slug + hash) acceptable?
2. **CTO review:** Keyword extraction feasible in PostgreSQL? Timeline realistic?
3. **UI Designer mockups:** Word-pill interface prototypes
4. **Beta test:** 5-10 researchers try word-pill customization, gather feedback
5. **Implementation:** 4 week sprint (simpler than original—no redirect logic)

**Success = dual URLs become standard:** "Press gives you a URL you can share AND verify"

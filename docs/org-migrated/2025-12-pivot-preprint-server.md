# Pivot toward a preprint server

**Status:** Historical (December 2025)

**Note**: This document captures the initial pivot toward a preprint server. For current strategic positioning and competitive analysis (as of January 2026), see `competitive-positioning.md`.

## Executive Summary

Scroll Press is **what arXiv would be if it was built today** - a permanent, trusted archive for HTML-native research. We're an ARCHIVE, not a platform. Simple upload, permanent storage, DOIs.

## Core Innovation

"HTML preprints that last forever" - A preprint archive that accepts HTML from any tool (Typst, Quarto, Markdown, MyST, Observable), with permanent URLs and DOIs. Like arXiv, but for the web.

## Core Vision Evolution

### From
- Annotation tool competing with Hypothesis/Mendeley
- Solving "PDF annotation problems"
- Convincing satisfied researchers to change

### To
- Publishing platform that makes marginalia part of scholarship
- Infrastructure for living documents with bundled metadata
- Capturing the existing trend away from PDF-only publishing

## The Four Foundational Pillars

1. **UNIVERSAL**
   - Documents work on any device, any ability, any preference
   - Work offline or online, your library syncs everywhere
   - Open API - no platform lock-in
   - Accessibility is non-negotiable

2. **TRANSPARENT**
   - Bundle prose, code, data, history, annotations, feedback
   - Permanent addresses for all versions
   - Everything exportable

3. **INTERACTIVE**
   - Multimedia, visualizations, immediate feedback
   - UI gets out of the way and offers context on demand
   - Real-time collaboration when wanted

4. **INVITING**
   - Reading feels effortless
   - Form follows function
   - Respects user's time

## Strategic Pivot: API as Enabler

**Instead of:** "Use our annotation system"
**New approach:** "We handle web-native docs + persistent metadata, integrate with YOUR workflow"

- Build API for Aris frontend anyway
- Open it with examples (Notion, Obsidian exports)
- Let community build/maintain integrations
- Become metadata backbone, not destination

## Critical Challenges & Responses

### Challenge: Researchers are satisfied with PDFs
**Response:** They're satisfied within the PDF paradigm. We're building for the post-PDF era that's already emerging (Typst, journal HTML, etc.)

### Challenge: Network effects - arXiv has millions of papers
**Response:** Not competing with arXiv initially. Building infrastructure for next generation of publishing. Start with Typst users and LaTeX refugees.

### Challenge: Who publishes first 100 papers?
**Response:**
- Author publishes own work first
- Typst enthusiasts (already rejecting standards)
- Researchers attempting interactive papers
- Those frustrated with journal HTML

### Challenge: Long-term maintenance commitment
**Response:** If successful enough to worry about (100k papers), community and institutional support will exist. If not, sunset gracefully with full data export.

### Challenge: Power users have elaborate existing systems
**Response:** Don't replace their systems - feed them better data via API. Their Obsidian/Notion stays workflow, but gets enriched by Aris metadata.

## What Makes Aris Different

Not just HTML output (others do this), but infrastructure for living documents:
- Persistent annotation anchors
- Identity and permissions
- Real-time sync
- Version tracking
- Permanent hosting
- Metadata streaming

**The bet:** Make the experience "so good it cannot be ignored"

## Market Validation Signals

- Multiple "better LaTeX" tools emerging
- Journals investing in HTML (poorly)
- Immediate "sounds awesome, support Typst!" response
- Industry already moving post-PDF

## Go-to-Market Strategy

1. **Build excellent foundation** (in progress)
2. **Support Typst import** (clear user pull)
3. **Author uses for own papers** (dogfooding)
4. **Target LaTeX refugees** (already seeking alternatives)
5. **Let early adopters discover API** (power user growth)

## Key Insights

- **"Marginalia is scholarship"** - but keep it informal, non-citable
- **Accessibility matters** - non-negotiable despite being niche
- **API strategy** - enhance workflows, don't replace them
- **Typst users** - perfect early adopters (already rejecting norms)
- **Post-PDF era** - capture existing trend, not create new demand

## The Fundamental Bet

**Aris succeeds if:**
- The reading/publishing experience is dramatically better than PDF
- Enough researchers care about accessibility, interactivity, and preserving understanding
- The trend away from PDF-only publishing continues
- A community forms around open infrastructure for research

**Aris fails if:**
- PDFs remain "good enough" for most
- Network effects of existing systems prove insurmountable
- Technical complexity of preservation overwhelms benefits
- No critical mass of early content

*The core tension remains: Building something radically new means slow adoption, but capturing the emerging post-PDF trend could position Aris as essential infrastructure for next-generation scientific publishing.*

# Roadmap

## Phase 1: Modern Preprint Hosting
**Focus:** Establish Press as the home for non-PDF preprints

## Phase 2: Enhanced Interaction (Months 6-12)
**Focus:** Add value beyond basic hosting

- Inline commenting where HTML structure allows
- Basic peer review workflows
- Email notifications for activity
- Author profiles and collections
- PDF generation for compatibility
- API for basic operations
- Success metric: 100 active review cycles

## Phase 3: Format Intelligence (Months 12-18)
**Focus:** Progressive enhancement based on format

- Smart structure detection
- Offer RSM conversion for enhanced features
- Paragraph-level annotations for compatible formats
- Cross-references and semantic linking
- Review assignment system
- Integration with ORCID
- Success metric: 30% of uploads use enhanced features

## Phase 4: Review Revolution (Months 18-24)
**Focus:** Become the preferred review platform

- Structured peer review workflows
- Version diff visualization
- Review context preservation across versions
- Anonymous and signed review options
- Integration with journal submission systems
- Post-publication review
- Success metric: First journal partnership

## Phase 5: Knowledge Layer (Years 2-3)
**Focus:** Surface the hidden knowledge

- Lab/team knowledge spaces
- Cross-paper connections and citations
- Semantic search across all content
- Data/code bundling with papers
- Reproducibility badges
- Machine-readable semantic markup (opt-in)
- Success metric: 10,000 active researchers

## Phase 6: Publishing Alternative (Years 3-5)
**Focus:** Legitimate alternative to traditional publishing

- Overlay journal infrastructure
- Formal peer review certification
- Research assessment metrics
- Institutional subscriptions
- Long-term preservation guarantees
- Become recommended platform for funding agencies
- Success metric: Recognition by major funders

## Phase 7: Protocol Emergence (Years 5+)
**Focus:** Become the infrastructure

- Open protocol for scientific documents
- Distributed hosting network
- Blockchain-backed versioning
- Universal citation standard
- Publisher adoption of Aris format
- Success metric: External apps building on Aris

# Why This Path Works

- **Solves immediate need:** Modern format users need somewhere to publish today
- **Natural adoption curve:** Each phase adds value without forcing change
- **Progressive enhancement:** Features unlock as formats evolve
- **Network effects compound:** More papers → more reviews → more value
- **Respects researcher autonomy:** You own your work, always

# Key Strategic Principles

## Start Where Researchers Are
- Don't force new formats or workflows
- Accept what they're already creating
- Add value incrementally
- Let usage guide development

## Respect Researcher Time
- No complex submission process
- No artificial deadlines
- No rights transfer
- No predatory fees

## Context Is Everything
- Reviews stay with documents
- Versions connect naturally
- Knowledge accumulates
- Nothing gets lost

## Open by Default
- All content accessible
- APIs for integration
- Export everything
- Community governance

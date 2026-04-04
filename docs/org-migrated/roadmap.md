# Press Strategy

**Product**: Press - HTML preprint archive with optional premium features

This document contains product-specific strategy for Press. For Aris Program-wide strategy, see `/program/strategy/business-model.md`.

---

## Product Vision

**What is Press:**
A permanent HTML preprint archive that enables researchers to publish web-native research with DOIs and permanent URLs. Like arXiv, but built for HTML in 2026.

**Core value proposition:**
- "Where modern research lives"
- Archive-first: permanent storage, DOIs, citability
- Free core with optional vanity features (custom domains, premium themes)

**Target audience:**
- Computational researchers (primary beachhead)
- Data scientists, digital humanists
- Anyone publishing research with interactive components

---

## Funding Model

Press is **free forever, for everyone**. There are no paid tiers and no monetization path. Preprint archival is a public good. Sustainability comes from grants and donations. See [funding.md](/program/finances/funding.md).

---

## Product-Market Fit Validation

### Success Metrics (2026)

**Phase 1 — Showcase validation (March–May 2026):**
- Social post engagement (impressions, replies, shares)
- Inbound interest (researchers who want to publish their own work)
- First non-Leo papers published on Press

**Phase 2 — Early traction (Q3 2026):**
- 20+ papers published (mix of Leo's work and community)
- 5+ unsolicited testimonials
- Researchers sharing Press papers in their own communities

**Phase 3 — Growth validation (Q4 2026):**
- 20+ papers published (revised down from 100 — realistic given 6 papers as of March 2026)
- First non-Leo papers from community outreach
- Inbound interest from researchers discovering Press organically

---

## Feature Roadmap

### Launch Features (MVP — Shipped Q1 2026)

**Shipped:**
- Publish public HTML preprints
- DOI minting via Zenodo (DataCite DOIs)
- Google Scholar indexing (Highwire meta tags, Schema.org)
- Basic search across papers
- ZIP archive upload with entry point detection
- Author-facing versioning (scroll_series_id + version number)
- ORCID field on user profiles
- Read-only public API (GET scrolls, metadata, content)
- HTML security validation (reject model, nonce-based CSP, curated JS allowlist)
- Rate limiting (5 uploads/hour per user)
- Mobile-optimized reading
- Subject categorization

**Not shipped:**
- ~~Basic themes (3-5 professional templates)~~ — Press serves author HTML as-is
- ~~Comments on public preprints~~ — deferred

**Deferred decision (evaluate post-showcase):**
- **MCP Content Server** - API/MCP access for AI tools to query Press papers
  - See [MCP Integration Ideas](/ideas/mcp-integration.md) for evaluation criteria
  - Build if: < 40 hours implementation + discovery tools interested + strategic advantage clear
  - Defer if: High complexity or no validated demand
  - Context: [AI-mediated access research](/cross/market/research/2026-02-ai-mediated-access.md) shows researchers increasingly discover papers through AI tools; [Semantic enrichment research](/cross/market/research/2026-02-semantic-enrichment-ai.md) validates that RSM's semantic structure provides measurable RAG performance advantages
  - Decision timeline: After showcase launch validates Press traction (Q2 2026)

**Can defer post-launch:**
- Advanced analytics
- Reading/annotation features (when 200+ papers justify them)

### Post-Launch Phase 1 (Q2-Q3 2026)

**Focus: Retention and feedback**
- Fix bugs reported by early users
- Improve onboarding based on user confusion
- Add most-requested features (prioritize by retention impact)
- Build community (Discord, forum, regular updates)

### Phase 2 (Q3-Q4 2026)

**Focus: Archive credibility and reading**
- Advanced search with filters
- Personal library (save papers, organize collections)
- Annotation support (highlights, notes — free)
- Citation tracking and alerts
- Discovery feed (recommendations)

### Phase 3 (2027+)

**Focus: Scale and ecosystem**
- API access for programmatic publishing
- Institutional site license support (voluntary contribution model, like arXiv)
- Integration with discovery tools (Scite, Consensus, Elicit)

---

## Go-to-Market Strategy

### Friends & Family Beta (COMPLETED — YELLOW)

Ran February 3 – March 9, 2026 with 10-15 participants. Product worked, no critical bugs, but zero papers uploaded. The audience was wrong — general friends, not researchers who already produce HTML. See `operations/launch/2026-01-beta-logistics.md` for full retrospective.

**Key learning:** Don't ask people to evaluate infrastructure. Show them something they didn't know they could have.

### Current Strategy: Showcase-First Open Beta (March 2026)

**Lead with a compelling artifact, not a product pitch:**
1. GLEE interactive edition (Torres et al., J. Complex Networks 2020) published on Press with explorable figures, responsive layout, mobile-friendly — DONE
2. Next: publish additional showcase papers (Leo's own work, including new research entering active debates)
3. Frame as "interactive edition" of existing work or born-interactive new research — not asking researchers to adopt new infrastructure, showing what's possible
4. Let desire pull people to Press, not pitches push them

**Why this works:**
- No cold start problem — Leo produces the compelling artifact himself
- Positions as researcher showing what's possible, not founder pitching a product
- The interactive figure gap (static PDF vs explorable web) is immediately visceral
- "Interactive edition" framing lowers perceived risk — complement existing publication, not replacement

**Post-GLEE sequence (CURRENT):**
- GLEE interactive edition posted on Bluesky + LinkedIn (DONE March 2026)
- Second showcase paper (born-interactive new preprint) published on Press — DONE March 2026
- First Studio beta waitlist signup from showcase paper exposure (March 2026) — showcase-first strategy generating inbound demand
- Publish additional papers on Press (Leo's own work)
- Social launch for each paper with topic-specific hooks
- Harden for strangers (auth, moderation, abuse prevention)
- Community outreach to Quarto/Typst/Observable/Jupyter communities — people who already have HTML output with no permanent home

**Public beta goals:**
- Social post reaches 5K+ impressions
- 50+ researchers visit Press from the post
- 5+ researchers reach out wanting to publish their own interactive editions
- First non-Leo paper published on Press

### Growth Channels (Organic, Free-Only)

**Primary channels:**
- Published preprints (each paper is a Press advertisement)
- Word-of-mouth in research communities
- GitHub (open source visibility)
- Academic Twitter/Mastodon
- Conference talks (1-2 high-value conferences/year)

**Secondary channels:**
- Technical blog posts (how we built Press, web-native publishing)
- SEO (papers indexed by Google Scholar, search traffic)
- Academic mailing lists (selective, respectful announcements)

**Avoid until proven:**
- Paid advertising (no budget, not cost-effective for academics)
- Product Hunt (consumer bias, low academic presence)
- Mass email campaigns (spam risk)

---

## Technical Constraints & Decisions

### Architecture

**Current stack (as of Q1 2026):**
- Backend: Python 3.11+ / FastAPI / Uvicorn
- Frontend: Jinja2 + HTMX (no JS framework)
- Database: PostgreSQL (Supabase) + SQLAlchemy 2.0 async
- Storage: Tigris (Fly.io S3-compatible) for archive files
- Hosting: Fly.io (single machine, fra region)

**Key architectural decisions:**
- HTML-first rendering (not PDF conversion)
- Embeddable interactive components (Observable, Jupyter, etc.)
- Static export for archival (papers can be downloaded as standalone HTML)
- API-first for AI accessibility (see [Design Constraints](/products/press/technical/design-constraints.md))
- Metrics track both direct usage AND AI-mediated access (see [Metrics Strategy](/products/press/technical/metrics-strategy.md))

### Scalability

**Current capacity:**
- Single server can handle 1,000-5,000 users
- In-memory state limits horizontal scaling
- Need to address before 10,000+ users

**Future needs:**
- Distributed architecture for scale
- CDN for static assets
- Database read replicas

**Decision: Build for validation first, scale later**

### Data & Privacy

**GDPR compliance required** (even for free service):
- Data Processing Agreements (DPAs) with processors
- Privacy Policy and Terms of Service
- User data deletion on request
- Cookie consent
- Data breach notification plan

**Critical before monetization:**
- Execute DPAs with Stripe, hosting providers
- Privacy Policy finalized
- Account deletion UI implemented

---

## Integration Strategy

### Studio Integration

**Goal**: Write in Studio → Publish in Press (one-click workflow)

**Implementation:**
- Studio export format = Press import format
- "Publish to Press" button in Studio
- Metadata transfer (title, authors, abstract)
- Preview before publishing

**Value**: Complete "web-native from start" story

### Reference Manager Integration

**Supported:**
- Zotero export
- Mendeley export
- BibTeX export
- RIS export

**Why**: Researchers need to cite Press papers in their own work

### External Tool Integration (Future)

**Potential:**
- Observable notebooks (embed interactive visualizations)
- Jupyter notebooks (embed code and outputs)
- Quarto documents (native support for Quarto-authored papers)
- Typst documents (if Typst gains traction)

---

## Competitive Positioning

**For comprehensive competitive analysis,** see:
- `/products/press/market/competitive/competitive-positioning.md` - Full strategic positioning document
- `/products/press/market/competitive/competitive-osf.md` - OSF analysis
- `/cross/market/competitive/competitive-curvenote.md` - Curvenote SCMS (relevant to Press AND Studio)

**Quick summary:**
- **arXiv:** Complement (not compete) - "arXiv for PDF, Press for HTML"
- **bioRxiv/medRxiv:** Cross-disciplinary HTML alternative
- **OSF Preprints:** Archive-first, permanent DOIs vs generic infrastructure
- **Curvenote:** Simple archive vs complex platform, different market segments

**Positioning Statement:** "Press is for researchers who want to publish interactive HTML preprints, not static PDFs. Unlike arXiv or bioRxiv, Press embraces the full power of the web for accessible, explorable scholarship."

---

---

## Strategic Risks

### Risk 1: No One Publishes Interactive Papers

**If researchers stick to PDFs and don't use interactive features:**
- Press becomes "yet another preprint server"
- No differentiation from arXiv
- Low retention, low conversion

**Mitigation:**
- Showcase best interactive papers (gallery, featured papers)
- Tutorials on creating interactive content
- Templates for common interactive patterns
- Partner with tools that generate interactive content (Observable, Jupyter)

### Risk 2: Infrastructure Costs Exceed Grant Funding

**If hosting costs grow faster than grant revenue:**
- Sustainability depends entirely on external funding

**Mitigation:**
- Optimize for low marginal cost per paper (CDN, static hosting)
- Pursue arXiv-style voluntary institutional contributions (long-term)
- Grant pipeline: Prototype Fund, NLnet, Sloan Foundation

---

## Success Criteria

### By Q3 2026 (Showcase Validation)

- ✅ GLEE interactive edition published on Press (DONE March 2026)
- ✅ 5+ inbound researchers wanting to publish
- ✅ 20+ papers on Press (seeded + community)
- ✅ 5+ unsolicited testimonials

### By Q4 2026 (Growth Validation)

- ✅ 500+ weekly active users
- ✅ 30%+ monthly retention rate
- ✅ 100+ papers published
- ✅ 10+ unsolicited testimonials
- ✅ 15%+ referral rate (word-of-mouth)

### By Q4 2027

- ✅ 1,000+ active users
- ✅ 200+ papers published
- ✅ Google Scholar indexing confirmed
- ✅ At least one grant award funding ongoing development

---

**Next review**: After second showcase paper launch OR after Q3 2026 growth validation

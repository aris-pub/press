# Strategic Decisions Log - Scroll Press

This document tracks major strategic decisions for Scroll Press.

---

## Decision #1: No Standalone CLI Tool (January 10, 2026)

### Context
Research into target users (Quarto, MyST, Typst) and competitive landscape (Curvenote, arXiv) raised the question: Should Press offer a CLI tool for upload (`press login && press upload`)?

### Decision
**NO standalone CLI tool will be built.**

### Rationale
1. **arXiv precedent**: arXiv (30+ years, millions of papers) is web-only and successfully serves the same technical audience
2. **Archive vs platform**: We're building an archive, not trying to own the authoring workflow
3. **Maintenance burden**: Solo founder cannot sustain cross-platform CLI (Windows, Mac, Linux) + authentication + API versioning
4. **Low upload frequency**: Researchers submit 1-2 papers/year (not daily), so web UI friction is acceptable
5. **Tool ecosystem integration**: Better to integrate with existing CLIs (`quarto publish press`, `myst publish press`) than build our own

### Alternative Approach
- ✅ Excellent web upload UX (drag-and-drop HTML/ZIP)
- ✅ Public API for programmatic access
- ✅ Import from URL (user deploys temp version, Press archives)
- ✅ Documentation for Quarto/MyST workflows
- ✅ Community can build CLI wrapper if demand exists (like arXiv ecosystem)

### Impact on Roadmap
- Removed: "Build Press CLI tool" (previously Phase 4)
- Added: "Public API v1" (Phase 4)
- Added: "Import from URL" (Phase 4)
- Added: "Quarto/MyST integration documentation" (Phase 4)

### References
- `competitive-positioning.md` (detailed analysis)
- C-suite analysis session (January 10, 2026)

---

## Decision #2: Archive-First Product Positioning (January 10, 2026)

### Context
Initial product vision included authoring tools, collaboration features, and "living documents" with discussions. Competitive analysis revealed Curvenote is already building a full platform.

### Decision
**Press is an ARCHIVE, not a platform. Focus on permanent storage + DOIs, not authoring/collaboration.**

### Positioning Statement
> "Scroll Press is what arXiv would be if it was built today - a permanent, trusted archive for HTML-native research."

### In Scope (Archive Functions)
- ✅ Simple HTML upload
- ✅ DOI minting (Crossref)
- ✅ Permanent URLs (immutable, versioned)
- ✅ Metadata (ORCID, ROR, funding)
- ✅ Google Scholar indexing
- ✅ Mobile-optimized reading
- ✅ Accessibility (WCAG)
- ✅ Search & discovery

### Out of Scope (Platform Functions)
- ❌ Authoring tools (WYSIWYG editor, Markdown editor)
- ❌ Real-time collaboration
- ❌ Version control during authoring (use GitHub)
- ❌ CMS features (project management, dashboards)
- ❌ Complex peer review workflows
- ❌ Publisher white-labeling

### Rationale
1. **Clear differentiation**: Curvenote = platform, Press = archive (different categories)
2. **Focus**: Solo founder must focus on one thing done exceptionally well
3. **Trust**: Archival credibility requires institutional backing and permanence guarantees, not feature bloat
4. **Complement existing tools**: Let researchers use Quarto/Typst/Overleaf for authoring, GitHub for collaboration, Press for archival

### Impact on Roadmap
- Removed: "Real-time commenting" (too platform-like)
- Removed: "Peer review workflows" (complex, out of scope)
- Removed: "Team collaboration features"
- Simplified: Basic inline annotations only (Phase 3), not full discussion system

### References
- `competitive-positioning.md` (Section: "What We ARE / What We ARE NOT")
- `product-vision.md` (updated January 10, 2026)

---

## Decision #3: Complement arXiv, Don't Compete (January 10, 2026)

### Context
arXiv has 30+ years of trust, millions of papers, and unbeatable network effects. Initial positioning suggested competing directly.

### Decision
**Position as COMPLEMENT to arXiv, not competitor.**

### Strategy
- Researchers can use BOTH platforms:
  - PDF version → arXiv (established, trusted)
  - HTML version → Press (interactive, web-native)
- "arXiv for your PDF, Press for your interactive version"

### Messaging
- ❌ DON'T say: "We're better than arXiv"
- ❌ DON'T say: "Replace arXiv with Press"
- ✅ DO say: "arXiv was built for PDFs in 1991. Press is built for HTML in 2026."
- ✅ DO say: "Use both: PDF to arXiv, HTML to Press"

### Target Scenarios
1. **HTML-only research**: "arXiv won't accept my interactive Observable notebook"
2. **Dual publishing**: "I submit PDF to arXiv for discoverability, HTML to Press for interactivity"
3. **HTML-first researcher**: "I write in Quarto, HTML is my primary format"
4. **Post-publication enhancement**: "My PDF is on arXiv, interactive companion on Press"

### Rationale
1. **Can't win network effects battle**: arXiv has 30 years head start
2. **Serves different need**: PDF archival vs HTML archival (not mutually exclusive)
3. **Reduces resistance**: Not asking researchers to abandon trusted infrastructure
4. **Expands market**: Dual publishing means more total papers, not zero-sum competition

### Impact
- Changed all marketing messaging from competitive to complementary
- Updated target user scenarios
- Adjusted go-to-market strategy (not "arXiv alternative" but "HTML archive")

### References
- `competitive-positioning.md` (Section: "Competitive Landscape > arXiv")
- `product-vision.md` (Section: "Differentiation")

---

## Decision #4: Curvenote is NOT Direct Competitor (January 10, 2026)

### Context
Initial analysis positioned Curvenote as direct competitor. Deeper research showed they're building a different product category.

### Decision
**Curvenote is a platform, Press is an archive. Different categories, both can succeed.**

### Market Segmentation
- **Curvenote's market**: Authors who need authoring + collaboration + publishing platform (like Notion for research)
- **Press's market**: Authors who need simple archival for HTML output (like arXiv for HTML)

### Differentiation
| Dimension | Curvenote | Press |
|-----------|-----------|-------|
| **Category** | Content management platform | Archive |
| **Workflow** | Author in our platform | Archive output from any tool |
| **Pricing** | Custom/"book a demo" | Transparent/public |
| **Focus** | Publishers + institutions | Individual researchers |
| **Complexity** | High (full-featured) | Low (simple upload) |

### Can Both Coexist?
YES - serving different needs:
- Author writes in Curvenote → Can archive final output on Press
- Author writes in Quarto → Archives on Press (Curvenote doesn't serve this user)
- Publisher uses Curvenote for journals → Press not competing

### Strategic Implications
1. **Don't compete on features**: Curvenote will always have more features (full team, funding)
2. **Compete on values**: Simplicity, transparency, open source, researcher-first
3. **Target different segments**: Individual researchers (not publishers/institutions)
4. **Emphasize tool-agnostic**: Accept Quarto output (Curvenote is MyST-focused)

### References
- `competitive-positioning.md` (Section: "Competitive Landscape > Curvenote")

---

## Decision #5: Funding Model (arXiv-Inspired) (January 10, 2026)

### Context
Initial monetization strategy focused on freemium SaaS (vanity URLs, premium features). Research into arXiv's sustainability model revealed alternative approach.

### Decision
**Hybrid model: Free forever core + optional premium + institutional membership (long-term)**

### Phases

**Phase 1: Bootstrap + Grants (2026-2027)**
- Prototype Fund: €47.5k (non-dilutive)
- NLnet Foundation: €5-50k
- Foundation grants: Sloan, Mozilla
- Core service: FREE (validate PMF without revenue pressure)

**Phase 2: Free forever (February 2026 decision)**

**⚠️ Superseded:** Press will have no paid features. All features are free forever.
Pricing model explored here (pay-per-paper, reading subscription, Pro bundle) was abandoned February 2026. See `strategy/vision.md` for current funding model.

Press is sustained by grants and donations, not user revenue.

### Key Principles
1. **Core archival = public good** (always free, like arXiv)
2. **No premium tier** (Press never monetizes)
3. **Institutional = sustainability** (long-term funding model)

### Why This Works
1. **Validation without monetization pressure**: Can launch free, validate PMF
2. **Aligns with mission**: Archival as public infrastructure
3. **Universities understand**: Already fund arXiv, can fund Press
4. **Sustainable**: Not dependent on VC growth expectations

### Impact
- Removed revenue pressure from 2026 launch
- Focus on user adoption, not conversion
- Apply for grants immediately (Prototype Fund)
- Build institutional partnership pipeline

### References
- `competitive-positioning.md` (Section: "Funding Model")
- `product-vision.md` (Section: "Monetization Strategy")

---

## Decision #6: Unified Platform with Subject Categories (January 10, 2026)

### Context
OSF competitive analysis revealed that OSF suspended its generalist preprint server (August 2025) while 14 community-specific servers (PsyArXiv, SocArXiv, etc.) remain thriving. This raised the question: Should Press launch as separate discipline-specific instances (PsychPress, BioPress, etc.) or as unified platform?

### Decision
**Unified platform with subject categories (arXiv model), NOT separate community-specific instances (OSF model).**

### Rationale

**Why OSF's Federated Model Works for Them:**
1. **Moderation**: Discipline communities self-govern with shared quality standards
2. **Identity**: Researchers identify with disciplines ("I'm a psychologist" > "I'm a researcher")
3. **Trust**: Community moderators understand field-specific norms

**Why Press Should Do Unified Platform Instead:**
1. **Solo founder constraint**: Cannot maintain 14 separate instances, moderation teams, and community partnerships
2. **HTML-first is the differentiator**: Press's value is "HTML preprints with DOIs" not discipline-specific archiving
3. **arXiv proves generalist works**: 30+ years, millions of papers, unified platform with subject categories
4. **Network effects compound better**: All researchers checking Press > fragmented communities
5. **Interdisciplinary research**: Computational biology, digital humanities span multiple disciplines

**OSF's Real Lesson:** Generalist failed not because "generalist is bad" but because of unmoderated content with unclear quality standards. arXiv, Zenodo, Figshare are all successful generalist platforms with proper moderation.

### Implementation Approach

**Phase 1 (Q1 2026 Launch):**
- Single platform: press.scroll.pub
- Basic subject categories: CS, Biology, Physics, Math, Social Sciences, Humanities, Other
- Author-selected categorization
- Automated moderation (HTML validation, spam detection)

**Phase 2 (Post-100 Papers):**
- Analyze adoption patterns by discipline
- Add subject-specific RSS feeds
- Recruit discipline advisors (volunteer, lightweight)
- Enhance categorization based on usage

**Phase 3 (If Needed, 2027+):**
- Community moderation boards for active categories
- Discipline-specific submission guidelines
- Still unified platform, shared infrastructure

### Impact on Roadmap
- Confirmed: Single unified platform (not separate instances)
- Added: Subject categorization system (Phase 1)
- Added: Category-specific RSS feeds (Phase 2)
- Added: Optional community governance (Phase 3, if needed)

### References
- `competitive-osf.md` (OSF analysis, community server insights)
- arXiv model (30+ years successful generalist with categories)
- OSF generalist server suspension (August 2025)

---

## Decision #7: Showcase-First Launch Strategy (March 2026)

### Context
Friends & family beta (Feb 3 – Mar 9, 2026) resulted in YELLOW outcome: product worked, no critical bugs, but zero papers uploaded. Participants were general friends with no HTML content and no intrinsic motivation. The product wasn't the problem; the audience was wrong.

Asking people to "evaluate infrastructure" generates obligation, not desire. A different approach is needed.

### Decision
**Lead with a compelling showcase artifact, not a product pitch. Publish an interactive edition of Leo's own paper (GLEE) as the flagship demonstration.**

### Strategy
1. Take GLEE (Torres et al., J. Complex Networks, 2020) and produce a full interactive edition with explorable figures
2. Post on socials with hook: "What if papers had interactive figures?"
3. Frame as "interactive edition" — complement to existing publication, not replacement
4. Let the artifact create desire; don't pitch infrastructure
5. Follow up by seeding the archive with more of Leo's own work
6. Then harden for strangers and do community outreach to HTML tool communities (Quarto, Typst, Observable, Jupyter)

### Rationale
1. **No cold start problem**: Leo produces the compelling artifact himself, no dependency on others
2. **Desire over obligation**: Social post creates "I want this" not "I'll try this as a favor"
3. **Researcher, not founder**: Leo posting his own interactive paper positions as researcher showing what's possible, not founder pitching a product
4. **Visceral gap**: The difference between a static PDF figure and an explorable interactive version is immediately obvious in a 3-second scroll
5. **Low-risk framing**: "Interactive edition of published work" lowers perceived risk vs "publish on new platform"

### Impact
- Replaced generic "public launch" plan with showcase-first sequence
- Updated social media strategy around GLEE showcase post
- Changed target audience from "general researchers" to "researchers who already produce HTML and have no permanent home for it"
- Deferred broad community outreach until after showcase validates the narrative

### References
- `operations/launch/2026-01-beta-logistics.md` (YELLOW outcome and next steps)
- `strategy/roadmap.md` (updated Go-to-Market section)

---

## Document Changelog

### January 10, 2026
- Created document
- Added Decision #1: No CLI tool
- Added Decision #2: Archive-first positioning
- Added Decision #3: Complement arXiv
- Added Decision #4: Curvenote differentiation
- Added Decision #5: Funding model
- Added Decision #6: Unified platform with subject categories

### March 16, 2026
- Added Decision #7: Showcase-first launch strategy (post-beta pivot)

---

**Owner**: Leo Torres
**Review Cadence**: After major strategic decisions
**Next Review**: After second showcase paper launch results (GLEE published March 2026)

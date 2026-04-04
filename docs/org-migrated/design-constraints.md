# Press Design Constraints

Core technical and architectural constraints that shape Press product decisions.

---

## AI-Mediated Access Pattern (Added Feb 2026)

**Context:** [Scholarly Kitchen research](https://scholarlykitchen.sspnet.org/2026/02/12/guest-post-theres-an-elephant-in-the-room-but-not-in-your-usage-reports/) shows researchers increasingly access scholarly content through AI intermediaries (ChatGPT, Claude, Scite, Consensus, Elicit) rather than direct platform visits. Traditional usage metrics miss this entirely.

**Design Constraint:** Press must assume AI tools as primary access pattern, not direct human browsing.

### Implications for Press Architecture

**1. Content Structure Must Be Machine-Readable**
- RSM's semantic markup is strategic advantage over PDF-first competitors
- Metadata must be comprehensive and structured (authors, affiliations, keywords, citations, DOIs)
- Semantic structure (sections, equations, figures, cross-references) must be explicitly labeled
- AI tools should be able to extract specific content types programmatically

**2. API-First Architecture**
- Design public API for programmatic access before building web UI
- API should expose semantic queries, not just document retrieval
- Consider MCP (Model Context Protocol) server for AI tool integration
- See [MCP Integration Ideas](/ideas/mcp-integration.md) for evaluation criteria

**3. Instrumentation for AI Usage Metrics**
- Track API queries as first-class usage metrics (not secondary to page views)
- Log: queries, papers accessed, content types extracted, source tools
- New impact metrics: "Papers accessed by AI tools serving X researchers/month"
- Traditional COUNTER metrics will undercount actual usage

**4. Citation and Attribution Infrastructure**
- Ensure AI tools can properly cite Press papers (DOI, permanent URLs)
- Provide citation metadata in machine-readable formats (BibTeX, CSL-JSON, etc.)
- Track citation provenance when possible (which AI tool cited which paper)

**5. Rate Limiting and Access Tiers**
- Free tier: Individual researchers via AI assistants (reasonable rate limits)
- Paid tier: Enterprise/industrial discovery tools (Scite, Consensus, Elicit)
- Align with Aris values: essential individual use free forever, charge for scale
- See [Press Roadmap](/products/press/strategy/roadmap.md) for business model details

### What This Does NOT Mean

**We are NOT building:**
- AI-generated summaries or synthesis (Press is archive, not AI tool)
- AI recommendation engine for discovery
- AI writing assistance in Press interface

**We ARE building:**
- Infrastructure that makes Press content maximally accessible to AI tools
- Metrics that capture AI-mediated usage accurately
- APIs that enable AI tools to query and cite Press papers properly

### Decision Points

**Before Press V1 Launch:**
- [ ] Evaluate MCP server feasibility (see [MCP Integration](/ideas/mcp-integration.md))
- [ ] Design API instrumentation strategy
- [ ] Document rate limiting policy
- [ ] Update positioning: "Most AI-accessible preprint server"

**Post-Launch (if demand exists):**
- [ ] Enterprise API tier for discovery tools
- [ ] Enhanced semantic query capabilities
- [ ] Partnership with discovery tools (Scite, Consensus, Elicit)

---

## Other Design Constraints

(Additional constraints to be documented as they emerge)

### Archive-First, Not Platform

Press is an archive (permanent storage, simple retrieval) not a platform (feeds, recommendations, engagement features).

See [Competitive Positioning](/products/press/market/competitive/competitive-positioning.md) for details.

### Static Content, No Build Step

Papers are static HTML/RSM, not dynamically generated. No server-side rendering, no build process per paper.

### Security: User Content is Untrusted

All uploaded HTML must be sanitized. See [Security Sanitization Spec](/products/press/technical/security-sanitization-spec.md).

---

**Related Documentation:**
- [AI-Mediated Access Research](/cross/market/research/2026-02-ai-mediated-access.md)
- [MCP Integration Ideas](/ideas/mcp-integration.md)
- [Press Roadmap](/products/press/strategy/roadmap.md)

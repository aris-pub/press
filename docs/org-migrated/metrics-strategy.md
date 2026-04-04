# Press Metrics Strategy

How Press measures usage, impact, and value in an AI-mediated research landscape.

---

## The Measurement Problem

**Traditional approach (COUNTER metrics):**
- Page views, PDF downloads, unique visitors
- Assumes researchers visit publisher platforms directly
- Works for 2010s-era research consumption

**Current reality (2026+):**
- Researchers access content through AI intermediaries (ChatGPT, Claude, Scite, Consensus, Elicit)
- Traditional metrics capture <50% of actual usage (and declining)
- "Zero-click searches" deliver value without platform visits

**Source:** [Scholarly Kitchen: AI-Mediated Access](https://scholarlykitchen.sspnet.org/2026/02/12/guest-post-theres-an-elephant-in-the-room-but-not-in-your-usage-reports/) (Feb 2026)

**Design constraint:** Press must measure AI-mediated usage as first-class metrics, not afterthoughts.

---

## Metrics Framework

### Tier 1: Direct Human Usage (Traditional Metrics)

**What we measure:**
- Page views (paper detail pages, HTML rendered papers)
- Unique visitors (daily, weekly, monthly)
- Time on page
- Referral sources

**Why it matters:**
- Still relevant for human readers who browse Press directly
- Comparable to competitors (arXiv, bioRxiv)
- Expected by grant funders (they understand these metrics)

**Tools:**
- Privacy-respecting analytics (Plausible or self-hosted)
- No tracking cookies, respect DNT headers
- Aggregate data only, no individual tracking

### Tier 2: AI-Mediated Usage (New Primary Metric)

**What we measure:**
- API queries (search, paper retrieval, metadata access)
- Papers accessed via API/MCP by tool type (Claude, ChatGPT, Scite, etc.)
- Content types extracted (full text, abstracts, citations, equations, figures)
- Unique AI tools accessing Press per month
- Estimated researcher reach (if AI tools share usage data)

**Why it matters:**
- Captures actual usage invisible to traditional metrics
- Demonstrates value even when researchers don't visit directly
- Future-proofs impact narrative for grants/funders

**Implementation:**
- Log all API requests with metadata (tool type, content accessed, timestamp)
- Aggregate by tool, paper, content type
- Privacy-preserving: don't log individual researcher queries (log tool-level patterns)

**Instrumentation requirements:**
- API request logging (built into Press V1 API layer)
- MCP server usage tracking (if MCP server built)
- Rate limiting infrastructure (doubles as usage counter)

### Tier 3: Impact Metrics (Outcome-Focused)

**What we measure:**
- Citations in AI-generated content (if trackable)
- Papers indexed by discovery tools (Scite, Consensus, Elicit)
- Author-reported outcomes (grants funded, collaborations started)
- Papers that migrate to peer-reviewed journals (Press → journal pipeline)

**Why it matters:**
- Demonstrates research impact beyond consumption
- Shows Press enables research progress (not just hosting)
- Qualitative stories for grant narratives

**Implementation:**
- Annual author survey (opt-in, voluntary)
- Citation tracking via DOI metadata
- Discovery tool partnerships (ask for indexing stats)

---

## Reporting Framework

### Monthly Metrics Dashboard (Internal)

**Core metrics:**
- Total papers hosted
- New papers this month
- Direct page views (Tier 1)
- API queries (Tier 2)
- AI tools accessing Press (Tier 2)
- Top papers by combined usage (direct + API)

**Use case:** Founder monitors health, identifies growth patterns

### Quarterly Grant Report (External)

**Narrative structure:**
1. **Reach:** "Press served X researchers directly and Y researchers via AI tools"
2. **Usage:** "Z papers accessed via direct browsing + API queries"
3. **Impact:** "Papers from Press cited in A publications, indexed by B discovery tools"
4. **Growth:** "Month-over-month increase in AI-mediated access: C%"

**Use case:** Demonstrate value to funders (grants, institutional members)

### Annual Impact Report (Public)

**Highlights:**
- Total papers, authors, institutions
- Combined usage (direct + AI-mediated)
- Top discovery use cases
- Author testimonials and outcomes
- Year-over-year growth

**Use case:** Community transparency, marketing, researcher trust

---

## Privacy and Ethics

### What We Track

**Aggregate patterns only:**
- "100 API queries from Scite this month"
- "Paper X accessed 50 times via direct + 200 times via API"
- "AI tools retrieved 1,000 abstracts, 300 full texts this week"

**Never individual researchers:**
- No tracking of which researcher queried what via AI tools
- No personally identifiable information in API logs
- No tracking cookies on Press website

### Data Retention

- API logs: 12 months (rolling window)
- Aggregate metrics: Retained indefinitely
- Individual IP addresses: Not logged

### Alignment with Aris Values

- Transparency: Metrics methodology documented publicly
- Privacy: Aggregate usage only, no individual tracking
- Open: Consider publishing aggregate API usage data for research

---

## Implementation Timeline

### V1 Launch (Immediate)

**Must have:**
- [ ] Privacy-respecting analytics for direct usage (Plausible or self-hosted)
- [ ] API request logging infrastructure
- [ ] Basic rate limiting (doubles as usage counter)
- [ ] Monthly metrics dashboard (internal)

**Nice to have (defer if time-constrained):**
- [ ] MCP server usage tracking (only if MCP server built)
- [ ] Discovery tool indexing tracking

### Post-Launch (3-6 months)

**After beta validation:**
- [ ] Quarterly grant report template
- [ ] Author survey for impact metrics
- [ ] Citation tracking via DOI metadata
- [ ] Discovery tool partnerships

### Future (12+ months)

**If Press scales:**
- [ ] Public annual impact report
- [ ] Real-time metrics API for researchers ("see who's accessing your paper")
- [ ] Enhanced AI usage analytics (content type trends, tool patterns)

---

## Open Questions

**1. Should we share API usage data with authors?**
- Pro: Transparency, authors see full impact (direct + AI-mediated)
- Con: Privacy concerns if AI tools reveal usage patterns
- Decision: Deferred until V2 (validate demand first)

**2. How to handle attribution when AI tools don't cite sources?**
- Problem: AI synthesizes without attribution, researchers don't know source was Press
- Mitigation: Encourage AI tools to cite properly, provide citation metadata
- Long-term: Industry-wide standards for AI citation attribution

**3. What's the baseline for "good" AI-mediated usage?**
- No comparable data exists (Press is early)
- Hypothesis: AI usage should exceed direct usage by 2027 (3-5x ratio)
- Validate during beta, adjust expectations

**4. Should Press charge AI tools for usage (per action item #7)?**
- Free tier: Individual researchers via AI assistants (rate-limited)
- Paid tier: Enterprise discovery tools (Scite, Consensus, Elicit)
- Metrics infrastructure enables tiered pricing (track usage, enforce limits)

---

## Success Criteria

**By Q4 2026 (6 months post-launch):**
- 500+ papers indexed
- 10,000+ combined usage events/month (direct + API)
- 3+ discovery tools actively accessing Press
- Metrics dashboard operational and useful

**By Q4 2027 (18 months post-launch):**
- AI-mediated usage exceeds direct usage (validation of market shift)
- Quarterly grant reports demonstrate growing impact
- Author survey shows Press enables research outcomes

---

**Related Documentation:**
- [AI-Mediated Access Research](/cross/market/research/2026-02-ai-mediated-access.md)
- [Design Constraints](/products/press/technical/design-constraints.md)
- [Press Roadmap](/products/press/strategy/roadmap.md)

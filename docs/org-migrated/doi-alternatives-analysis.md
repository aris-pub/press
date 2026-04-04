# Free DOI Minting Alternatives - Complete Analysis

**Date**: January 10, 2026
**Context**: Crossref membership ($275/year + $1/DOI) is cost-prohibitive during bootstrap phase. Need free alternative for Q1 2026 launch.

**Critical Requirement**: DOI minting is P0 - WITHOUT DOIs, Press is just "fancy GitHub Pages" and not a credible archive.

**Key Clarification**: DataCite is a DOI **registration agency** (like Crossref), not a service you can directly use. To get DataCite DOIs, you must either:
1. Become a DataCite member (expensive: €2,000-5,000/year)
2. Use a service that's already a DataCite member (like Zenodo)

So "Zenodo vs DataCite" is not the right comparison - Zenodo **uses** DataCite infrastructure to mint DOIs for free.

---

## All Free DOI Minting Options

### Option 1: Zenodo (CERN) ⭐ RECOMMENDED

**What it is**: Open-access repository operated by CERN, uses DataCite
**DOI prefix**: 10.5281
**Cost**: FREE (EU/CERN funded)
**API**: Full REST API
**Use case**: Research outputs, datasets, preprints, software

**How to use**:
- Register account → get API token → create deposits via API → mint DOIs
- No approval needed, immediate access
- Can mint DOIs for content hosted elsewhere (configurable landing page URL)

**Technical Details**:
- **API**: Full REST API available (create deposits, mint DOIs programmatically)
- **Sandbox**: Yes (sandbox.zenodo.org for testing)
- **Storage**: Free unlimited storage
- **Authority**: DataCite (equally valid as Crossref)

**Pros**:
✅ **Zero cost** - completely free forever (CERN/EU commitment)
✅ **Immediate availability** - can start today, no approval needed
✅ **Excellent API** - well-documented REST API, sandbox environment
✅ **Credible provider** - CERN-backed, 1M+ DOIs minted (proven credibility)
✅ **Google Scholar compatible** - DataCite DOIs are indexed
✅ **Flexible metadata** - can redirect DOI to Press URLs
✅ **Storage backup** - content also stored on Zenodo (redundancy)

**Cons**:
❌ **Different DOI prefix** - 10.5281 (Zenodo) vs 10.XXXXX (custom Crossref)
❌ **"Via Zenodo" branding** - DOI metadata shows Zenodo as publisher
❌ **Less control** - can't customize DOI suffix structure
❌ **DataCite vs Crossref** - different metadata standards (minor difference)

**Implementation Effort**: 3-5 days

**Example DOI**: `10.5281/zenodo.1234567` → resolves to `https://press.scroll.pub/papers/[hash]`

---

### Option 2: Open Science Framework (OSF)

**What it is**: Open-source research platform (Center for Open Science)
**DOI prefix**: 10.17605 (OSF Storage via DataCite) or 10.31219 (OSF Preprints via Crossref)
**Cost**: FREE (non-profit, grant-funded)
**API**: Full REST API
**Use case**: Preprints, datasets, project materials

**How to use**:
- OSF Preprints: Upload preprint → auto-DOI via Crossref (10.31219)
- OSF Storage: Upload any file → DataCite DOI (10.17605)
- API allows programmatic creation

**Pros**:
✅ **Crossref DOIs** - OSF Preprints use Crossref (academic standard for preprints)
✅ **Zero cost** - non-profit mission, free forever
✅ **Excellent API** - well-documented
✅ **Preprint-focused** - designed specifically for preprints
✅ **Google Scholar indexed**
✅ **Academic credibility** - COS is well-known in research community

**Cons**:
❌ **Partnership dependency** - may require formal agreement with COS
❌ **Less control** - reliant on OSF infrastructure
❌ **"Via OSF" branding** - DOI metadata shows OSF as publisher
❌ **URL resolution** - DOI likely resolves to OSF, not Press directly
❌ **Uncertain availability** - need to confirm COS will support this use case
❌ **Competitive overlap** - Would Press just be duplicating OSF's preprint service?

**Implementation Effort**: 1-2 weeks (includes partnership outreach)

**Example DOI**: `10.31219/osf.io/abc123` → resolves to OSF landing page

---

### Option 3: Figshare

**What it is**: Commercial research repository (Digital Science), uses DataCite
**DOI prefix**: 10.6084 or 10.25384
**Cost**: FREE for individuals (freemium model)
**API**: Full REST API available
**Use case**: Datasets, figures, preprints, posters

**Pros**:
✅ Free for individual researchers
✅ Full API access
✅ Well-known in academia
✅ DataCite DOIs

**Cons**:
❌ **Commercial company** - sustainability risk (Digital Science)
❌ **Freemium model** - may limit features
❌ Less control over metadata
❌ DOI likely resolves to Figshare, not Press
❌ API integration more complex than Zenodo

**Comparison to Zenodo**: Zenodo is better - non-profit, simpler API, clearer terms

---

### Option 4: Harvard Dataverse

**What it is**: Open-source research data repository, uses DataCite
**DOI prefix**: 10.7910 (Harvard) or institution-specific
**Cost**: FREE (Harvard-hosted instances)
**API**: Full REST API

**Pros**:
✅ Free via Harvard infrastructure
✅ Academic credibility (Harvard-backed)
✅ Open-source platform

**Cons**:
❌ **Designed for datasets, not preprints**
❌ May require Harvard affiliation or approval
❌ API access unclear for external projects
❌ DOI resolves to Dataverse landing page
❌ Less appropriate for HTML preprints

**Comparison to Zenodo**: Zenodo is better - designed for preprints, no approval needed

---

### Option 5: PubPub (MIT Media Lab)

**What it is**: Open-source publishing platform (Knowledge Futures Group)
**DOI prefix**: Uses Crossref (via MIT Press partnership)
**Cost**: FREE for hosted communities
**API**: GraphQL API available

**Pros**:
✅ Free, open-source
✅ MIT backing
✅ Uses Crossref (not DataCite)
✅ Designed for scholarly publishing

**Cons**:
❌ DOI resolves to PubPub, not Press
❌ Would create dependency on PubPub infrastructure
❌ Unclear if supports external API-based DOI minting
❌ Less established than Zenodo

**Comparison to Zenodo**: Zenodo is better - clearer API, established service

---

### Option 6: University Library Crossref Sponsorship

**Overview**: Some university libraries hold Crossref memberships and sponsor DOI minting for affiliated repositories/projects.

**How It Would Work**:
1. Approach German university libraries (FU Berlin, TU Berlin, etc.)
2. Request Crossref sponsorship for Press
3. Use their membership to mint DOIs under their prefix
4. Share metadata/reports with sponsor library

**Pros**:
✅ **Crossref DOIs** - proper academic DOI prefix
✅ **Institutional backing** - university association adds credibility
✅ **Free during bootstrap** - no upfront cost
✅ **Potential partnership** - could lead to institutional adoption

**Cons**:
❌ **Requires institutional relationship** - may be difficult as solo founder
❌ **Uncertain timeline** - academic bureaucracy is slow (2-6 months)
❌ **Dependency** - reliant on library partnership
❌ **May require affiliation** - might need to be student/staff

**Implementation Effort**: 2-6 months (partnership negotiation), uncertain success probability

---

### Options NOT Recommended

**Internet Archive Scholar**: Experimental, not designed for new preprint DOI minting, unclear API

**ScienceOpen**: Designed for curated collections, not individual preprints, unclear business model

**arXiv**: Does NOT mint DOIs - papers get arXiv IDs (arXiv:2401.12345), not DOIs

---

## Comparison Matrix

| Service | DOI Agency | Prefix | API Quality | Preprint-Focused | No Approval | Best Fit | Timeline |
|---------|-----------|--------|-------------|-----------------|-------------|----------|----------|
| **Zenodo** | DataCite | 10.5281 | ⭐⭐⭐⭐⭐ | ✅ | ✅ | **YES** | Immediate |
| OSF Preprints | Crossref | 10.31219 | ⭐⭐⭐⭐ | ✅ | ⚠️ | Maybe | 1-2 weeks |
| Figshare | DataCite | 10.6084 | ⭐⭐⭐⭐ | ⚠️ | ✅ | No | Immediate |
| Dataverse | DataCite | 10.7910 | ⭐⭐⭐ | ❌ | ❌ | No | Uncertain |
| PubPub | Crossref | Via MIT | ⭐⭐⭐ | ✅ | ⚠️ | No | Uncertain |
| University | Crossref | Custom | N/A | ✅ | ❌ | No | 2-6 months |

---

## Direct Membership Costs (For Reference)

### Crossref Membership (If/When Funded)
- **Cost**: $275/year (sponsor level) + $1/DOI
- **Year 1 estimate**: $275 + (100 papers × $1) = $375
- **Year 2 estimate**: $275 + (500 papers × $1) = $775
- **Viable**: With Prototype Fund (€47.5k), easily affordable

### DataCite Direct Membership
- **Cost**: €2,000-5,000/year (Direct Member fees)
- **Requirements**: Organization (not individual), annual fees, reporting
- **Why NOT viable now**: Same cost problem as Crossref, just different agency
- **Why viable LATER**: Prototype Fund could cover this

---

## RECOMMENDED STRATEGY: Hybrid Zenodo → Crossref

### Overview
Use free service (Zenodo) for bootstrap phase, migrate to own Crossref membership post-funding.

### Implementation Timeline

**Phase 1 (Q1 2026): Launch with Zenodo**
- Implement Zenodo integration (3-5 days)
- Launch Press with free DataCite DOIs (10.5281)
- Validate PMF with 100 papers, 40% retention
- Zero cost, zero dependency, immediate availability

**Phase 2 (Q2 2026): Grant Applications**
- Use "100 papers with DOIs" as evidence in applications
- Apply for Prototype Fund (€47.5k)
- Apply for NLnet Foundation (€5-50k)

**Phase 3 (Q4 2026 or 2027): Crossref Membership**
- Use grant funds for Crossref membership
- Apply for custom DOI prefix (10.XXXXX/press.YYYY)
- New papers get Press DOIs
- Old Zenodo DOIs remain valid (DOIs are permanent)

### Rationale

**Why Zenodo for bootstrap:**
- Zero cost, zero dependency, immediate availability
- Proper DOI minting (DataCite is equally valid as Crossref)
- CERN backing = credibility, 1M+ DOIs minted
- Can implement in 3-5 days = doesn't block launch
- Excellent API documentation with sandbox

**Why NOT OSF:**
- Requires partnership approval (uncertain outcome, adds 1-2 weeks)
- Less control over metadata/branding
- Creates dependency on COS policy
- May compete with OSF's own preprint service

**Why NOT university sponsorship:**
- Months of negotiation, uncertain outcome
- Blocks launch while waiting for institutional approval
- Solo founder may not have leverage

**Why migrate to Crossref later:**
- Custom DOI prefix (10.XXXXX/press.YYYY) = better branding
- Full control over metadata
- Academic standard (Crossref > DataCite for preprints)
- Grants will fund this transition
- $275/year is trivial with €47.5k funding

### Precedent

This is exactly how many archives started:
- **bioRxiv**: Started with existing infrastructure, later got own prefix
- **medRxiv**: Leveraged existing infrastructure before independence
- **Zenodo itself**: Uses DataCite, highly credible, 1M+ DOIs minted

### Handling Mixed DOI Prefixes

**Concern**: Early papers have 10.5281, later papers have custom prefix

**Response**:
- DOIs are permanent - old DOIs remain valid forever
- Many archives have mixed prefixes (organizational mergers, transitions)
- Researchers care about having A DOI, not which prefix
- Communicate transparently: "We started with Zenodo, now have our own prefix"

### Communication Strategy

Be transparent with users:
- "Press mints DOIs via Zenodo (CERN/DataCite infrastructure)"
- "All DOIs are permanent and citable"
- "As Press grows, we'll join Crossref for custom DOI prefix"

---

## Implementation Plan: Zenodo Integration

### Phase 1: Setup (Day 1)
1. Create Zenodo account
2. Generate API token
3. Test sandbox.zenodo.org
4. Verify DOI minting flow

### Phase 2: Backend Integration (Days 2-3)

Create `/press/app/integrations/zenodo.py`:
- `create_deposit()` - create Zenodo record
- `upload_files()` - upload HTML to Zenodo
- `publish_deposit()` - finalize and mint DOI
- `get_doi()` - retrieve minted DOI

Database migration:
- Add `doi` field to `scrolls` table (nullable, unique)
- Add `zenodo_record_id` for tracking

Update `/press/app/routes/scrolls.py`:
- After publish, call Zenodo API
- Store DOI in database
- Handle API errors gracefully

### Phase 3: Frontend Updates (Day 4)

Update `/press/app/templates/scroll.html`:
- Display DOI prominently
- Add Schema.org `sameAs` with DOI URL
- Add citation helper ("Cite this work: [DOI]")

Update `/press/app/templates/index.html`:
- Show DOI badge on paper cards
- Add "All papers get permanent DOIs" messaging

### Phase 4: Testing (Day 5)
1. Test end-to-end flow in sandbox
2. Verify DOI resolution
3. Test Google Scholar metadata
4. Error handling (API failures, network issues)

### Phase 5: Production Deploy
1. Switch to production Zenodo API
2. Mint first Press DOI
3. Monitor for 48 hours
4. Document in launch checklist

---

## Why NOT Defer DOIs

### Option: Launch Press WITHOUT DOIs initially, add DOI minting post-funding

### Analysis: ❌ **DO NOT DO THIS**

**Why this is wrong:**
1. **Not a credible archive** - "preprint without DOI" = blog post, not citable research
2. **Trust issue** - researchers expect DOIs from day 1 on any preprint server
3. **Retroactive DOI minting** - assigning DOIs to already-published papers is messy
4. **Competitive disadvantage** - Curvenote has DOIs, OSF has DOIs, bioRxiv has DOIs
5. **Breaks promise** - product-vision.md says "Upload HTML, get DOI, done"

**CPO quote from analysis:**
> "Launching without DOIs = not a credible archive (just HTML hosting). Without DOIs, Press IS just fancy GitHub Pages."

---

## DataCite vs Crossref: Does It Matter?

**Reality**: Most researchers don't know the difference
- Both are valid, citable, Google Scholar indexed
- Both are DOI registration agencies (equally authoritative)
- Crossref is more common for preprints (journal tradition)
- DataCite is common for data/software (repository tradition)

**For Press**:
- Bootstrap: DataCite via Zenodo (free, immediate)
- Mature: Crossref with custom prefix (branded, controlled)
- Both approaches are credible and widely accepted

---

## Open Questions

1. **OSF investigation**: Worth reaching out to COS to ask about using OSF Preprints DOIs?
   - Pro: Crossref DOIs (more "standard")
   - Con: Adds 1-2 weeks uncertainty, creates dependency

2. **Budget clarification**: Is $275 unaffordable NOW, or forever?
   - If NOW: Zenodo → Crossref hybrid makes sense
   - If FOREVER: Zenodo is permanent solution (perfectly acceptable)

---

## Final Recommendation

**Zenodo is the best free DOI service for Press launch.**

After researching ALL free alternatives, Zenodo wins because:

1. **No approval needed** - Register and start minting DOIs immediately
2. **Best API** - Well-documented REST API, sandbox environment, easy integration
3. **Proven scale** - 1M+ DOIs minted, trusted by research community
4. **Permanent commitment** - CERN/EU funding ensures long-term sustainability
5. **Preprint-appropriate** - Designed for research outputs including preprints
6. **Flexible metadata** - Can configure DOI to resolve to Press URLs
7. **Google Scholar compatible** - DataCite DOIs are indexed
8. **Zero dependencies** - No partnership, approval, or special relationship needed
9. **Free forever** - Not dependent on grants or business model changes

**Action Items**:
1. Confirm hybrid strategy (Zenodo now → Crossref post-funding)
2. Implement Zenodo integration (3-5 days)
3. Launch Press in Q1 2026 with DOI minting enabled
4. Apply for Prototype Fund using "100 papers with DOIs" as validation
5. Join Crossref post-funding for custom prefix

**Bottom Line**: Zenodo provides credible, free DOI minting that unblocks launch. Later migration to Crossref provides branding upgrade. This is pragmatic, cost-effective, and standard practice for bootstrapped archives.

---

**Decision Authority**: Leo Torres (Founder)
**Status**: Awaiting decision
**Blocking**: Q1 2026 launch (P0)

# Press HTML Sanitization Specification

# Executive Summary
This document specifies the HTML sanitization and JavaScript execution security model for Preview Press MVP. The approach prioritizes user safety while preserving the interactive capabilities that differentiate web-native research from static PDFs. The solution uses Content Security Policy with nonce-based script execution combined with server-side HTML sanitization.

## Security Architecture

### Primary Defense: Nonce-Based Script Execution
**Core Principle**: Only server-approved JavaScript executes in user browsers. Each page load generates a unique, unpredictable nonce that acts as a cryptographic token for script execution authorization.

**Implementation Flow**:
1. Server generates cryptographically secure random nonce per request
2. Approved scripts receive the nonce attribute during HTML processing
3. Content Security Policy header restricts execution to nonce-bearing scripts
4. Browser enforces policy, blocking any non-nonce scripts including XSS payloads

**Why This Works**: Attackers cannot predict or forge valid nonces, making XSS injection ineffective even if HTML parsing vulnerabilities exist.

### Secondary Defense: HTML Sanitization
**Server-side sanitization** removes dangerous HTML elements and attributes while preserving scientific formatting. Uses allowlist approach - only explicitly permitted tags and attributes pass through.

**CSS validation** ensures inline styles contain only safe properties and values, preventing CSS-based attacks or layout manipulation.

## MVP Supported Content

### HTML Elements (Allowlist)
**Document Structure**: html, head, body, title, meta, link
**Typography**: h1-h6, p, br, hr, strong, em, u, sub, sup, small, mark
**Lists**: ul, ol, li, dl, dt, dd
**Tables**: table, thead, tbody, tfoot, tr, th, td, caption, colgroup, col
**Semantic Elements**: article, section, aside, header, footer, main, nav, div, span
**Media**: img, figure, figcaption, svg (with restrictions)
**Links**: a (href validation required)
**Code**: pre, code, kbd, samp
**Quotes**: blockquote, cite, q
**Scientific**: abbr, dfn, time, data

### CSS Properties (Allowlist)
**Typography**: font-family, font-size, font-weight, font-style, color, text-align, line-height, text-decoration
**Layout**: margin, padding, width, height, max-width, max-height, display, vertical-align
**Visual**: background-color, border, border-radius, box-shadow
**Tables**: border-collapse, border-spacing, table-layout

### JavaScript Libraries (Curated)
**Data Visualization**: D3.js, Plotly.js, Chart.js - served from Aris CDN with integrity hashes
**Mathematical Content**: MathJax, KaTeX - for interactive mathematical expressions
**Observable Runtime**: For Observable-style notebooks and reactive programming
**Scientific Computing**: Limited subset of libraries for data analysis visualization

**Distribution Method**: All approved libraries served from Aris-controlled CDN with Subresource Integrity verification. Papers reference libraries by name/version, not external URLs.

## File Validation Requirements

### Upload Validation
**File Type Verification**: MIME type checking combined with magic number validation prevents executable files disguised as HTML.

**Size Limits**: Individual files capped at 50MB, total bundle size limited to 200MB to prevent storage abuse.

**HTML Structure Validation**: Strict parsing ensures well-formed documents, rejecting malformed HTML that could exploit browser vulnerabilities.

**External Resource Inventory**: Catalog all referenced external assets, validate domains against allowlist of academic/scientific resources.

### Content Quality Checks
**Academic Content Verification**: Basic heuristics to identify papers with legitimate academic structure (title, abstract, references, author information).

**Suspicious Pattern Detection**: Flag content with excessive external links, keyword stuffing, or other spam indicators for manual review.

**Metadata Extraction**: Validate presence and format of essential academic metadata (title, authors, abstract, submission date).

## Technical Implementation

### Backend Libraries
**HTML Sanitization**: Bleach library provides robust, battle-tested HTML cleaning with configurable allowlists for tags, attributes, and CSS properties.

**CSS Validation**: Bleach CSS sanitizer handles CSS property validation and dangerous pattern removal.

**File Type Detection**: python-magic library for reliable MIME type detection and file format validation.

**Cryptographic Nonce Generation**: Python secrets module for cryptographically secure random nonce generation.

### Security Headers
**Content Security Policy**: Strict policy allowing only nonce-bearing scripts, preventing inline event handlers and eval-based code execution.

**Additional Headers**: X-Frame-Options, X-Content-Type-Options, and Referrer-Policy for defense-in-depth security.

## Risk Assessment and Mitigation

### Acceptable Risks for MVP
**Limited JavaScript Ecosystem**: Starting with curated library set reduces functionality but ensures security during market validation phase.

**Manual Review Bottleneck**: Custom interactive content requires manual security review, limiting initial adoption but protecting platform integrity.

**Performance Overhead**: Sanitization and nonce generation add processing time but remain acceptable for academic publishing timescales.

### Unacceptable Risks
**XSS Vulnerabilities**: Zero tolerance for script injection attacks that could compromise user data or platform integrity.

**Content-Based Attacks**: Malware distribution, phishing, or other malicious content hosted on platform could destroy academic credibility.

**Infrastructure Abuse**: Unlimited resource consumption could make platform economically unsustainable.

## Success Metrics
**Security Metrics**: Zero successful XSS attacks, zero malware incidents, less than 1% of uploads requiring manual intervention.

**Functionality Metrics**: Support for 90% of Typst/Quarto interactive features, successful rendering of D3.js visualizations and mathematical content.

**Performance Metrics**: HTML sanitization adds less than 200ms to upload processing time, page load times under 2 seconds on mobile devices.

## Future Expansion Path
**Phase 2 Capabilities**: User-submitted JavaScript with automated static analysis and manual review workflow.

**Container Isolation**: Evaluation of containerized JavaScript execution for complex interactive content requiring broader library support.

**Community Moderation**: Reputation-based system allowing trusted community members to approve interactive content.

*NOTE: This specification is largely stale — the actual Press security model (iframe isolation, HTMLValidator, CSP with unsafe-inline/unsafe-eval) differs significantly from what is described above. See the Press CLAUDE.md for the current implementation. This document is retained for historical reference.*

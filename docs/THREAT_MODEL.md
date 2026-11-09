# Threat model

**Rule for agents:** before proposing security work, name the row below it addresses. If the row says Accept, or there is no row, stop. Work on it only after Leo changes this file.

**1. What are we working on?** Press is a preprint archive. Authors upload HTML papers, and Press gives each a permanent URL and a DOI from Zenodo. The parts are:
- scroll.press, the Press pages and logins, on Fly behind Cloudflare
- the content domain, where each paper's files are served from its own subdomain, with no Press login
- Supabase (database), Tigris (file storage), Zenodo (DOIs), Resend (email), ORCID (login)

Trust boundaries: author files never run on scroll.press. Readers' and authors' logins live only on scroll.press.

**2 and 3. What can go wrong, and what we do about it** (STRIDE):

| Type | Threat | Response |
|---|---|---|
| Spoofing | Password guessing on login | Mitigate: 10 failed logins lock that account for 15 minutes |
| Spoofing | A paper's scripts acting as a reader | Mitigate: papers served from the content domain |
| Spoofing | Targeted phishing, fake Press login pages | Accept |
| Tampering | Someone changing a published paper or adding a version under another author | Mitigate: only the owner can publish, published files are fixed by content hash |
| Tampering | Spam or phishing uploads | Accept: Leo deletes them in the database when found. No user-facing takedown. |
| Repudiation | An author denies uploading a paper | Accept: app logs only |
| Information disclosure | Emails, names or ORCID iDs leaking | Mitigate: owner checks on every private page, see GDPR.md |
| Information disclosure | Readers' IPs reaching outside content an author loads | Accept |
| Information disclosure | PR preview apps exposing real data | Mitigate: no production storage or secrets |
| Denial of service | Crawlers or hot-linking running up costs | Mitigate: Cloudflare caches paper files |
| Denial of service | Spam DOIs getting Press's Zenodo account banned | Accept: a DOI is requested on publish |
| Elevation of privilege | Someone taking over a Press service account | Transfer to the provider. Leo keeps 2FA and offline recovery codes on each account. |

**4. Did we do a good enough job?** Leo reviews this file when Press gets many authors, holds anything of money value, has an incident (decide within 72 hours whether GDPR requires notice), or changes a part listed in 1.

**Settled:** the iframe sandbox was rejected because it breaks author code.

Sources: Threat Modeling Manifesto four questions, OWASP Threat Modeling Cheat Sheet (STRIDE, Mitigate/Eliminate/Transfer/Accept).

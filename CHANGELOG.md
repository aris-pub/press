# Changelog

## [0.1.0] - 2026-03-19

### Added

- Public REST API (v1) for AI agent access to scholarly content
- Human-readable scroll URLs at `/{year}/{slug}` with automatic slug generation at publish time
- Rich social link previews with Open Graph images and structured metadata
- Turnstile CAPTCHA and signup rate limiting on registration
- Per-user upload rate limit of 5 uploads per hour
- Password change feature with forgot-password link
- Account deletion flow
- Infinite draft persistence for academic workflows
- Admin email notifications for new signups and published scrolls
- DOI badge component with Zenodo sandbox detection
- Back-to-top floating action button on scroll view pages
- Post-deployment email health check
- Database health checks with latency metrics
- Backup health check workflow
- Sentry alert rules with abuse-pattern reporting
- Plotly CDN support for interactive widgets

### Fixed

- FAB occlusion issues resolved with grouped horizontal layout
- Dashboard `hx-boost` bug and dead footer partial removed
- Dark mode contrast and How It Works page layout
- Turnstile widget rendering failures with HTMX navigation
- CSRF protection for password change form
- Double navbar after HTMX navigation
- Theme toggle and event listeners for HTMX-loaded content
- Upload form returning full page instead of partial on errors
- Session injection vulnerability via Supabase RLS enforcement
- Email error handling with Sentry integration
- Parallel database conflicts in unit tests
- Flaky mobile login and E2E test timing issues

### Changed

- Redesigned floating action buttons as a grouped horizontal unit
- Homepage refactored to HTMX patterns with dark-mode footer fix
- HTML validation switched from regex to BeautifulSoup
- File uploads use `UploadFile` for better memory efficiency
- Static file cache TTL reduced from 1 year to 1 hour
- Security model relaxed to allow `unsafe-eval` for interactive research libraries (Bokeh, Plotly)
- Signup form label changed to "Full Name"
- Legal page dates and privacy policy updated with named subprocessors for GDPR compliance
- Excluded `html_content` from list queries to improve load times
- Unified email verification banners into a reusable component


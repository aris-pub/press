# Changelog

All notable changes to Scroll Press will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- **GDPR Data Export Endpoint** (`/user/export-data`)
  - Users can export all their data in JSON format (GDPR Article 20 compliance)
  - Returns user profile, scrolls, and active sessions
  - Requires authentication, users can only export their own data
  - Comprehensive test coverage in `tests/test_data_export.py`

- **Static File Caching**
  - Static files cached for 1 year with `immutable` flag
  - SEO files (robots.txt, sitemap.xml) cached for 1 day
  - Implemented via `StaticFilesCacheMiddleware`
  - Reduces server load and improves page load times

- **Sentry Release Tracking**
  - GIT_COMMIT environment variable now set via Dockerfile build arg
  - Fly.io automatically injects actual git commit hash during deployment
  - Enables tracking which deploy introduced bugs in Sentry dashboard

### Changed
- **Scaling Limitation Documented**
  - `max_machines_running` set to 1 in `fly.toml` (down from 5)
  - In-memory CSRF and rate limiting prevents horizontal scaling
  - Must migrate to database/Redis before scaling beyond 1 machine
  - Documented in DEPLOYMENT.md with clear explanation

### Fixed
- Static files now served with proper caching headers
- Sentry release tracking now shows commit hashes instead of "dev"

## Release Notes

### Launch Readiness Changes (2026-01-02)

This release includes 4 critical improvements for public launch:

1. **GDPR Compliance**: Added data export endpoint as required by EU law
2. **Performance**: Implemented static file caching to reduce server load
3. **Monitoring**: Fixed Sentry release tracking for better debugging
4. **Stability**: Limited scaling to prevent CSRF/rate limiting issues

**Files Changed**:
- `tests/test_data_export.py` (new - 174 lines)
- `app/routes/auth.py` (+72 lines)
- `Dockerfile` (+3 lines)
- `fly.toml` (2 changes)
- `app/middleware.py` (+25 lines)
- `main.py` (+2 lines)
- `README.md` (updated features and GDPR section)
- `SENTRY_SETUP.md` (marked GIT_COMMIT as done)
- `DEPLOYMENT.md` (added scaling limitation docs)
- `CLAUDE.md` (documented new patterns)

**Test Results**: All 323 unit tests passing (including 4 new data export tests)

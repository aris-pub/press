# Scroll Press Deployment Guide

This guide covers deploying Scroll Press to production using Supabase (database) and Fly.io (application).

## Environments

Press runs in four places. Only production holds real data or production secrets.

| | Production | PR preview | CI | Local |
|---|---|---|---|---|
| Where | Fly app `scroll-press`, behind Cloudflare at scroll.press | Fly app `scroll-press-pr-<number>` at `<app>.fly.dev` | GitHub Actions | Your machine |
| Database | Supabase | Its own Fly Postgres, `scroll-press-pr-<number>-db` | Postgres in the job | Local Postgres |
| Data | Real users and papers | Sample papers from `examples-press`, reloaded on every deploy | Test data | Your own |
| File storage | Tigris bucket `scroll-press-storage` | In memory, lost on restart | In memory | Your `.env` |
| Secrets | All, set with `fly secrets set` | `SECRET_KEY` and `ENVIRONMENT=preview` only | None | Your `.env` |
| Paper files | `{url_hash}.scrollusercontent.com` once `CONTENT_DOMAIN` is set | Press itself | Press itself, plus a second server with `CONTENT_DOMAIN=content.test` for its browser tests | Press itself |

### PR previews

`.github/workflows/preview.yml` creates a preview app and database when a PR is opened, deploys
it on every push, and destroys both when the PR is closed. Dependabot PRs get no preview.

Previews get no production secrets. Each missing secret turns a feature off:

- No storage keys: uploaded files are kept in memory (`app/storage/__init__.py`) and are gone when
  the preview restarts.
- No ORCID keys: the "Sign in with ORCID" button is hidden. Email login works.
- No Resend key: no emails are sent, so new accounts on a preview cannot verify their email. Use
  the seeded account `testuser@example.com` (see `scripts/seed.py`).
- No Zenodo token: no DOIs are minted.
- No Sentry DSN, Turnstile keys or Bluesky password.

Rules:

- Never give a preview a production secret. Preview code has not been reviewed, and a production
  key would let it read, change or delete production data. `tests/test_preview_workflow.py` fails
  if `preview.yml` names one.
- If a preview needs a service to work, create a separate test account or key for it, never the
  production one.
- Secrets are set only when a preview app is first created. Changing `preview.yml` does not change
  previews that already exist. Close and reopen the PR to rebuild one.

## Prerequisites

- [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/) installed
- Supabase account
- Git repository ready for deployment

## Phase 1: Database Setup (Supabase)

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up/login
2. Create a new project: "scroll-press-prod"
3. Choose a region close to your users
4. Set a strong database password

### 2. Get Database Connection Details

1. Navigate to Settings > Database in your Supabase project
2. Copy the connection string under "Connection string"
3. Convert to async format:
   ```
   Original: postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
   For app: postgresql+asyncpg://postgres:[PASSWORD]@[HOST]:5432/postgres
   ```

### 3. Run Migrations

Update your local `.env` file with the Supabase DATABASE_URL and run:

```bash
# Apply database migrations
just migrate

# Seed with initial data
just seed
```

## Phase 2: Email Service Setup (Resend)

### 1. Create Resend Account

1. Go to [resend.com](https://resend.com) and sign up
2. Verify your domain or use Resend's testing domain
3. Generate an API key from the dashboard

### 2. Configure Email Settings

For production, you'll need:
- `RESEND_API_KEY`: Your Resend API key
- `FROM_EMAIL`: Verified sender email (e.g., noreply@yourdomain.com)
- `BASE_URL`: Your production URL (e.g., https://scroll-press.fly.dev)

## Phase 3: Application Deployment (Fly.io)

### 1. Initialize Fly.io App

```bash
# Install Fly CLI (if not done)
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
fly auth login

# Launch app (but don't deploy yet)
fly launch --no-deploy
```

This will create a `fly.toml` file. The one in this repo is already configured.

### 2. Set Environment Variables

Never set `TESTING` or `E2E_TESTING` on Fly. They turn off rate limits and the HTTPS
redirect and open test-only routes. The app refuses to start if either is set on a Fly
machine or with `ENVIRONMENT=production` (`app/startup_guard.py`).

```bash
# Set your Supabase database URL
fly secrets set DATABASE_URL="postgresql+asyncpg://postgres:[PASSWORD]@[HOST]:5432/postgres"

# Set email service credentials
fly secrets set RESEND_API_KEY="re_your_api_key_here"
fly secrets set FROM_EMAIL="noreply@yourdomain.com"
fly secrets set BASE_URL="https://scroll-press.fly.dev"

# Set application limits
fly secrets set HTML_UPLOAD_MAX_SIZE="52428800"
fly secrets set MAX_EXTERNAL_LINKS="10"

# Tigris object storage (for zip archive uploads)
# Created via: fly storage create
# Fly.io auto-injects these after `fly storage create`, but you can set them manually:
fly secrets set BUCKET_NAME="your-bucket-name"
fly secrets set AWS_ENDPOINT_URL_S3="https://fly.storage.tigris.dev"
fly secrets set AWS_ACCESS_KEY_ID="your-access-key"
fly secrets set AWS_SECRET_ACCESS_KEY="your-secret-key"
```

### 3. Deploy Application

```bash
# Deploy to Fly.io
fly deploy

# Check deployment status
fly status

# View logs
fly logs

# Open in browser
fly open
```

### 4. Verify Deployment

**Run email health check (recommended after every deployment):**
```bash
# After deploying with 'fly deploy', run:
fly ssh console -C "python scripts/email_health_check.py"
```

This sends a test email to verify:
- Resend API key is valid
- FROM_EMAIL domain is properly configured
- BASE_URL is correct for email links
- Email delivery is working

Test these endpoints:
- `/health` - Health check (should return `{"status": "ok", "service": "scroll-press"}`)
- `/` - Homepage loads
- `/register` - User registration works
- Email verification - Check that verification emails are sent and links work
- `/upload` - File upload (after email verification)
- `/robots.txt` - SEO crawlers can access site map
- `/sitemap.xml` - Dynamic sitemap generates correctly
- `/user/export-data` - Data export works (requires authentication)

**Check static file caching**:
```bash
# Verify cache headers are present
curl -I https://your-domain.com/static/css/main.css
# Should include: Cache-Control: public, max-age=3600
```

**Verify Sentry release tracking**:
```bash
# SSH into production and check GIT_COMMIT
fly ssh console
env | grep GIT_COMMIT
# Should show actual git commit hash, not "dev"
```

## Phase 4: Custom Domain (Optional)

### 1. Add Custom Domain

```bash
# Add your domain
fly certs add your-domain.com

# Check certificate status
fly certs list
```

### 2. Update DNS

Add these DNS records:
```
A record: your-domain.com -> [Fly.io IP from fly ips list]
AAAA record: your-domain.com -> [Fly.io IPv6 from fly ips list]
```

## Monitoring and Maintenance

### Application Logs
```bash
# View recent logs
fly logs

# Follow logs in real-time
fly logs -f
```

### Database Monitoring
- Monitor database performance in Supabase dashboard
- Set up alerts for connection limits
- Review query performance regularly

### Scaling

**⚠️ IMPORTANT - Current Scaling Limitation**

The application is currently limited to **1 machine maximum** due to in-memory storage for CSRF tokens and rate limiting:

```toml
# fly.toml
max_machines_running = 1  # Limited to 1 until CSRF/rate limiting moved to database
```

**Why this limitation exists**:
- CSRF tokens are stored in-memory (module-level dictionary in `app/auth/csrf.py`)
- Rate limiting uses in-memory counters (module-level dictionary in `app/middleware.py`)
- With multiple machines, each would have its own separate storage
- This would cause CSRF validation failures and ineffective rate limiting

**To scale beyond 1 machine**, you must first:
1. Migrate CSRF token storage to database or Redis
2. Migrate rate limiting to database or Redis
3. Update `fly.toml` to allow `max_machines_running = 5`

**Current capacity with 1 machine**:
- Configured for 100 concurrent requests (hard limit)
- 75 concurrent requests (soft limit)
- Sufficient for initial launch and small-to-medium user base

**Vertical scaling** (increasing resources on single machine):
```bash
# Scale machine resources (works within current limitation)
fly scale memory 2048
fly scale cpu 2
```

### Backups
- Supabase automatically backs up your database
- Manual backups available in Supabase dashboard
- Consider setting up automated app deployment backups

## Rollback Strategy

### Application Rollback
```bash
# List recent deployments
fly releases

# Rollback to previous version
fly deploy --image [previous-version-id]
```

### Database Rollback
- Use Supabase dashboard to restore from backup
- Test rollback procedure in staging environment

## Troubleshooting

### Common Issues

**App won't start:**
```bash
# Check logs for errors
fly logs

# Verify environment variables
fly secrets list
```

**Database connection issues:**
```bash
# Test connection from app
fly ssh console
# Then run: uv run python -c "from app.database import engine; print('DB OK')"
```

**Static files not loading:**
- Verify `/static` mount in fly.toml
- Check static files are included in Docker build

### Support Resources
- [Fly.io Documentation](https://fly.io/docs/)
- [Supabase Documentation](https://supabase.com/docs)
- Application logs: `fly logs`
- Database monitoring: Supabase dashboard

## Security Considerations

- Database passwords are managed by Supabase
- All secrets stored in Fly.io secrets (encrypted)
- HTTPS enforced via `force_https = true`
- Application runs as non-root user in container
- Regular dependency updates via `uv sync`
- GDPR-compliant data export via `/user/export-data` endpoint
- Static files cached with immutable headers (1-year TTL)
- Sentry release tracking enabled for error debugging
- CSRF and rate limiting use in-memory storage (single-machine only)

## Cost Monitoring

- **Fly.io**: Monitor usage in dashboard, set spending limits
- **Supabase**: Free tier generous, monitor database size and API calls
- Set up billing alerts in both services

### Supabase egress from papers

Papers uploaded as a single HTML file are stored in the database, in the `html_content`
column of `scrolls`. Some are over 10 MB. Supabase charges for every byte read out of the
database, so each time Press reads a paper, it costs money.

The scroll page does not read the paper. Only the paper URL inside it does
(`/scroll/{hash}/paper`), and it answers "not modified" from the content hash without
reading the paper. A full read still happens for every reader who has no copy yet.

This is why Cloudflare caches `/scroll/{hash}/paper`. With that cache, Supabase is read
about once a day per paper, not once per reader. Press marks those answers
`s-maxage=86400` for Cloudflare. Previews are marked `private, no-store` and must never be
kept. "Not found" answers carry no mark.

The Cloudflare rule, "Cache paper bytes":

- Field URI Path, wildcard `/scroll/*/paper*`, Eligible for cache.
- Edge TTL: "Use cache-control header if present, bypass cache if not". Never "Ignore
  cache-control header". That setting keeps previews and "not found" answers too.

Once `CONTENT_DOMAIN` is set, published paper files are served from the content domain
(see `docs/ARCHITECTURE.md`), so the content domain's Cloudflare zone needs the same rule,
for all paths. Add it before setting `CONTENT_DOMAIN`, or every paper read goes to
Supabase. The redirects from the old scroll.press paper paths carry no cache header and
are not cached.

Rules for the Cloudflare cache:

- Keep caching the paper URLs. Removing that cache brings the Supabase cost back.
- Do not cache scroll pages (`/scroll/{hash}`, `/{year}/{slug}`). Each one carries its own
  security nonce, and a cached copy breaks the page for the next reader.
- Before deleting or changing any cache rule, read this section and check what the rule
  covers.
- Deploys do not clear Cloudflare. After a deploy that changes how papers are served (for
  example `paper-bridge.js`), purge the paper URLs, or readers get the old version for up
  to a day.

Papers uploaded as zip archives are stored in Tigris, not in the database, and do not
cost Supabase egress.
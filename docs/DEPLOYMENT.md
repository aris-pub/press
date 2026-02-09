# Scroll Press Deployment Guide

This guide covers deploying Scroll Press to production using Supabase (database) and Fly.io (application).

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
# Should include: Cache-Control: public, max-age=31536000, immutable
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
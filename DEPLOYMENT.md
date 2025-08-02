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

## Phase 2: Application Deployment (Fly.io)

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

Test these endpoints:
- `/health` - Health check
- `/` - Homepage loads
- `/register` - User registration works
- `/upload` - File upload (after registration)

## Phase 3: Custom Domain (Optional)

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
```bash
# Scale up for traffic
fly scale count 2

# Scale machine resources
fly scale memory 2048
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

## Cost Monitoring

- **Fly.io**: Monitor usage in dashboard, set spending limits
- **Supabase**: Free tier generous, monitor database size and API calls
- Set up billing alerts in both services
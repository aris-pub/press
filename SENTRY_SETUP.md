# Sentry Configuration Guide for Scroll Press

## Current Status

Your Sentry integration is configured and ready. The DSN is already set in Fly.io secrets.

## Recommended Configuration Steps

### 1. Set Release Tracking ✅ CONFIGURED

Release tracking is now configured via `GIT_COMMIT` build argument:

**Configuration** (already implemented):
- `fly.toml` passes `GIT_COMMIT = "auto"` as build arg
- `Dockerfile` accepts and sets `GIT_COMMIT` environment variable
- Sentry reads `GIT_COMMIT` on startup to track releases

**How it works**:
```dockerfile
# Dockerfile
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=$GIT_COMMIT
```

```toml
# fly.toml
[build.args]
  GIT_COMMIT = "auto"
```

Fly.io automatically replaces "auto" with the current git commit hash during deployment.

### 2. Verify Production Alerts are Working

**Test Sentry integration**:
```bash
# SSH into production
fly ssh console

# Trigger a test error
python -c "import sentry_sdk; sentry_sdk.init(dsn='YOUR_DSN'); sentry_sdk.capture_message('Test from production')"
```

Check your Sentry dashboard - you should see the event.

### 3. Configure Alert Rules in Sentry Dashboard

**Recommended alerts**:

1. **High Error Rate Alert**
   - Condition: More than 10 errors in 5 minutes
   - Action: Email you immediately

2. **500 Internal Server Error Spike**
   - Condition: More than 5 server errors in 10 minutes
   - Action: Email + Slack/Discord webhook

3. **Performance Degradation**
   - Condition: P95 response time > 2 seconds
   - Action: Email notification

4. **Database Connection Issues**
   - Condition: SQLAlchemy errors spike
   - Action: Immediate notification

**To configure**: Sentry Dashboard → Alerts → Create Alert Rule

### 4. Performance Monitoring Budget

Current sampling rates:
- **Production**: 10% of requests (good balance)
- **Development**: 100% (fine for debugging)

**Cost estimation** (assuming 1000 req/day in production):
- Sampled requests: 100/day
- Monthly: ~3000 transactions
- Sentry free tier: 10k transactions/month ✅

You're well within free tier limits.

**If you exceed free tier**, reduce to 5%:
```python
traces_sample_rate=1.0 if environment == "development" else 0.05,
```

### 5. Ignore Noise

Currently all errors go to Sentry. You may want to filter out common non-critical errors.

**Add to `main.py` after Sentry init**:
```python
def before_send(event, hint):
    # Filter test environment
    if environment == "testing":
        return None

    # Ignore 404s (they're not errors, just missing pages)
    if event.get("level") == "error":
        for exception in event.get("exception", {}).get("values", []):
            if "404" in str(exception):
                return None

    # Ignore rate limit errors (expected behavior)
    if "rate_limit" in str(event).lower():
        return None

    return event
```

Replace the current `before_send` lambda with this function.

### 6. Set Up Releases in Sentry (Optional but Recommended)

**Benefits**:
- Track which version introduced bugs
- See if new deploys increase error rates
- Associate commits with errors

**Setup**:
```bash
# Install Sentry CLI
curl -sL https://sentry.io/get-cli/ | bash

# Create .sentryclirc
cat > .sentryclirc << EOF
[defaults]
org=your-org-name
project=scroll-press

[auth]
token=YOUR_SENTRY_AUTH_TOKEN
EOF

# Add to deploy script
sentry-cli releases new $(git rev-parse --short HEAD)
sentry-cli releases set-commits --auto $(git rev-parse --short HEAD)
sentry-cli releases finalize $(git rev-parse --short HEAD)
fly deploy
```

### 7. Dashboard Review Checklist

**Weekly** (once you have traffic):
- [ ] Check error rate trends
- [ ] Review new error types
- [ ] Check performance degradation
- [ ] Verify no PII is being sent (users, emails, IPs)

**Monthly**:
- [ ] Review Sentry quota usage
- [ ] Adjust sampling rates if needed
- [ ] Clean up resolved issues

## Current Configuration Summary

```python
# Production settings (verified):
- traces_sample_rate: 10% ✅
- profiles_sample_rate: 10% ✅
- send_default_pii: False ✅ (GDPR compliant)
- environment: "production" ✅
- integrations: FastAPI, SQLAlchemy, AsyncIO ✅
```

## What You Get With This Setup

1. **Error Tracking**: All unhandled exceptions automatically logged
2. **Performance Monitoring**: 10% of requests tracked for latency
3. **Database Query Insights**: Slow queries automatically flagged
4. **User Impact**: See how many users affected by each error
5. **Release Tracking**: Which deploy introduced each bug (once releases configured)
6. **Breadcrumbs**: See the 50 events leading up to each error

## Verification Commands

```bash
# Check Sentry is configured in production
fly ssh console
env | grep SENTRY_DSN  # Should show your DSN

# Check environment is set correctly
env | grep ENVIRONMENT  # Should show "production"

# Check Git commit tracking (should show actual commit hash)
env | grep GIT_COMMIT
```

## Next Steps (Priority Order)

1. ✅ **DONE**: Sentry DSN configured in Fly.io secrets
2. ✅ **DONE**: GIT_COMMIT environment variable configured for release tracking
3. **TODO**: Trigger test error to verify alerts work
4. **TODO**: Configure email alerts in Sentry dashboard
5. **OPTIONAL**: Set up Sentry CLI for release tracking
6. **OPTIONAL**: Add Slack/Discord webhook for critical alerts

## Useful Sentry Features You're Not Using Yet

1. **Session Replay**: Record user sessions when errors occur (requires frontend integration)
2. **Cron Monitoring**: Track scheduled tasks (when you add background jobs)
3. **Uptime Monitoring**: Sentry can ping your /health endpoint (alternative to UptimeRobot)
4. **Custom Contexts**: Add more metadata to errors (scroll IDs, user roles, etc.)

All of these can wait until after launch.

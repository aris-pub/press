# Authentication Documentation

## Overview

Scroll Press uses session-based authentication with token-based email verification and password reset functionality.

## Authentication Architecture

- **Session-based authentication**: Not JWT-based
- **Session storage**: In-memory (24-hour expiration)
- **Session management**: `app/auth/session.py`
- **Token verification**: Email verification and password reset via `app/auth/tokens.py`
- **Email service**: Resend API for transactional emails

## Email Verification Flow

1. **Registration**: User registers and receives verification email via Resend
2. **Verification**: User clicks email link with time-limited token (24 hours)
3. **Access Control**: Unverified users can view dashboard but cannot upload or export data
4. **Password Reset**: Secure token-based password reset with 1-hour expiration

## Token Security

### Email Verification Tokens
- **Expiration**: 24 hours
- **Storage**: Hashed in database
- **Limit**: One active verification token per user

### Password Reset Tokens
- **Expiration**: 1 hour
- **Storage**: Hashed in database
- **Limit**: One active reset token per user

## Access Control

### Authenticated Routes
Users must be logged in to:
- Upload scrolls
- Manage their submissions
- Export their data (GDPR compliance)
- Update account settings

### Unverified User Restrictions
Users with unverified email addresses can:
- View their dashboard
- Browse public scrolls

Users with unverified email addresses cannot:
- Upload new scrolls
- Export their data
- Perform account operations

## Email Service Configuration

Scroll Press uses [Resend](https://resend.com) for transactional emails.

### Required Environment Variables
```bash
RESEND_API_KEY=re_xxxxxxxxxxxx
FROM_EMAIL=noreply@updates.aris.pub
BASE_URL=https://scroll.press
```

### Email Templates
Email templates are defined in `app/emails/templates.py`:
- Verification email
- Password reset email
- Welcome email (future)

## Security Considerations

### Scaling Limitation
The application is currently limited to 1 machine in `fly.toml` because:
- Session storage uses in-memory module-level dictionary (`app/auth/session.py`)
- CSRF tokens use in-memory module-level dictionary (`app/auth/csrf.py`)
- Rate limiting uses in-memory module-level counters (`app/middleware.py`)

**Before scaling horizontally**, migrate to database or Redis-backed storage for:
- Sessions
- CSRF tokens
- Rate limiting counters

Current capacity: 100 concurrent requests per machine (hard limit)

## Session Management

### Session Creation
Sessions are created on successful login and stored in memory with:
- Unique session ID (UUID)
- User ID reference
- Creation timestamp
- Expiration timestamp (24 hours)

### Session Validation
All authenticated routes use `get_current_user_from_session()` dependency to:
1. Extract session ID from cookie
2. Validate session exists and hasn't expired
3. Return authenticated user or raise 401

### Session Cleanup
Expired sessions are cleaned up automatically on validation attempts. No background cleanup process is currently implemented.

# GDPR Compliance Documentation

## Overview

Scroll Press implements GDPR Article 20 (Right to Data Portability) to allow users to export all their personal data in a machine-readable format.

## Data Export

### Endpoint
```
GET /user/export-data
```

### Authentication
Requires active session authentication (session cookie).

### Usage Example
```bash
# Using curl with session cookie
curl -X GET https://scroll.press/user/export-data \
  -H "Cookie: session_id=YOUR_SESSION_ID"
```

### Response Format
The endpoint returns JSON containing all user data:

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "User Name",
    "is_verified": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  "scrolls": [
    {
      "id": "uuid",
      "scroll_id": "unique-scroll-id",
      "title": "Research Paper Title",
      "authors": "Author Names",
      "abstract": "Paper abstract...",
      "content": "<html>...</html>",
      "is_published": true,
      "version": 1,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "sessions": [
    {
      "session_id": "session-uuid",
      "created_at": "2024-01-01T00:00:00Z",
      "expires_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

### Exported Data Includes
- **User profile**: Email, display name, verification status, timestamps
- **All scrolls**: Published and draft manuscripts with complete metadata and content
- **Active sessions**: Session IDs with creation and expiration times

### Security Features
- **Authentication required**: Returns 401 if not logged in
- **User isolation**: Users can only export their own data
- **Structured format**: JSON for easy portability and parsing
- **Email verification required**: Unverified users cannot export data

### Implementation
- **Location**: `export_user_data` in `app/routes/auth.py`
- **Tests**: `tests/test_data_export.py`

## Data Minimization
Current data collection is minimal:
- Email (required for authentication)
- Display name (optional)
- Scroll content (user-provided research)
- Session data (temporary, expires in 24 hours)

No third-party tracking, analytics, or advertising data is collected.

## Compliance Notes

### Data Processing
- All user data is processed exclusively for service functionality
- No data is sold. Every service that receives data is listed in the privacy policy, section 6.
- Email service (Resend) is used only for transactional emails

### Data Storage
- **Database**: Supabase PostgreSQL (EU region for European users)
- **Sessions**: in the database, expire after 24 hours
- **Files**: Tigris
- **Backups**: GitHub Actions (encrypted, private repository)

### User Rights
Users can:
- Export their data (Article 20)
- Delete their account (Article 17)
- Ask for corrections by email (Article 16), since there is no profile edit page
- Contact leo@leotrs.com for any data request

## If there is a data breach

A breach is any loss, leak or unauthorized access to personal data, for example a leaked database key.

1. Stop it: rotate the leaked keys, take the app down if needed.
2. Within 72 hours of learning about it, decide whether it is likely to put people at risk. If yes, report it to the Sächsische Datenschutz- und Transparenzbeauftragte with their online form at datenschutz.sachsen.de.
3. If the risk to people is high, email the affected users without delay.
4. Write down every breach, even ones not reported: what happened, what data, what was done. GDPR requires this record.

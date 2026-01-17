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
- **Location**: `app/routes/auth.py:810-881`
- **Tests**: `tests/test_data_export.py`

## Future GDPR Features

### Planned Implementations
- **Right to Erasure (Article 17)**: Account deletion with data anonymization options
- **Right to Rectification (Article 16)**: Profile update endpoints (partially implemented)
- **Privacy Policy**: Terms of service and privacy policy pages
- **Consent Management**: Cookie consent and tracking preferences
- **Data Retention**: Automated cleanup of expired tokens and old sessions

### Data Minimization
Current data collection is minimal:
- Email (required for authentication)
- Display name (optional)
- Scroll content (user-provided research)
- Session data (temporary, expires in 24 hours)

No third-party tracking, analytics, or advertising data is collected.

## Compliance Notes

### Data Processing
- All user data is processed exclusively for service functionality
- No data is sold or shared with third parties
- Email service (Resend) is used only for transactional emails

### Data Storage
- **Database**: Supabase PostgreSQL (EU region for European users)
- **Sessions**: In-memory storage (not persisted to disk)
- **Backups**: GitHub Actions (encrypted, private repository)

### User Rights
Users can:
- Export their data (Article 20)
- Update their profile information (Article 16)
- Contact support for data inquiries via GitHub issues

### Future Scaling
When migrating from in-memory sessions to database/Redis:
- Session data will be included in GDPR export
- Session cleanup policies will be documented
- Retention periods will be clearly defined

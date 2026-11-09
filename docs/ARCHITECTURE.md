# Architecture

How Press is built inside. For the database see `DATABASE.md`, for logins see
`AUTHENTICATION.md`, for tests see `TESTING.md`.

## Templates and frontend

- Jinja2 with macro components, not includes. Example:
  `{% from "components/form_input.html" import form_input %}`.
- Form macros: `form_input()`, `button()`, `auth_form()` in `app/templates/components/`.
- Use the `xmlattr` filter for conditional HTML attributes.
- HTMX for form submissions and dynamic parts of a page. HTMX forms target containers with
  `hx-swap="innerHTML"`. Validation errors return status 422.
- All CSS is in one file, `static/css/main.css`.
- Fonts: Source Sans 3 for text, Georgia for headings.
- Class names for paper components use the `scroll-` prefix, not `paper-`.
- Icons are inline SVG with `stroke="currentColor"`, so they follow the theme.

## Database access

- Every database call is async.
- Check the logged-in user with `get_current_user_from_session()` (`app/auth/session.py`).
- Custom SQLAlchemy TypeDecorators in `app/models/` keep the models working on both
  PostgreSQL and SQLite.

## File storage (Tigris)

- Tigris is Fly's S3-compatible storage, used through aioboto3.
- `StorageBackend` in `app/storage/backend.py` defines `put`, `get`, `delete`, `exists`
  and `list_prefix`.
- `TigrisStorage` (`app/storage/tigris.py`) is used in production. `InMemoryStorage`
  (`app/storage/memory.py`) is used in tests and PR previews.
- `get_storage()` in `app/storage/__init__.py` picks one from the environment variables
  `BUCKET_NAME`, `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
- Keys are `scrolls/{content_hash}/{relative_path}`. A key is set by the file's content
  hash and never changes.

## Uploads

`POST /upload-form` takes a single `.html` file or a `.zip`.

Zip checks (`app/upload/zip_validator.py`):

- at most 200 MB uncompressed and a compression ratio of at most 100:1
- no path traversal and no symlinks
- only file types in `ALLOWED_EXTENSIONS`
- SVG files parsed with defusedxml
- every `.html` file passes `HTMLValidator`
- `__MACOSX` and dotfiles are skipped

The main HTML file of a zip (`app/upload/entry_point.py`), first rule that matches:

1. the only HTML file
2. `index.html` at the shallowest level
3. `paper.html`, `article.html`, `main.html` or `manuscript.html` at the shallowest level
4. the largest HTML file
5. the first one alphabetically

If a zip has more than one HTML file, the author confirms the choice on
`entry_point_picker.html`, which starts with the detected file selected.

## How papers are stored and served

- `inline` (single HTML upload): the HTML is in the `html_content` column of `scrolls`.
  It is served at `/scroll/{url_hash}/paper`.
- `archive` (zip upload): files are in Tigris with their folders kept. `entry_point` names
  the main HTML file and `archive_manifest` lists every file with its size and type. The
  main file is served at `/scroll/{url_hash}/paper/` (the trailing slash makes relative
  links work). Other files are at `/scroll/{url_hash}/paper/{relative_path}`, cached for
  one year.

### The content domain

When `CONTENT_DOMAIN` is set (production: `scrollusercontent.eu`), published paper files
are served from `{url_hash}.<CONTENT_DOMAIN>` instead, a different site from Press. A
paper's scripts then cannot use a reader's Press login (`docs/THREAT_MODEL.md`).

- `app/content_domain.py` maps a request to `{url_hash}.<CONTENT_DOMAIN>/{path}` onto the
  paper routes above, as `/scroll/{url_hash}/paper/{path}`. Nothing else in Press can be
  reached there: other methods and every error get a plain 404, and no cookie is set.
- Responses there may only be framed by Press (`frame-ancestors` names `BASE_URL`).
- On Press, the paper addresses above and `/{year}/{slug}/paper` redirect (301) to the
  content domain. The scroll page's iframe loads from it, and the scroll page CSP allows it
  in `frame-src`.
- Previews stay on Press, because the owner's login cookie never reaches the content
  domain. Signed preview links will move them (prs-2m6.1).
- The content domain uses Press's own scheme, from `BASE_URL`: https in production, http in
  the local browser tests.
- When `CONTENT_DOMAIN` is unset (local, CI, previews), nothing changes.

## Middleware order

Middleware is added in `main.py`. The last one added runs first.
`StaticFilesCacheMiddleware` is added first, so it runs last and sets cache headers on the
finished response. `ContentDomainMiddleware` is added second to last, so only
`ProxyHeadersMiddleware` runs before it and every other layer sees the mapped paper path.

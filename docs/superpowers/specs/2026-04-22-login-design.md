# Login Design — Bird ID Realtime

**Date:** 2026-04-22  
**Status:** Approved

## Summary

Add a simple password-gated login to the Bird ID app. On successful login the main page loads with the RTSP stream URL pre-filled, so the user never has to type it. The RTSP credentials stay server-side at all times.

## Architecture

### Session management

- Use `itsdangerous.URLSafeTimedSerializer` to sign a session cookie (`bird_id_session`). This is already available as a transitive dependency via Starlette/FastAPI.
- Cookie is `HttpOnly`, `SameSite=Lax`, `Secure` when behind HTTPS (Cloudflare tunnel / Render both terminate TLS).
- No database — the signed cookie is the entire session. Signing with `SECRET_KEY` prevents forgery.

### New routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/login` | Render login page. Redirect to `/` if already authenticated. |
| `POST` | `/login` | Validate password. On success set cookie and redirect to `/`. On failure re-render login with an error message. |
| `GET` | `/logout` | Clear cookie, redirect to `/login`. |

### Auth dependency

A `require_auth(request: Request)` FastAPI dependency reads and verifies the session cookie. It is applied to:
- `GET /` (main page)
- `POST /api/analyze`
- `POST /api/analyze-stream`
- `GET /api/health` — excluded (needed for Render health checks)

Unauthenticated requests to HTML routes redirect to `/login`. Unauthenticated API requests return `401 Unauthorized` (so the JS can surface a helpful message rather than silently failing).

## Configuration

Three new fields added to `app/config.py` / `.env`:

```
APP_PASSWORD=yourpassword          # Required — no default
SECRET_KEY=<random 32-char string> # Required — no default
DEFAULT_STREAM_URL=rtsp://...      # Optional — empty string default
```

`APP_PASSWORD` and `SECRET_KEY` have no defaults and will raise a startup error if missing, forcing explicit configuration before deployment.

## Template changes

### `index.html`

- `<input id="stream-url">` receives `value="{{ default_stream_url }}"` from the template context.
- A "Sign out" link is added to the top-bar right section, next to the sightings button.

### `login.html` (new)

- Matches existing app aesthetic: same CSS custom properties, same font stack, light mode.
- Centered card layout: Bird ID wordmark, password `<input type="password">`, Sign In `<button>`.
- Inline error message ("Wrong password — try again.") shown on failed attempt; no redirect, no reveal of whether the account exists.
- No username field — single shared password.

### `styles.css`

- Add `.login-card` styles scoped to the login page. Reuse existing variables for consistency — no new design tokens needed.

## Error handling

| Scenario | Behaviour |
|----------|-----------|
| Wrong password | Re-render `/login` with inline error, HTTP 200 |
| Missing `APP_PASSWORD` or `SECRET_KEY` at startup | FastAPI startup raises `ValueError`, app refuses to start |
| Tampered / expired cookie | Treated as unauthenticated; redirect to `/login` |
| Unauthenticated API call | `401 {"detail": "Unauthenticated"}` |

## Out of scope

- Multiple user accounts / per-user passwords
- "Remember me" duration control (cookie expires with browser session by default)
- Password reset flow
- Rate-limiting login attempts (acceptable for a personal tool)

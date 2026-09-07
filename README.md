# BSIT 4 — Class Announcement System

A web announcement board for BSIT 4, Saint Louis College (City of San Fernando, La Union).
The admin posts announcements; each one gets a readable, shareable link with a rich
Facebook Messenger preview. Classmates just open the link — no account, no login.

```
frontend/   Astro 7 + React islands, SSR, deploys to Vercel
backend/    Django 5 + DRF, deploys to Render
            PostgreSQL (Render managed) + Cloudinary (media)
```

---

## What it does

| | |
|---|---|
| **Home** (`/`) | Every published announcement, newest first, with search and pagination |
| **Announcement** (`/a/exam-schedule`) | Server-rendered page with body, photo gallery, and file downloads |
| **Admin** (`/admin`) | Modal-driven dashboard — create, edit, publish/unpublish, upload, delete |

Slugs come from the title (`Exam Schedule` → `exam-schedule`) and collisions get a
suffix (`exam-schedule-2`). Every announcement page carries Open Graph tags in the
server-rendered HTML, so Facebook's crawler sees the title, snippet, and first
image — falling back to the school seal when there is no photo.

---

## Running the system

The system is **two programs that run at the same time**: the Django API and the
Astro site. Each needs its own terminal window, and both must be running — the
site fetches everything from the API, so with the API stopped the pages load but
stay empty.

```
Terminal 1  →  backend    Django API   http://127.0.0.1:8000
Terminal 2  →  frontend   the website  http://localhost:4321
```

**Requirements:** Python 3.12+ and Node 20+. Check with `python --version` and
`node --version`. On Windows, if `python` opens the Microsoft Store, use `py -3.12`
instead of `python` in the commands below.

### First time only — set up

Run these once. Skip to [Every time](#every-time--start-the-system) afterwards.

**1. Backend**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # PowerShell
pip install -r requirements.txt
copy .env.example .env
```

<details>
<summary>Git Bash / macOS / Linux</summary>

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate     # Git Bash;  .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env
```
</details>

Open `backend/.env` and set `ADMIN_PASSWORD` to the password you want for your
admin login (10+ characters). Leave `DATABASE_URL` and the Cloudinary keys blank
— locally the app uses a SQLite file and saves uploads to `backend/media/`, so
there is nothing else to install.

```powershell
python manage.py migrate          # creates the database tables
python manage.py ensure_admin     # creates your admin account from .env
```

**2. Frontend** — in a second terminal:

```powershell
cd frontend
npm install
copy .env.example .env            # cp .env.example .env  on Git Bash/macOS
```

The default `frontend/.env` already points at `http://127.0.0.1:8000`, so it
works as-is for local use.

**3. Replace the logo**

`frontend/public/logo.png` is a **generated placeholder**. Save the real Saint
Louis College seal over it, keeping the filename — it is used in the header, on
empty states, and as the Open Graph fallback image. Square, at least 600×600.
(The placeholder can be regenerated with
`python frontend/scripts/generate_placeholder_logo.py`.)

### Every time — start the system

**Terminal 1 — the API:**

```powershell
cd backend
.venv\Scripts\Activate.ps1        # source .venv/Scripts/activate  on Git Bash
python manage.py runserver
```

Leave it running. It prints `Starting development server at http://127.0.0.1:8000/`.

**Terminal 2 — the website:**

```powershell
cd frontend
npm run dev
```

Leave it running too. Then open:

| | |
|---|---|
| **The board** | <http://localhost:4321> |
| **Admin dashboard** | <http://localhost:4321/admin> |
| **Django admin** (optional, rarely needed) | <http://127.0.0.1:8000/django-admin/> |

Sign in at `/admin` with the `ADMIN_USERNAME` and `ADMIN_PASSWORD` you put in
`backend/.env`. Click **New announcement**, write it, attach photos and files,
then use **Share** to copy the link for your Messenger group chat.

**To stop:** press `Ctrl+C` in each terminal.

### Posting your first announcement

1. Go to <http://localhost:4321/admin> and sign in.
2. **New announcement** → title and body (Markdown: `**bold**`, `- bullets`,
   `[links](https://…)`) → keep **Published** ticked → **Create announcement**.
3. **Files** on that row → upload photos and attachments. The first photo becomes
   the Messenger preview image.
4. **Share** → **Copy link** → paste into Messenger.

While testing locally the link will be a `localhost` URL, which only works on
your own computer. Real shareable links start working once it is deployed.

### If something goes wrong

| Symptom | Cause and fix |
|---|---|
| "No announcements have been posted yet" | Normal on a fresh install — go post one. If you *have* posted some, the API terminal has stopped or crashed: check Terminal 1, and confirm <http://127.0.0.1:8000/healthz/> returns `{"status": "ok"}`. |
| `Could not load announcements` on `/admin` | The backend is not reachable. Start Terminal 1. |
| `Port 8000 is already in use` | An old server is still running. Close it, or use `python manage.py runserver 8001` and set `PUBLIC_API_BASE_URL=http://127.0.0.1:8001` in `frontend/.env`. |
| `Port 4321 is in use` | Astro offers the next free port; use the URL it prints. |
| `Invalid username or password` and you are sure it is right | Re-run `python manage.py ensure_admin` — it resets the password to whatever is in `.env`. |
| `Too many attempts. Wait a minute` | The login limiter (5 tries/minute). Wait 60 seconds. |
| Signed out after restarting the browser | Expected — the session is deliberately dropped when the tab closes. Sign in again. |
| `.venv\Scripts\Activate.ps1 cannot be loaded` | PowerShell script policy. Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\activate.bat`. |

### Running the tests

```bash
cd backend && python manage.py test      # 17 tests: slugs, auth, permissions, uploads
cd frontend && npx astro check           # TypeScript + Astro diagnostics
```

---

## Deployment

### A. Cloudinary (do this first)

Render's free disk is ephemeral — anything uploaded there disappears on the next
deploy — so media must live off-box.

1. Create a free account at [cloudinary.com](https://cloudinary.com).
2. From the dashboard, copy **Cloud name**, **API Key**, and **API Secret**.

### B. Backend on Render

**With the blueprint:** push this repo to GitHub, then in Render choose
**New → Blueprint** and point it at the repo. `render.yaml` creates the web
service and the Postgres database together.

**Manually:** New → Web Service, connect the repo, then set

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Build command | `./build.sh` |
| Start command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60` |
| Health check path | `/healthz/` |

Create a Postgres instance in Render and copy its **Internal Database URL**.

Environment variables:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | a long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` |
| `DATABASE_URL` | the Internal Database URL |
| `FRONTEND_ORIGIN` | `https://your-app.vercel.app` (no trailing slash) |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | from step A |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | your admin login |
| `PYTHON_VERSION` | `3.12.6` |

`build.sh` runs migrations and `ensure_admin` on every deploy. **After the first
successful deploy, blank out `ADMIN_PASSWORD`** so it is not left sitting in the
dashboard — the account persists, and the command becomes a no-op.

### C. Frontend on Vercel

New Project → import the repo → set **Root Directory** to `frontend`. Vercel
detects Astro; the adapter handles the rest.

| Variable | Value |
|---|---|
| `PUBLIC_API_BASE_URL` | `https://your-service.onrender.com` (no trailing slash) |
| `PUBLIC_SITE_URL` | `https://your-app.vercel.app` (no trailing slash) |
| `PUBLIC_SITE_NAME` | optional |
| `PUBLIC_SITE_TAGLINE` | optional |

### D. Close the loop

1. Set `FRONTEND_ORIGIN` on Render to the real Vercel domain and redeploy.
   CORS rejects every other origin, so this must match exactly.
2. Set `PUBLIC_SITE_URL` on Vercel to the real domain — Open Graph URLs are
   built from it, and Messenger will not render a preview for a `localhost` URL.
3. Post a test announcement and paste its link into
   [Facebook's Sharing Debugger](https://developers.facebook.com/tools/debug/)
   to prime the crawler cache.

> **Free tier note:** Render spins the service down after inactivity, so the
> first request after a quiet spell takes ~30 seconds. If a page loads empty,
> that is usually a cold start — reload. Setting up an uptime pinger against
> `/healthz/` avoids it.

---

## API

Public, no auth:

| Method | Path | |
|---|---|---|
| `GET` | `/api/announcements/` | published only, newest first, `?page=` `?q=` |
| `GET` | `/api/announcements/<slug>/` | one announcement, 404 if unpublished |

Admin, `Authorization: Bearer <access token>`:

| Method | Path | |
|---|---|---|
| `POST` | `/api/auth/login/` | rate limited to 5/min |
| `POST` | `/api/auth/refresh/` | rotate the access token |
| `GET` | `/api/auth/me/` | current admin |
| `GET` `POST` | `/api/admin/announcements/` | drafts included |
| `GET` `PATCH` `DELETE` | `/api/admin/announcements/<id>/` | |
| `POST` | `/api/admin/announcements/<id>/attachments/` | multipart: `file`, `kind`, `caption` |
| `PATCH` `DELETE` | `/api/admin/attachments/<id>/` | |

Deleting an announcement also deletes its Cloudinary assets.

---

## Security

- **Passwords** hashed with Argon2 (PBKDF2 kept for verifying older hashes);
  10-character minimum plus Django's standard validators.
- **Admin API** behind JWT (30-min access, 7-day rotating refresh). Only
  `is_staff` accounts can sign in — there is no classmate account to compromise.
- **Login rate limited** to 5 attempts/minute per client; uploads to 60/minute.
- **CORS** allowlisted to `FRONTEND_ORIGIN` only; `CSRF_TRUSTED_ORIGINS` set for
  the Django admin, which stays session + CSRF protected.
- **HTTPS** enforced in production: SSL redirect, HSTS with preload, secure
  cookies, `nosniff`, `X-Frame-Options: DENY`.
- **Uploads** validated on extension, MIME type, and size (images 5 MB / files
  10 MB); images are decoded with Pillow so a renamed executable is rejected;
  filenames are stripped to `[A-Za-z0-9._-]` with path components removed, and
  stored under a random public id.
- **XSS**: announcement bodies are Markdown, rendered server-side and passed
  through a `sanitize-html` allowlist — script tags, event handlers, and
  `javascript:` URLs are discarded before the HTML reaches the page.
- **SQL injection**: all queries go through the Django ORM; there is no raw SQL.
- **Tokens** are held in memory in the browser, with the refresh token in
  `sessionStorage` (cleared when the tab closes) rather than `localStorage`.

### Known advisory

`npm audit` reports a ReDoS in `path-to-regexp`, pulled in transitively by
`@astrojs/vercel` → `@vercel/routing-utils`. The latest adapter still depends on
it and there is no non-breaking fix; it runs at build time on your own route
config, not on visitor input. Re-run `npm audit` after adapter updates.

---

## Project layout

```
backend/
  config/              settings, urls, wsgi/asgi
  announcements/
    models.py          Announcement + Attachment, slug generation, excerpts
    serializers.py     public read / admin write shapes
    views.py           public read-only + JWT admin endpoints
    validators.py      upload allowlists, size caps, filename sanitising
    storage.py         Cloudinary upload/delete, local-disk dev fallback
    throttles.py       upload rate limit
    exceptions.py      uniform { detail, errors } error envelope
    tests.py           17 tests
    management/commands/ensure_admin.py
  build.sh             Render build: install, collectstatic, migrate, ensure_admin

frontend/
  src/
    lib/               api client, admin JWT client, markdown, formatting, config
    layouts/           BaseLayout.astro — Open Graph and page chrome
    components/        cards, Gallery + ShareBar islands
      admin/           Modal, LoginModal, AnnouncementModal,
                       AttachmentsModal, ConfirmModal, AdminDashboard
    pages/             index.astro, a/[slug].astro, admin/index.astro, 404.astro
  public/              logo.png (replace me), favicon.svg, robots.txt
  scripts/             placeholder logo generator
```

# BSIT 4 — Class Announcement System

A web announcement board for BSIT 4, Saint Louis College (City of San Fernando, La Union).
The admin posts announcements; each one gets a readable, shareable link with a rich
Facebook Messenger preview. Classmates just open the link — no account, no login.

```
frontend/   Astro 7 + React islands, SSR, deploys to Vercel
backend/    Django 5 + DRF, deploys to Railway
            PostgreSQL (Railway managed) + Cloudinary (media)
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

### On phones

Most classmates open these links from Messenger on a phone, so the layout is
built for that first and verified from 320 px (an iPhone SE / small Android)
up to 1440 px, in portrait and landscape:

- **Nothing scrolls sideways.** Long words, long URLs, and wide schedule tables
  are contained — a table gets its own horizontal scroller inside the article
  rather than stretching the page.
- **Cards stack** below 640 px; the poster moves above the text.
- **The admin dashboard becomes a card list** below 700 px. The desktop table
  has five columns and cannot be read on a phone, so each announcement turns
  into a card with its Edit / Files / Share / Delete buttons in thumb reach.
- **Controls are at least 44 px tall** on touch screens, and form fields use
  16 px text so iOS Safari does not zoom in when you tap a field.
- **Heights use `dvh`**, so the mobile address bar cannot cut off a modal's
  Save button.

To re-check after a change, `frontend` has no built-in harness — the audit was
run with a throwaway Puppeteer script that loads each page at ten widths and
reports any element wider than the viewport. Chrome DevTools device toolbar
(`Ctrl+Shift+M`) covers the same ground manually.

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

**3. The logo** (already done — nothing to do here)

`frontend/public/logo.png` is the Saint Louis College seal, used in the header,
on empty states, and as the Open Graph fallback image. The original scan lives
in `frontend/brand/slclogo.jpg` and is *not* deployed.

To swap in a new seal, replace that source file and run
`python frontend/scripts/build_logo.py`. It cleans the scan to navy-on-white,
writes an 800×800 `logo.png`, and crops the central crest into the favicons
(`favicon.ico`, `favicon-32.png`, `apple-touch-icon.png`) — the full seal's ring
text is unreadable at 16px, so the tab icon uses the shield alone.

If you change `SIZE` in that script, update `LOGO_WIDTH` and `LOGO_HEIGHT` in
`src/lib/config.ts` to match — they are sent as `og:image:width`/`height`, and
Facebook trusts those tags over the real file.

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

### Who can do what

Two roles. Both sign in at `/login` with their **email address**.

| | Publisher | Admin |
|---|---|---|
| Post an announcement | yes | yes |
| Edit their own post | yes | yes |
| Edit someone else's | no | yes |
| Delete a post | no | yes |
| Add and remove publishers | no | yes |

The admin account is the one created from `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
It can also still sign in with its username, in case no email was ever set on
it. Everyone else is added by invitation.

### Adding a publisher

1. Sign in as the admin -> **Publishers** -> type their email -> **Send invite**.
2. They get an email with a **link**, valid for 7 days (`INVITE_EXPIRY_DAYS`).
3. They open it, choose their own password, and are signed straight in.

No password is ever created for them, emailed, or shown to anyone. Until the
link is opened the account has no usable password at all, so there is nothing
to intercept and nothing for you to pass on by accident. **You never see a
publisher's password** - not even as the admin.

The link is also shown in the dashboard after you send it, so if email is down
you can pass it on over Messenger and the invite still works. It can only be
used once, and issuing a new one kills the old.

Password rules: at least 10 characters, with an uppercase letter, a lowercase
letter, a number and a symbol. Common passwords are rejected even in disguise,
so `Password123!` will not be accepted.

**Resend invite** issues a fresh link, which doubles as the password reset for
someone who has forgotten theirs. **Disable** stops an account signing in while
keeping it; **Remove** deletes it. Either way, the announcements that person
posted stay on the board.

Email goes through **Brevo's HTTP API**, not SMTP. Railway - like most
container hosts - blocks outbound SMTP, which shows up as
`OSError: [Errno 101] Network is unreachable` on port 587; no credential fixes
that, because the packets never leave the container. Brevo sends over HTTPS
instead. Set `BREVO_API_KEY` to an **API key** (`xkeysib-...`, from Brevo's
SMTP & API page under *API Keys*) and `EMAIL_SENDER` to an address verified in
that account. An SMTP key (`xsmtpsib-...`) is a different credential and will
not work here.

With no key set, invites are printed to the server console instead of being
sent - fine locally, and the startup checks warn if it happens in production.

### Posting an announcement

1. Go to <http://localhost:4321/login> and sign in.
2. **New announcement** → fill in:
   - **Title** — the bold line in the Messenger preview.
   - **Body** — Markdown (`**bold**`, `- bullets`, `[links](https://…)`). The
     first ~200 characters become the grey line in the preview.
   - **Category** — Class suspension, Holiday, Exam schedule, Enrollment,
     Event, or General. This is what readers filter by.
   - **Year level** — a specific year, or All year levels. A post for "all"
     stays visible whichever year a reader filters to, so a campus-wide class
     suspension is never hidden from anyone.
   - **Re-posted from** — which page it came from (optional).
   - **Link to the original post** — the Facebook post URL (optional).
   - **Poster and attachments** — **Make a poster** draws one from a template
     (see below), and the file picker takes photos and files you already have.
     The poster is uploaded first, so it becomes the Messenger preview image.
3. Keep **Published** ticked → **Create announcement**. Everything, uploads
   included, is saved in that one dialog.
4. **Share** on that row → **Copy link** → paste into your Messenger group chat.

To change something later, **Edit** for the text or **Files** for the
attachments. Editing the title does *not* move the link, so anything you already
sent keeps working.

While testing locally the link is a `localhost` URL that only works on your own
computer. Real shareable links start working once it is deployed.

### Making the poster image

Two ways in: **Make a poster** in the New announcement dialog, or **Poster** on
any row of the dashboard afterwards. Either way you pick the kind of notice,
type the words, and it draws a 1200px PNG in the school's navy — nothing to
drag, size or align.

From the new-post dialog, **Use this poster** hands it back and it is uploaded
with the announcement. From a dashboard row, **Attach to announcement** puts it
straight on the post. **Download PNG** saves it to send by hand instead.

The templates are Notice, Meeting, Reminders, Class schedule, Exam schedule,
Class suspension, Holiday, Enrollment, Event, Deadline and General
announcement. The ones that suit the announcement's category are listed first,
but any template can be used for any post.

Two fields take a list rather than a sentence:

- **Bullets** — one per line. Indent a line to nest it under the line above,
  and again for a third level. Tabs, two spaces or four all work, as long as
  you are consistent; pasted `-` and `•` characters are stripped.
- **Entries** (schedules) — one class or exam per line, columns separated by
  `|`:

  ```
  IT 123 - Systems Administration | Mon | 8:00 - 10:00 AM | B03
  ```

  Dashes, commas or runs of spaces work as separators too, and a line missing
  its room will not shear the table. Start a line with `#` to name the columns
  yourself.

Nothing has to be sized by hand. A few subjects are set as cards, a dozen as a
table, and a full week is grouped under a heading per day; longer than that and
it goes back to one table, set in two columns where the entries are short
enough. The poster grows taller as it fills up, and only once it has run out of
room does the type shrink - the editor prints the final size under the preview,
and says so when there is more text than fits on one poster.

### Re-posting from the SLC Facebook pages

The pages in the **Re-posted from** dropdown are:

| | |
|---|---|
| Saint Louis College | <https://www.facebook.com/slc1964> |
| SLC Central Student Council | <https://www.facebook.com/SLCCSC> |
| SLC Student Help Desk | <https://www.facebook.com/SLCstudentHelpDesk> |
| SLC Registrar | <https://www.facebook.com/slcRegistrar> |
| SLC CAS-TE-IT-CRIM | <https://www.facebook.com/slccasteitcrim> |
| Society of Information Technology Students | <https://www.facebook.com/sits.slclu> |

To edit that list, change `backend/announcements/sources.py` — the dropdown is
served from there via `/api/source-pages/`, so there is one place to update.

**The system does not read those pages automatically, and cannot.** Facebook's
Graph API only returns a Page's posts to an app holding an access token issued
by an admin *of that Page*; a page being publicly viewable grants no API access.
The alternative — scraping the HTML — violates Facebook's terms, hits login
walls for logged-out requests, and breaks whenever they change their markup, so
it is not a safe base for something your class depends on.

The workflow is therefore a deliberate re-post, which takes about a minute:

1. Open the post on Facebook.
2. Copy the caption; save the poster image (right-click → *Save image as*).
3. In the admin: **New announcement** → paste the caption into the body, write a
   short title, pick the page under **Re-posted from**, paste the post URL, and
   select the saved image under **Poster and attachments**.
4. **Create announcement** → **Share** → **Copy link** → paste into Messenger.

Readers see a *"Re-posted from …"* credit under the title linking back to the
original, so the source page still gets the traffic.

### What the Messenger preview looks like

Pasting an announcement link into Messenger produces the large-image card:
poster on top, the **title** in bold, then the start of the body in grey.

That layout depends on three things, all handled for you:

- The page is **server-rendered**, so Facebook's crawler sees the tags in the
  HTML rather than an empty shell.
- `og:image:width` / `og:image:height` are sent with every announcement, taken
  from the uploaded image. Facebook needs them to commit to the large card
  instead of a small thumbnail.
- With no photo attached, the school seal is used, so a link is never previewed
  bare.

Use a poster of at least 600×315 (bigger is better; portrait posters like
1080×1350 work fine). After the first share of a new link, run it through
[Facebook's Sharing Debugger](https://developers.facebook.com/tools/debug/) if
the preview looks stale — Facebook caches previews aggressively, and *Scrape
Again* refreshes it.

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
cd backend && python manage.py test      # 22 tests: slugs, auth, permissions, uploads, sources
cd frontend && npx astro check           # TypeScript + Astro diagnostics
```

---

## Deployment

### A. Cloudinary (do this first)

Container filesystems on Railway and Render are ephemeral — anything uploaded
there disappears on the next deploy — so media must live off-box. (Railway can
attach a persistent volume, but Cloudinary is already wired up here and serves
images from a CDN, which keeps Messenger previews fast.)

1. Create a free account at [cloudinary.com](https://cloudinary.com).
2. From the dashboard, copy **Cloud name**, **API Key**, and **API Secret**.

### B. Backend on Railway

Railway runs the Django API and the Postgres database. The repo holds two apps
side by side, so the service must be pointed at `backend/` — otherwise Railway
looks at the repo root, finds no Python project, and the build fails.

**1. Add the database.** In your Railway project: **New → Database → Add
PostgreSQL**. Nothing to configure.

**2. Add the API service.** **New → GitHub Repo →** this repo. Then open the
service's **Settings**:

| Setting | Value |
|---|---|
| Root Directory | either `/` or `backend` — both build |
| Networking → Public Networking | **Generate Domain** |

**Root Directory can be either `/` or `backend`** — both work. There is a
Dockerfile and a `railway.json` at each level, and Railway picks up whichever
matches the setting:

| Root Directory | uses |
|---|---|
| `/` (default) | [`Dockerfile`](Dockerfile) + [`railway.json`](railway.json) |
| `backend` | [`backend/Dockerfile`](backend/Dockerfile) + [`backend/railway.json`](backend/railway.json) |

Both produce the same image and both were built and run against Postgres before
being committed. Either way `railway.json` supplies the start command, the
healthcheck, and the migration step, so there is nothing to configure by hand.

> **Leave the dashboard's Start Command empty.** For Dockerfile services Railway
> runs a dashboard start command in exec form — no shell — so a bare
> `--bind 0.0.0.0:$PORT` reaches gunicorn as the literal text `$PORT` and it
> exits immediately with `'$PORT' is not a valid port number`. The container
> then looks deployed while every healthcheck hits a dead process. The command
> in `railway.json` is wrapped in `sh -c '...'` so the shell expands `$PORT`
> either way; if you do set one by hand, wrap it the same way. Migrations and `ensure_admin` run as
a **pre-deploy** step (after the build, before traffic switches over), so a
failed migration stops the release instead of half-applying it.

**3. Set the variables** on the API service (**Variables** tab):

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` — type it exactly; Railway resolves the reference |
| `DJANGO_SECRET_KEY` | a long random string |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` |
| `FRONTEND_ORIGIN` | `https://your-app.vercel.app` (no trailing slash) |
| `BREVO_API_KEY` | a Brevo **API key** (`xkeysib-...`), not an SMTP key |
| `EMAIL_SENDER` | an address verified as a sender in Brevo |
| `SITE_NAME` | shown as the sender name in invite emails |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | from step A |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | your admin login |

You do **not** need to set `DJANGO_ALLOWED_HOSTS`, `PORT`, or `PYTHON_VERSION`.
The settings module picks up `RAILWAY_PUBLIC_DOMAIN` for the allowed hosts and
CSRF origins by itself, Railway injects `PORT`, and `backend/.python-version`
pins Python 3.12.

**After the first successful deploy, blank out `ADMIN_PASSWORD`** so it is not
left sitting in the dashboard. The account persists and `ensure_admin` becomes a
no-op on later deploys.

Check it worked by opening `https://<your-railway-domain>/healthz/` — it should
return `{"status": "ok"}`.

<details>
<summary>Deploying the backend to Render instead</summary>

`render.yaml` is kept as an alternative blueprint: in Render choose **New →
Blueprint** and point it at the repo, which creates the web service and Postgres
together. Set the same variables as above (Render supplies `DATABASE_URL` from
the blueprint), plus `PYTHON_VERSION=3.12.6`. The same settings module handles
both platforms — it reads `RENDER_EXTERNAL_HOSTNAME` there instead.
</details>

### C. Frontend on Vercel

New Project → import the repo → set **Root Directory** to `frontend`. Vercel
detects Astro; the adapter handles the rest.

| Variable | Value |
|---|---|
| `PUBLIC_API_BASE_URL` | `https://your-service.up.railway.app` (no trailing slash) |
| `PUBLIC_SITE_URL` | `https://your-app.vercel.app` (no trailing slash) |
| `PUBLIC_SITE_NAME` | optional |
| `PUBLIC_SITE_TAGLINE` | optional |

### D. Close the loop

1. Set `FRONTEND_ORIGIN` on Railway to the real Vercel domain and redeploy.
   CORS rejects every other origin, so this must match exactly.
2. Set `PUBLIC_SITE_URL` on Vercel to the real domain — Open Graph URLs are
   built from it, and Messenger will not render a preview for a `localhost` URL.
3. Post a test announcement and paste its link into
   [Facebook's Sharing Debugger](https://developers.facebook.com/tools/debug/)
   to prime the crawler cache.

> **Cold starts:** a small backend that has been idle can take a few seconds to
> answer its first request. If a page loads empty, reload it. Railway keeps
> services warm on a paid plan; on hosts that sleep, an uptime pinger against
> `/healthz/` avoids it.

---

## API

Public, no auth:

| Method | Path | |
|---|---|---|
| `GET` | `/api/announcements/` | published only, newest first, `?page=` `?q=` |
| `GET` | `/api/announcements/<slug>/` | one announcement, 404 if unpublished |
| `GET` | `/api/source-pages/` | the watched Facebook pages, for the editor dropdown |

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
Dockerfile             builds the API image (Root Directory = /)
railway.json           healthcheck + pre-deploy migrations

backend/
  config/              settings, urls, wsgi/asgi
  announcements/
    models.py          Announcement + Attachment, slug generation, excerpts
    serializers.py     public read / admin write shapes
    views.py           public read-only + JWT admin endpoints
    validators.py      upload allowlists, size caps, filename sanitising
    sources.py         the watched Facebook pages (edit the list here)
    storage.py         Cloudinary upload/delete, local-disk dev fallback
    throttles.py       upload rate limit
    exceptions.py      uniform { detail, errors } error envelope
    tests.py           22 tests
    management/commands/ensure_admin.py
  Dockerfile           same image for Root Directory = backend
  railway.json         healthcheck + pre-deploy migrations
  build.sh             Render build: install, collectstatic, migrate, ensure_admin

frontend/
  src/
    lib/               api client, admin JWT client, markdown, formatting, config
      poster/          the poster maker: theme, block vocabulary, layout
                       engine (wrapping, fitting, page growth), the parsers
                       for typed lists and schedules, and the templates
    layouts/           BaseLayout.astro — Open Graph and page chrome
    components/        cards, Gallery + ShareBar islands
      admin/           Modal, LoginModal, AnnouncementModal,
                       AttachmentsModal, PosterModal, ConfirmModal,
                       AdminDashboard
    pages/             index.astro, a/[slug].astro, admin/index.astro, 404.astro
  public/              logo.png (the seal), favicon.ico/-32/apple-touch, robots.txt
  brand/               slclogo.jpg - original scan, not deployed
  scripts/             build_logo.py - regenerates the logo and favicons
```

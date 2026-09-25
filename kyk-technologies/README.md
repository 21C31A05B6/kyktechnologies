# KYK Technologies — Full-Stack Web Platform

A fully-featured recruitment, software services, and AI intelligence website
built with Python / Flask on the backend and plain HTML/CSS/JavaScript on the
frontend. No Node.js, no build step, no framework lock-in.

---

## Quick start (development)

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:3000
```

Default admin credentials (change before any real use):
- **Email:** admin@kyktechnologies.com
- **Password:** KYKAdmin@2026

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **Yes in prod** | JWT signing secret. |
| `DATABASE_URL` | Optional | SQLAlchemy URL. If unset, JSON files under `/data` are used. Example: `postgresql+psycopg2://user:pass@host:5432/kyk` |
| `SMTP_HOST` | Optional | SMTP server for transactional email. |
| `SMTP_PORT` | Optional | Default `587`. |
| `SMTP_USER` | Optional | SMTP login username. |
| `SMTP_PASSWORD` | Optional | SMTP login password. |
| `SMTP_FROM` | Optional | Sender address. |
| `PORT` | Optional | HTTP port (default `3000`). |
| `DEBUG` | Optional | Set `1` for Flask debug (never in production). |

Without `SMTP_HOST`, emails are logged to `data/outbox.json` and printed to
the console so the full flow can be exercised in dev without a mail provider.

---

## Storage backends

### JSON files (default, zero config)

Every collection lives as one file under `/data`. Thread-safe. Fine for demo
and small production use.

### PostgreSQL (recommended for production)

```bash
pip install psycopg2-binary
export DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/kyk
# Table is auto-created on first run.
# Migrate existing JSON data (idempotent):
DATABASE_URL=postgresql+psycopg2://... python migrate_json_to_sql.py
```

Any SQLAlchemy dialect works (MySQL, SQLite for testing, etc.).

---

## Project structure

```
app.py                  Flask app — all routes
db.py                   Storage dispatcher (JSON or SQL)
db_json.py              JSON-file store (dev default)
db_sql.py               SQLAlchemy store (production)
migrate_json_to_sql.py  One-off JSON → SQL migration
security.py             JWT tokens, password hashing
email_util.py           Transactional email (SMTP or dev log)
seed.py                 Seeds demo jobs, insights, admin account

static/
  index.html            Home — animated hero, network diagram, stats
  global-recruitment.html  Global talent placement
  ai.html               Intelligence / AI services + core visualisation
  services.html         Software & web services
  careers.html          Job search + 4-step application wizard
  insights.html         Blog / articles — category filter, search, modal
  about.html            Company / mission / vision
  contact.html          Contact form with success animation
  admin.html            Admin dashboard — kanban, chart, audit log
  privacy.html          Privacy policy
  terms.html            Terms of service
  css/style.css         Design system (glassmorphism, animations, themes)
  js/main.js            Experience engine (cursor, tilt, reveal, AI widget)

uploads/                Uploaded résumés (gitignore this)
data/                   JSON-file store (gitignore this)
requirements.txt        Python dependencies
```

---

## API reference

### Public

| Method | Path | Description |
|---|---|---|
| GET | `/api/jobs` | List active jobs (`?q=`, `?department=`, `?location=`, `?type=`) |
| GET | `/api/jobs/:id` | Single job |
| POST | `/api/applications` | Submit job application (multipart/form-data) |
| POST | `/api/talent` | Join talent pool (multipart/form-data) |
| POST | `/api/contact` | Contact message (JSON) |
| POST | `/api/newsletter` | Newsletter subscribe (JSON) |
| GET | `/api/insights` | List published insights |
| GET | `/api/insights/:id` | Single insight |
| POST | `/api/assistant` | KYK AI assistant (`{message}`) |
| GET | `/api/stats` | Public site statistics |

### Admin (Bearer token required)

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Login → JWT token |
| GET | `/api/admin/overview` | Dashboard KPIs |
| GET/POST | `/api/admin/jobs` | List / create jobs |
| PUT/DELETE | `/api/admin/jobs/:id` | Update / delete job |
| GET | `/api/admin/applications` | All applications |
| PUT | `/api/admin/applications/:id` | Update status |
| GET | `/api/admin/talent` | All talent profiles |
| PUT | `/api/admin/talent/:id` | Update recruitment stage |
| GET | `/api/admin/contacts` | All contact messages |
| PUT | `/api/admin/contacts/:id` | Update read status |
| GET | `/api/admin/newsletter` | All subscribers |
| GET/POST | `/api/admin/insights` | List / create insights |
| PUT/DELETE | `/api/admin/insights/:id` | Update / delete insight |
| GET | `/api/admin/audit-log` | Admin activity log |
| GET | `/api/admin/files/:filename` | Download uploaded résumé |

---

## Security notes

Active hardening:
- JWT authentication with 8-hour expiry on all admin routes
- bcrypt-style password hashing (PBKDF2-HMAC-SHA256, 260 000 iterations)
- Per-IP rate limiting on every public POST endpoint
- Stricter rate limiting on `/api/auth/login`
- Magic-byte file-content validation on résumé uploads
- 5 MB file size cap enforced at Flask and OS level
- Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`, `HSTS` (when over HTTPS)
- Audit log recording all admin logins and mutations with IP and timestamp
- Input length caps on all user-supplied fields

**Before going to production:**
1. `SECRET_KEY` — set to a long random string: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Change the default admin password
3. Point `DATABASE_URL` at a real database
4. Set `SMTP_*` variables so emails actually send
5. Run behind a TLS-terminating reverse proxy (nginx, Caddy)

---

## Production deployment (Gunicorn + Caddy)

```bash
pip install gunicorn psycopg2-binary
export SECRET_KEY="<your-secret>"
export DATABASE_URL="postgresql+psycopg2://..."
export SMTP_HOST="smtp.sendgrid.net"
gunicorn -w 4 -b 127.0.0.1:3000 app:app
```

`/etc/caddy/Caddyfile`:
```
kyktechnologies.com {
    reverse_proxy 127.0.0.1:3000
}
```

Caddy handles TLS automatically. No Certbot needed.

---

## Connecting a real LLM to the AI assistant

The `/api/assistant` endpoint is a rule-based FAQ matcher by default.
To connect Claude (or any other model), replace the `assistant_reply()`
function body in `app.py`:

```python
import anthropic

@app.post("/api/assistant")
@rate_limit(max_requests=30, window_seconds=600)
def assistant_reply():
    data = request.get_json(silent=True) or {}
    message = clean(data.get("message"), 500)
    if not message:
        return jsonify({"reply": "Ask me about our services, open roles, or how to get in touch."})
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=(
            "You are the KYK Technologies AI assistant. "
            "Answer questions about KYK's services (Recruitment, Software, AI), "
            "open roles, and how to contact the team. Be concise."
        ),
        messages=[{"role": "user", "content": message}],
    )
    return jsonify({"reply": response.content[0].text})
```

Install the SDK: `pip install anthropic`
Set the key: `export ANTHROPIC_API_KEY=sk-ant-...`
The frontend widget calls the same `/api/assistant` endpoint — no changes needed there.

---

## Features implemented

### Frontend (all pages)
- Glassmorphism design system — glass panels, blur, borders, inset highlights
- Animated backdrop — gradient blobs, grid, particle field
- Mouse-follow glow on all cards
- 3D tilt on hover (6° max, desktop only)
- Magnetic button hover effect
- Custom cursor with scale-on-hover (desktop, fine pointer only)
- Dark / light / aurora theme switcher (persisted to localStorage)
- Branded loading screen (~800 ms, skipped for repeat visitors by browser cache)
- Page transition veil (fade between pages)
- Scroll-reveal animations (IntersectionObserver)
- Animated number counters (count-up on scroll)
- Floating KYK AI assistant widget (all pages)
- Responsive mobile design throughout
- `prefers-reduced-motion` respected — all animations disable cleanly

### Home
- Gradient headline, glass stat strip, animated counters
- Animated SVG network diagram (pulsing nodes, flowing dashes, rotating ring)

### AI page
- SVG AI-core visualisation with pulsing nodes and orbit ring

### Careers
- Advanced job search (text + department / location / type filters)
- 4-step application wizard (Personal → Professional → Resume → Review)
- Drag-and-drop résumé upload with progress bar and file preview
- Animated success overlay on submission

### Insights
- Category pill filter + live search
- Reading-time estimate per article
- Article detail modal with share buttons (copy link, LinkedIn, X)
- Newsletter subscription form

### Admin dashboard
- KPI stat cards with animated counters
- Application activity bar chart (canvas, no external library)
- Drag-and-drop Kanban recruitment pipeline (6 stages)
- Insight create / edit / publish / unpublish / delete
- Admin activity log (all logins and mutations with IP)
- Résumé download links

### Backend
- Dual-backend storage: JSON files (dev) or SQLAlchemy/PostgreSQL (prod)
- Zero-config JSON-to-SQL migration script
- Transactional email (SMTP in prod, console log in dev)
- Magic-byte résumé file validation
- Security headers on every response
- Audit log on all admin actions
- Rule-based AI assistant (drop-in LLM swap documented above)

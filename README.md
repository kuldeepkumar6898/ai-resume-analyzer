# AI Resume Analyzer — Phase 3

Phase 3 upgrades the Phase 2 project with a practical Resume Builder and PDF/DOCX export.

## Features
- Phase 1 ATS-style resume analysis
- Phase 2 AI-style resume rewriting
- Phase 2 skill-gap analyzer
- Resume Builder form
- Professional Summary
- Experience, Projects, Education, Certifications
- Skills and contact details
- PDF export
- DOCX export
- Download generated resume
- Responsive UI
- No external AI API required

## Install

```bash
python -m pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open:
`http://127.0.0.1:5000`

## Export
PDF uses ReportLab.
DOCX uses python-docx.

## Important
The rewrite/analyzer logic is local rule-based AI-style logic. Do not add qualifications, achievements or skills that are not true.

## Phase 5 — Real AI Integration

Phase 5 adds an optional OpenAI Responses API integration. The app continues to work with local fallback features when no API key is configured.

### Enable Real AI

Set environment variables before starting Flask:

Windows PowerShell:
`$env:OPENAI_API_KEY="your_api_key"`
`$env:OPENAI_MODEL="gpt-5.6-luna"`

macOS/Linux:
`export OPENAI_API_KEY="your_api_key"`
`export OPENAI_MODEL="gpt-5.6-luna"`

Never put the API key in frontend JavaScript or commit it to Git.

## Phase 5 — Module 3: ATS Score Engine + ATS Simulator
- Added deterministic ATS scoring engine with Content, Structure, Length, Impact and Keyword dimensions.
- Added ATS parser-readiness checks and formatting warnings.
- Added keyword intelligence against an optional target job description.
- Added detected section coverage, action-bullet and quantified-achievement checks.
- Added `/api/ats-simulator` endpoint and dashboard UI.
- Existing AI, Job Match, Premium Builder, authentication and resume history features remain available.

## Phase 5 — Module 4: AI Resume Builder & Job-Specific Versions

Added:
- Job-targeted AI resume generation using the configured OpenAI provider, with a safe local fallback.
- Multiple independent resume versions without overwriting the master resume.
- Version metadata: target role, job description and version label.
- Save, open, duplicate and delete version workflow.
- AI professional summary, improved factual bullets, priority keywords and missing-keyword analysis.
- Existing premium templates, profile photo, accent colors, ATS simulator, job match, optimization, authentication and export features remain available.

### Module 4 endpoints
- `POST /api/ai-build-resume`
- `GET /api/resume-versions`
- `POST /api/resume-versions`
- `POST /api/resume-versions/<id>/duplicate`
- `PATCH /api/resume-versions/<id>`

## Phase 5 — Module 5: Job Application Tracker

Added a user-scoped application management workspace with:
- Application pipeline statuses: Saved, Applied, Screening, Interview, Offer, Rejected, Withdrawn.
- Add, edit, delete and quick-status cycling.
- Company, role, location, salary, job URL, dates, recruiter contact and notes.
- Dashboard counts for total, active applications, interviews, offers and rejections.
- Search and status filters.
- Dedicated `/applications` page and REST API endpoints.
- Existing resume versions, ATS simulator, AI features, premium templates and exports remain available.

### Module 5 endpoints
- `GET /applications`
- `GET /api/applications`
- `POST /api/applications`
- `GET /api/applications/<id>`
- `PATCH /api/applications/<id>`
- `DELETE /api/applications/<id>`


## Phase 6 — Admin Dashboard & Production Features
- Admin dashboard with platform KPIs, user management, application analytics and audit trail.
- Admin-only routes and role/status controls.
- Optional first-run admin provisioning via `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`.
- `SECRET_KEY` and upload size configuration.
- Activity logging for key user/admin actions.

### Production environment
PowerShell example:
```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="change-this-strong-password"
$env:ADMIN_NAME="Administrator"
python app.py
```

## Phase 6 — Module 2: Advanced Analytics + AI Usage Monitoring
- Advanced admin analytics dashboard with 7/30/90/365-day windows.
- AI usage tracking by feature and provider with success/failure and response time.
- Daily AI activity, feature adoption, provider distribution and top AI users.
- CSV analytics export for administrators.
- Platform trend datasets for registrations, resumes and applications.
- AI activity is logged only for authenticated users and contains feature metadata, not resume text or job-description content.

## Phase 6 — Module 3: Production Security + Deployment

Production hardening added:
- Environment-based configuration with `.env.example` (never commit real secrets).
- Secure HTTP-only, SameSite session cookies with optional Secure cookies for HTTPS.
- Flask `ProxyFix` support for reverse proxies/load balancers.
- Configurable trusted hosts via `ALLOWED_HOSTS`.
- Same-origin protection for browser state-changing requests.
- Security response headers and HSTS when HTTPS cookies are enabled.
- 10 MB configurable request/upload limit with PDF/DOCX signature validation.
- Uploaded resume files are stored under random temporary names and removed after parsing.
- Export endpoints now require authentication and use non-guessable filenames.
- Structured server logging plus JSON 413/500 API responses.
- `/health` liveness endpoint and `/ready` database readiness endpoint.
- SQLite foreign keys, WAL mode and busy timeout for better production behavior.
- Optional Flask-Limiter protection; for multiple workers use Redis via `RATE_LIMIT_STORAGE_URI`.
- Gunicorn configuration for Linux/Unix production deployment.
- Dockerfile and `.dockerignore` for container deployment.
- `wsgi.py` application entry point.

### Production setup
1. Copy `.env.example` to `.env` and replace every placeholder secret/password.
2. Set `APP_ENV=production`, `SECRET_KEY` to a long random value and `SESSION_COOKIE_SECURE=true` when HTTPS is active.
3. Set `ALLOWED_HOSTS` to your real domain(s), e.g. `resume.example.com`.
4. Set `OPENAI_API_KEY` only through the server environment if Real AI is required.
5. For multi-worker deployments, configure a shared Redis-backed rate-limit store.
6. Run behind HTTPS using a reverse proxy such as Nginx or a managed platform TLS endpoint.

### Linux/Gunicorn
```bash
python -m pip install -r requirements.txt
cp .env.example .env
# edit .env
 gunicorn -c gunicorn.conf.py wsgi:application
```

### Docker
```bash
docker build -t ai-resume-analyzer .
docker run --env-file .env -p 8000:8000 ai-resume-analyzer
```

For persistent production data, mount a volume containing `RESUME_DB_PATH`; do not rely on a disposable container filesystem.


## PostgreSQL production database (Phase 7)

The app now supports both SQLite (local development) and PostgreSQL (production). Set `DATABASE_URL` to a PostgreSQL connection string and the app will create the required tables automatically on startup. On Render, use the Postgres **Internal Database URL** from the database Connect page and keep the web service and database in the same region.

For Render deployment:
1. Create a Render Postgres database.
2. In the web service Environment variables, add `DATABASE_URL` using the database Internal URL.
3. Keep `RESUME_DB_PATH` only as the local SQLite fallback; it is ignored when `DATABASE_URL` is set.
4. Redeploy the web service.

Do not commit a real `.env` file or expose database credentials.

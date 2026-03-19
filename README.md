# CareCircle

CareCircle is a Django application for coordinating family, volunteer, and professional caregiving inside a private role-based Circle of Care. It includes a caregiver dashboard, task coordination workflows, shared care feed, member management, voice logs, insights, alerts, notifications, and demo data for walkthroughs.

This repository is intended to be self-contained so that any collaborator with access can clone it, install the dependencies, run the database migrations, seed demo data, and start using the app locally.

## Highlights

- Django 6 + Django REST Framework backend
- Server-rendered UI plus JSON API endpoints
- Role-based circle membership flows
- Task claim and verification workflow
- Shared care feed and notifications
- Voice log ingestion and local transcription support
- Insights and trend analysis commands
- SQLite for local development, PostgreSQL-ready for production
- Production-ready Gunicorn + WhiteNoise setup

## Tech stack

- Python 3.13.7 tested locally
- Django 6.0.3
- Django REST Framework 3.17.0
- faster-whisper 1.1.1
- Gunicorn 23.0.0
- WhiteNoise 6.9.0
- PostgreSQL support via `psycopg`

## Project structure

- [config/](config) — Django project settings, URL config, WSGI/ASGI entrypoints
- [core/](core) — main application logic, models, serializers, views, admin, tests
- [docs/](docs) — delivery and interface planning notes
- [ops/](ops) — release and server startup helper scripts
- [templates/](templates) — server-rendered templates
- [static/](static) — source static assets
- [media/](media) — uploaded/generated media during runtime

## Requirements

Anyone setting up this project locally should have:

- Git
- Python 3.13+ recommended
- `pip`
- `venv` support (`python3 -m venv`)
- macOS, Linux, or WSL recommended

Optional for production:

- PostgreSQL
- Reverse proxy / HTTPS termination (Nginx, Caddy, platform load balancer, etc.)

## Clone and run locally

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd CareCircle
```

### 2. Create and activate a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local env file or export variables in your shell. Start from [.env.example](.env.example).

Minimum local setup:

```bash
export DJANGO_DEBUG=true
export DJANGO_SECRET_KEY='dev-only-secret-key-change-me'
export DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost,testserver'
export DJANGO_CSRF_TRUSTED_ORIGINS='http://127.0.0.1:8000,http://localhost:8000'
```

If you do not set `DATABASE_URL`, the app uses the local SQLite file `db.sqlite3`.

### 5. Run database migrations

```bash
python manage.py migrate
```

### 6. Seed demo data

```bash
python manage.py seed_demo_circle
```

### 7. Start the app

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Demo accounts

The demo seeding command creates or refreshes a sample circle and the following users:

- `demo.admin@carecircle.local` / `CareCircleAdmin!2026`
- `demo.james@carecircle.local` / `CareCircleMember!2026`
- `demo.anita@carecircle.local` / `CareCircleMember!2026`
- `demo.rita@carecircle.local` / `CareCircleMember!2026`

If you want to remove seeded data:

```bash
python manage.py purge_demo_circle --yes
```

## Common local commands

Run tests:

```bash
python manage.py test core
```

Run Django system checks:

```bash
python manage.py check
```

Run production-oriented deploy checks:

```bash
DJANGO_DEBUG=false \
DJANGO_SECRET_KEY='replace-with-a-long-random-secret' \
DJANGO_ALLOWED_HOSTS='127.0.0.1,localhost' \
DJANGO_CSRF_TRUSTED_ORIGINS='https://example.com' \
python manage.py check --deploy
```

Validate all empty states:

```bash
python manage.py prove_empty_state --all
```

Keep the app empty after validation:

```bash
python manage.py prove_empty_state --all --no-restore
```

Run the insights trend analyzer:

```bash
python manage.py analyze_insight_trends
```

Run the analyzer for one circle:

```bash
python manage.py analyze_insight_trends --circle-id 2 --days 14
```

## Main routes

UI routes:

- `/` — landing page
- `/login/` — login page
- `/dashboard/` — dashboard demo
- `/tasks/` — tasks interface
- `/logs/` — care logs / voice logs page
- `/alerts/` — alerts interface
- `/profile/` — profile page
- `/notifications/` — notifications page

Key API routes:

- `/api/health/`
- `/api/dashboard/`
- `/api/feed/`
- `/api/insights/`
- `/api/tasks/`
- `/api/voice-logs/`
- `/api/alerts/`
- `/api/profile/`
- `/api/notifications/`
- `/api/circles/`

## Environment variables

The repository includes [.env.example](.env.example) for production-style configuration.

Important variables:

- `DJANGO_DEBUG` — `true` for local dev, `false` for deployment
- `DJANGO_SECRET_KEY` — required in every environment
- `DATABASE_URL` — optional for local SQLite, required for PostgreSQL-based deployment
- `DJANGO_ALLOWED_HOSTS` — comma-separated hostnames
- `DJANGO_CSRF_TRUSTED_ORIGINS` — comma-separated HTTPS origins
- `DJANGO_SECURE_SSL_REDIRECT` — should be `true` in deployment
- `DJANGO_SECURE_HSTS_SECONDS` — recommended for deployment
- `DJANGO_DB_SSL_REQUIRE` — use `true` for managed Postgres when required
- `VOICE_TRANSCRIPTION_MODEL` — `base`, `small`, `medium`, etc.
- `VOICE_TRANSCRIPTION_ENABLED` — `true` or `false`

## Production deployment

This repository is ready for a standard Django deployment.

### Production checklist

1. Set real production environment variables
2. Point `DATABASE_URL` to PostgreSQL
3. Run migrations
4. Collect static files
5. Run deploy checks
6. Start Gunicorn behind HTTPS

### Release script

Use the helper script in [ops/release.sh](ops/release.sh):

```bash
./ops/release.sh
```

The script runs:

- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`
- `python manage.py check --deploy`

### Start script

Use the helper script in [ops/start-gunicorn.sh](ops/start-gunicorn.sh):

```bash
PORT=8000 ./ops/start-gunicorn.sh
```

Or run Gunicorn directly:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

## Health check

The readiness endpoint is:

```text
GET /api/health/
```

Expected response shape:

```json
{
  "status": "ok",
  "service": "carecircle",
  "debug": false,
  "timestamp": "..."
}
```

## Voice transcription notes

The app currently uses local `faster-whisper` support.

- No external API key is required for the current setup
- Heavier models improve accuracy but increase memory usage
- `base` is suitable for local development
- `small` is a better default for production if machine resources allow

## Repository handoff notes

If someone with repository access wants to run this project on their own machine, they only need to:

1. Clone the repository
2. Create a Python virtual environment
3. Install [requirements.txt](requirements.txt)
4. Configure environment variables
5. Run migrations
6. Seed demo data if desired
7. Start the development server

No additional private services are required for the default local SQLite workflow.

## GitHub overwrite workflow

If you want this codebase to replace the contents of an existing GitHub repository, the safest flow is:

```bash
git init -b main
git add .
git commit -m "Replace repository with CareCircle app"
git remote add origin <existing-github-repo-url>
git push --force origin main
```

`--force` is required only if the remote repository already contains unrelated or outdated code that you intend to replace.

## Status

Validated locally:

- `python manage.py test core`
- `python manage.py prove_empty_state --all`
- `python manage.py check --deploy` with production-style environment variables
- Gunicorn startup + `/api/health/` response

## Additional documentation

- Delivery plan: [docs/interface-phases.md](docs/interface-phases.md)

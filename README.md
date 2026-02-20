# TD Management and Verification System

Centralized, secure TD (Table Drawing) management and verification for plant staff. Publicly hosted, login-protected, developer-created accounts only.

## Stack

- **Backend:** Flask (server-rendered)
- **Database:** PostgreSQL
- **Session store:** Redis
- **ORM:** SQLAlchemy
- **Auth:** Session-based (Redis), bcrypt passwords, CSRF (Flask-WTF)
- **Frontend:** HTML, Jinja2, Bootstrap 5

## Environment variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Long random string (required in production) |
| `DATABASE_URL` | PostgreSQL URL (e.g. `postgresql://user:pass@host:5432/db`) |
| `REDIS_URL` | Redis URL (e.g. `redis://localhost:6379/0`) |
| `FLASK_ENV` | `production` or `development` |
| `FLASK_DEBUG` | `0` in production |
| `PORT` | Port for the app (Railway sets this) |
| `BACKUP_DIR` | Optional; directory for DB backups |

## Setup

1. Create a virtualenv and install dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Optional** – Set `DATABASE_URL` and `REDIS_URL` for PostgreSQL/Redis. If you leave them unset:
   - **Database:** SQLite is used (`td_checklist.db` in the project root), so you can run init and create the first user without installing PostgreSQL.
   - **Redis:** You still need Redis running for the app (sessions, rate limiting). For init/create-user scripts, Redis is not required.

3. Create tables:
   ```bash
   python scripts/init_db.py
   ```
   (Uses PostgreSQL if `DATABASE_URL` is set; otherwise uses SQLite.)

4. Create the first developer account:
   ```bash
   python scripts/create_developer.py
   ```

5. Run locally (development):
   ```bash
   set FLASK_ENV=development
   set FLASK_DEBUG=1
   python run.py
   ```
   For the full app you need PostgreSQL and Redis (or set `DATABASE_URL` / `REDIS_URL`). To only create tables and the first user, SQLite is enough and PostgreSQL can be skipped.

## Railway deployment

- Connect the repo and set `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`.
- Build and deploy; the `Procfile` runs Gunicorn.
- Run migrations/init and create the first developer via Railway shell or one-off job.

## Roles

- **Developer:** Users, backup/restore, maintenance mode, audit logs, active sessions, logout all.
- **Admin:** Full TD management (lines, FG codes, TD items), verification, export logs.
- **Operator:** Verification only (read TD, submit checklist).

## Security

- HTTPS enforced in production; secure cookies (HttpOnly, Secure, SameSite=Lax).
- Login rate limit: 5 attempts → 2-minute cooldown (Redis).
- Session inactivity timeout: 30 minutes; activity refreshes on each request.
- Passwords: bcrypt, min 10 chars, number, letter, symbol.
- No hard delete: users and TD entities use `is_active = False`.
- Restore DB: double confirmation, maintenance mode, flush all sessions.

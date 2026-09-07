# Shared Household Chores

Tasks 1 and 2 provide the database, shared page, PIN login, and household member
management. Chore workflows, reminders, and API endpoints follow in later tasks.

## Local setup (PowerShell)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed
(`winget install --id astral-sh.uv -e`), then open a new terminal. Run these
commands from the directory containing `manage.py` and `pyproject.toml`:

```powershell
uv sync --locked
uv run --locked python manage.py migrate
uv run --locked python manage.py createhouseholdadmin Admin
uv run --locked python manage.py createsuperuser
uv run --locked python manage.py runserver
```

Open http://127.0.0.1:8000/login/ and use the username and privately prompted PIN
from `createhouseholdadmin`. The command creates the first primary admin only.
The initial migration creates the single household. `createsuperuser` is optional
and creates separate internal-management credentials for `/admin/`; choose a
different username. Application roles are separate from staff/superuser privileges.

## Account management

After logging in as an admin, open **Members** to create accounts, reset member
PINs, and unlock accounts. Only the primary admin sees promotion/demotion actions;
direct requests enforce the same restrictions. Both admin roles can create
members, reset member PINs, and unlock other accounts, including locked admins.
Reset PINs appear only in the immediate, non-cacheable response; share them with
the member. Resets do not expire and do not unlock locked accounts automatically.

Usernames are case-sensitive (`Alex` and `alex` are different accounts). PINs
contain exactly six ASCII digits and cannot start with zero. **Change PIN** checks
the current PIN and rejects the current or immediately previous PIN. Changes
and resets invalidate every session through Django's session authentication hash;
the current session is also ended on self-service changes. Lockout occurs after
10 consecutive failed attempts and requires manual unlocking. Existing PIN
sessions stay invalid after unlocking, so users must log in again. Sessions
persist across browser restarts and expire after 24 hours without activity.

Account audit records contain change/reset, lock, and unlock events, never PINs
or individual login/logout events. Internal Django admin remains a development
tool that can bypass application rules, including recovery if all admins lock
themselves out. No household accounts or demo credentials are created by tests.

## Dependencies and reproducibility

uv manages `.venv` automatically; manual activation and Conda are unnecessary.
Python is pinned to 3.13.2 in `.python-version`. `uv sync --locked` installs the
versions recorded in `uv.lock` and downloads the pinned Python if necessary.
Commit `pyproject.toml`, `.python-version`, and `uv.lock` when sharing the project.

Add a dependency with `uv add package-name`, or remove it with `uv remove
package-name`. These update the project and lockfile together. `requirements.txt`
is a compatibility export, not the source of truth. Regenerate it after changes:

```powershell
uv export --locked --format requirements-txt --no-hashes --output-file requirements.txt
```

See the [uv project guide](https://docs.astral.sh/uv/guides/projects/) for details.

## Checks

Run repeat-safe reminders manually with `uv run --locked python manage.py send_reminders`.
For ongoing local use, configure Windows Task Scheduler to run the project's
`.venv/Scripts/python.exe` with arguments `manage.py send_reminders`, set **Start in**
to this project directory, and repeat hourly. Due reminders are once per date;
rejected-overdue member reminders start immediately, and admin reminders begin
after 24 hours. Pausing persists until an admin resumes reminders on the chore.

For desktop/mobile UI checks, run `uv run playwright install chromium`, set
`$env:RUN_BROWSER_TESTS = '1'`, then run the tests below. Without that environment
variable the Chromium tests are skipped. Screenshots go to `.artifacts/`.

```powershell
uv run --locked python manage.py check
uv run --locked python manage.py makemigrations --check --dry-run
uv run --locked python manage.py test
```

SQLite data lives in `db.sqlite3` and photos in `media/completion_photos/`.
Both persist between server restarts and are excluded from Git. Django serves
uploads locally while DEBUG is enabled. Upload validation belongs to the
completion submission workflow in task 4; no public upload endpoint exists yet.

`chores/services.py` is the shared business-operation entry point for future
pages and API calls. Chore deletion sets `deleted_at`; protected relationships
preserve attempts, photos, notifications, and audit history. Internal history
screens are read-only. Recurrence retains its original scheduled date separately
from the editable due date, with a uniqueness constraint to prevent duplicates.

The custom user stores its hashed PIN in Django's password field, with fields
for the previous hash, lockout, PIN changes, and session version. Database-backed
sessions use a sliding 24-hour expiry. Shared account rules are implemented in
`chores/accounts.py`, with PIN-session version checks in `chores/middleware.py`.

HTMX 2.0.4 is vendored from https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
with its upstream license in `chores/static/chores/vendor/`. The shared template
loads it locally for later partial updates. CSS switches cards to a single
column at 640px and includes keyboard focus and skip navigation.

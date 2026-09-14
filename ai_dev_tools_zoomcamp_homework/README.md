# Shared Household Chores

A local, single-household Django app for assigning chores and tracking completion.
Includes PIN accounts, role permissions, recurring schedules, approval workflows,
photos, audit history, notifications, reminders, responsive dashboards, HTMX,
Channels live updates, and a documented Django REST Framework demo API.

## Screenshots

The local demo includes a household dashboard, member workload overview, recurring
schedule, and audit history. These screenshots show the admin view with demo data.

### Household dashboard

Filter chores by category and priority, check due-work counts, and create or assign chores.

![Admin dashboard with category and priority filters, status counts, and today's chores](screenshots/Screenshot%202026-09-07%20163959.png)

### Member workload

Compare each member's active chores by low, medium, and high priority.

![Member workload table showing chore counts grouped by priority](screenshots/Screenshot%202026-09-07%20164012.png)

### Recurring schedule

Preview the next month's recurring chores on their original schedule.

![Recurring schedule preview listing upcoming dates and assigned members](screenshots/Screenshot%202026-09-07%20164102.png)

### History

Review chore events, completion notes, and rejection feedback in the household audit history.

![Household history showing a rejected submission, its note, and the original chore creation](screenshots/Screenshot%202026-09-07%20164029.png)

## Run the demo (PowerShell)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed
(`winget install --id astral-sh.uv -e`), then open a terminal in this directory:

```powershell
uv sync --locked
uv run --locked python manage.py migrate
uv run --locked python manage.py seed_demo
uv run --locked python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/login/. `runserver` uses Daphne/ASGI, serves local
static assets, and supports WebSockets. Keep a single serving process because the
channel layer is in memory. No Docker, Redis, deployment, or cloud account is needed.
Python is pinned to 3.13.2; uv manages `.venv` and installs `uv.lock` versions.

Initial local demo credentials:

| Username | PIN | Role |
| --- | --- | --- |
| demo_admin | 123456 | Primary admin |
| demo_helper | 234567 | Secondary admin |
| demo_alex | 345678 | Member |
| demo_sam | 456789 | Member |
| demo_jamie | 567891 | Member |

`seed_demo` creates eight example chores: varied categories/priorities, overdue
work, daily/weekly series, a photo submission awaiting approval, a completed chore,
and a rejected submission. Repeating it preserves existing PINs, dates, statuses,
and history; it only adds missing demo records. It refuses to replace an existing
non-demo primary admin. To keep an existing household separate, use another SQLite
file in the same terminal before running migrate, seed, and runserver:

```powershell
$env:HOUSEHOLD_DB = Join-Path (Get-Location) 'demo.sqlite3'
```

For a household without demo data, run `migrate`, then
`uv run python manage.py createhouseholdadmin Admin` instead of `seed_demo`.
The command privately prompts for a PIN and creates only the first primary admin.
Optional `uv run python manage.py createsuperuser` creates separate internal
management credentials for `/admin/`; use a different username.

## Demonstrate the workflow

1. Log in as `demo_admin`; use **Members** to create a member or promote one.
2. Open **Dashboard**, choose **Create and assign chore**, and assign it to
   `demo_alex`. Enable approval and optionally require a completion photo.
3. In a private window or separate browser profile, log in as `demo_alex`.
   The assignment appears without reloading. Filter by category/priority,
   open the chore, enter a note, attach a JPEG/PNG/WebP photo, and submit.
4. In the admin window, open the pending chore. Approve it or reject it with
   a reason. The member can read that reason and submit a fresh attempt.
5. Review **History**, **Notifications**, and the one-month **Schedule** preview.
   Completed chores leave the dashboard. Workload counts are grouped by priority.
6. Try a daily chore dated several days ago. Completion creates a pending admin
   catch-up choice: create all missed dates or skip them. The next occurrence
   waits for that choice. Approval-required recurrence advances only on approval.
7. Stop and restart the server; accounts, chores, notes, photos, and history persist.

Major due-date, priority, and assignment edits require a note. Reassignment notifies
both affected members. Duplication copies details/recurrence into an independent
series with a new assignee/date. Deletion preserves history and cannot be undone.
Members may undo their own completion within 15 minutes of final completion
(or submission while awaiting approval). Generated recurring occurrences remain.
Admins can reactivate completed chores with an audit note.

## Accounts and sessions

Usernames are case-sensitive. PINs are exactly six ASCII digits with no leading
zero and use Django password hashing. Self-service changes check the current PIN
and reject the current and immediately previous PIN. Changes and admin resets
invalidate all active sessions. Reset PINs do not expire and appear only in the
immediate non-cacheable response; share them with the member.

Ten consecutive failed login attempts lock the account until an admin unlocks it.
Resetting a PIN does not unlock the account. Both admin roles can create members,
reset member PINs, and unlock other accounts. Only the primary admin can promote
members or demote secondary admins. Primary-admin transfer is out of scope.
Internal Django admin can bypass application rules for local recovery/debugging.

Sessions persist across browser restarts and expire after 24 hours of inactivity.
Passive live refreshes do not extend the timer. Sockets recheck session validity,
reconnect after interruptions, and preserve unfinished form edits when updates
arrive. The audit log records PIN changes/resets and lock/unlock events without
PIN values, individual failed attempts, successful logins, or logouts.

## Notifications and reminders

Notifications become read when opened and are retained indefinitely. Review
notifications link to the chore; approval/rejection occurs on the chore page.
Rejection reasons stay on the chore and are omitted from notifications.

```powershell
uv run --locked python manage.py send_reminders
```

Run this repeat-safe command hourly using Windows Task Scheduler: executable
`<project>\.venv\Scripts\python.exe`, arguments `manage.py send_reminders`, and
**Start in** set to the project directory. If using a separate database, set
`HOUSEHOLD_DB` for that scheduled process too.

Due reminders are once per date. Rejected-overdue reminders start immediately for
members, then daily; admins receive them after 24 hours, then daily until
resubmission. Admins can pause/resume reminders on each chore. Overdue pauses need
a reason, display the pausing admin, and never resume automatically.

A reminder command is a separate process: its notifications persist immediately,
but the in-memory channel layer cannot broadcast across processes. They appear on
the next page refresh/reconnection. Changes made in the serving process are live.

## REST API and Swagger

Swagger: http://127.0.0.1:8000/api/docs/ · OpenAPI: `/api/schema/`.
Swagger assets are installed locally. Operations include member/PIN management,
chore CRUD/actions, bulk recurrence/catch-up, schedule, dashboards/workload,
completion attempts/photos, history, and notifications/reminder controls.
Every operation documents request and response examples, including errors.
GET/DELETE have no request body; header/path/query examples describe the request.

**This is an unauthenticated local demo API.** `X-Demo-Actor` asserts a user ID;
it is not authentication. Anyone can impersonate any user, including admins.
Browser session permissions do not secure the API. Keep the server on localhost.
On a fresh demo database, the primary admin ID is 1; inspect member IDs with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/members/ -Headers @{'X-Demo-Actor'='1'}
Invoke-RestMethod http://127.0.0.1:8000/api/chores/ -Headers @{'X-Demo-Actor'='1'}
```

Send JSON for operations; completion photos use multipart form data. POST actions
without fields accept `{}`. API validation errors use an `errors` envelope. Raw
photo downloads use the same asserted actor header and return image bytes.

## Verification

```powershell
uv run --locked python manage.py check
uv run --locked python manage.py makemigrations --check --dry-run
uv run --locked python manage.py test
uv run --locked python manage.py spectacular --file schema.yaml --validate --fail-on-warn
```

Run the complete suite including desktop/mobile ASGI browser flows:

```powershell
uv run --locked playwright install chromium
$env:RUN_BROWSER_TESTS = '1'
uv run --locked python manage.py test --noinput
Remove-Item Env:RUN_BROWSER_TESTS
```

Browser tests use a separate `test-browser.sqlite3`, two isolated browser sessions,
and Chromium at 1280px and 390px. They cover login, assignment appearing live,
filters, completion, rejection/resubmission, approval, and workload. Screenshots
are written to `.artifacts/`. Without the flag, browser tests are explicitly skipped.
Tests use disposable data and do not alter the running household database.

## Storage and implementation

SQLite defaults to `db.sqlite3`; photos default to `media/completion_photos/`.
`HOUSEHOLD_DB` and `HOUSEHOLD_MEDIA` can select isolated local paths. Database and
uploads survive restarts and are excluded from Git. Photos are validated images
up to 5 MB and served through ownership-checked browser routes, not public media
URLs. API photo access has the unauthenticated demo boundary described above.

Shared rules live in `accounts.py`, `services.py`, `completion.py`, `recurrence.py`,
and `reminders.py`; HTML and API routes call the same functions. Protected
relationships retain attempts, photos, notifications, and audit records after
soft deletion. Recurrence uses the original scheduled date with database uniqueness
and processing markers to prevent duplicates after retries or undo/recompletion.

HTMX 2.0.4 is vendored with its upstream license under `chores/static/chores/vendor/`.
Responsive CSS uses a single card column below 640px, keyboard focus, and skip
navigation. Dependencies are managed by `pyproject.toml` and `uv.lock`:

```powershell
uv add package-name
uv export --locked --format requirements-txt --no-hashes --output-file requirements.txt
```

`requirements.txt` is a compatibility export, not the source of truth. See
[_docs/backlog.md](_docs/backlog.md) for task completion and verification results.

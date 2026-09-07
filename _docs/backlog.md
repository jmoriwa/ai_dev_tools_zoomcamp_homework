# Shared Household Chores Backlog

Build these 10 tasks in order. Each task includes the database changes, Django logic, pages, and tests needed for that feature. The detailed requirements remain in [plan.md](plan.md).

Original starting point: Django was installed, the `config` project existed, and the `chores` app was registered. All 10 tasks are now complete. Verification notes under tasks 1–9 describe checks at those milestones; task 10 records final delivery verification.

## 1. Establish the database and application foundation

- [x] Configure a custom user model and `AUTH_USER_MODEL` before running the initial database migrations. Include the household, role, PIN history, lockout, and session-related fields needed by the plan.
- [x] Model the single household, chores, recurring series, completion attempts, audit events, and notifications. Keep completion attempts and audit history after a chore is deleted.
- [x] Create the initial SQLite migrations and configure Django admin screens for internal management.
- [x] Set up a responsive shared Django template, navigation, static files, and local photo storage. Add HTMX for later partial-page updates.
- [x] Put business operations in shared Python functions so pages and the future API can use the same rules.

**Done when:** migrations run on an empty database, records survive a restart, Django checks pass, and the shared page renders on narrow and wide screens.

**Verification:** Initial migrations, Django checks, and 9 foundation tests pass. The seeded household was read successfully in a separate process. Responsive CSS is implemented; visual narrow/wide browser verification remains pending because the browser tool could not initialize.

## 2. Implement login and household member management

- [x] Build username/PIN login, logout, and member management pages. Admins create accounts; only the primary admin can promote members or demote secondary admins. Both admin roles otherwise have equal operational permissions.
- [x] Enforce case-sensitive usernames and exactly six PIN digits with no leading zero. Store PINs with Django password hashing and prevent reuse of the immediately previous PIN.
- [x] Support self-service PIN changes after checking the current PIN, and admin resets to a random valid PIN that does not expire. Both operations invalidate all of that user's sessions, including the current session.
- [x] Lock accounts after 10 failed attempts; allow only manual admin unlocking. Implement a sliding 24-hour inactivity timeout.
- [x] Record PIN changes, lockouts, and unlocks in audit history without recording PIN values, individual failed attempts, successful logins, or logouts.
- [x] Enforce role and ownership checks on the server, including direct requests to another member's resources.

**Done when:** automated tests cover PIN validation/history, role restrictions, case sensitivity, lockout/unlock, session expiry, and session invalidation; an admin can create a member who can log in.

**Verification:** 30 automated tests pass (9 foundation and 21 account tests), including admin creation/member login through pages, PIN validation/history, role and direct-request restrictions, lockout/unlock, CSRF, sliding expiry, and multi-session invalidation. Django checks pass and no migration changes are needed. Browser visual verification remains pending because the browser connection failed to initialize.

## 3. Build chore creation and assignment

- [x] Build admin list, create, detail, edit, duplicate, and delete pages with title search.
- [x] Support title, optional description, predefined category, low/medium/high priority, one assignee, date-only due date, and photo/approval requirements.
- [x] Require an edit note for changes to due date, priority, or assignee. Record the note in audit history and create the member notification containing it.
- [x] Duplicate chore details and recurrence settings, requiring a new assignee and due date. Preserve history on deletion, mark the chore deleted, and provide no restore action.
- [x] Add a member list/detail page limited to their own assigned chores. Members cannot edit, delete, reassign, reject, or claim chores.

**Done when:** an admin can create and assign a chore that only its assigned member can access; tests cover permissions, required edit notes, duplication, deletion, and audit events.

**Verification:** 34 tests pass, including assignment ownership, required edit notes, notifications, independent duplication, search, deletion, and preserved audit history.

## 4. Implement completion, approval, and history

- [x] Allow members to mark chores done with an optional note/photo; enforce photos when required. Allow admins to complete chores for members and record the acting admin.
- [x] Complete ordinary chores immediately; send approval-required chores to pending review. Admins approve or reject from the chore detail page.
- [x] Require a rejection reason on the chore, but omit it from notifications. Keep rejected chores pending until resubmission and retain every attempt's note/photo. Resubmission requires a new submission rather than automatically reusing attachments or notes.
- [x] Show `Submitted on time` while a timely submission awaits review and `Rejected — overdue` for rejection after the due date.
- [x] Allow member undo within 15 minutes of completion. After that window, allow admin reactivation only with an audit note.
- [x] Build personal completion history and full household history for admins. Record all completion, review, resubmission, undo, and reactivation events.

**Done when:** tests verify each transition, photo requirements, ownership, preserved attempts, submission timing, and the undo boundary; the complete approval flow works through the pages.

**Verification:** 40 tests pass, including completion/review page flow, photo validation and access control, rejection retention, on-time status, undo boundary, and audit history.

## 5. Add daily and weekly recurrence

- [x] Generate the next occurrence when a recurring chore completes, using the original schedule rather than the completion date.
- [x] When scheduled occurrences were missed, present the admin with a choice to create all missed occurrences or skip them and continue with the next scheduled date.
- [x] Allow bulk assignment only for recurring chores, creating an independent series for each selected member.
- [x] Show members a one-month schedule preview. Preserve an already-created next occurrence when completion is undone.
- [x] Prevent duplicate occurrences when a completion request is retried or a chore is undone and completed again.

**Done when:** tests cover daily/weekly schedules, late completion, both catch-up choices, bulk assignment, preview dates, and undo/recompletion.

**Decision before implementation:** define how member completion waits for the admin's missed-occurrence choice. Use final approval as the completion point for approval-required recurrence unless the plan is clarified otherwise.

**Implemented decision:** Completion finishes immediately (or at final approval), with an explicit pending admin catch-up choice. The next occurrence waits for that choice. Undo preserves generated occurrences; repeat processing cannot duplicate them.

**Verification:** 45 tests pass, including daily/weekly schedules, original-date anchoring, both catch-up choices, approval timing, bulk page flow, preview ownership, and undo/recompletion.

## 6. Finish the member and admin dashboards

- [x] Build member sections for Today, Upcoming, Overdue, and Pending approval, plus Today/Upcoming/Overdue counts. Move completed chores to history.
- [x] Add member category/priority filters and connect the recurring schedule preview.
- [x] Build the separate application admin dashboard with create/assign actions, overdue work, pending approvals, and the count of locked accounts. Link to member management for unlocking.
- [x] Show each member's active workload grouped by priority and allow sorting by workload without numeric priority weights.
- [x] Use HTMX where useful for filtering and actions, with clear validation, empty states, and responsive layouts.

**Done when:** browser tests cover login, creation/assignment, member viewing/completion, approval/rejection, filters, and workload display at desktop and mobile sizes.

**Verification:** 46 backend tests and 2 Chromium UI tests pass. Desktop (1280px) and mobile (390px) flows cover login, assignment, completion, rejection/resubmission, approval, filters, and workload. Screenshots are saved under .artifacts/.

## 7. Deliver notifications and scheduled reminders

- [x] Build an unread badge and notification center; opening a notification marks it read. Retain all notifications and link review notifications to the chore detail page.
- [x] Connect notifications for major edits and member completions, and add due-date reminders.
- [x] For rejected-overdue chores, remind the member immediately and daily until resubmission; remind admins after one day and daily thereafter until resubmission.
- [x] Add admin pause/resume actions per chore. Require a pause reason when overdue, show members who paused reminders, audit both actions, and keep reminders paused until manually resumed.
- [x] Provide a repeat-safe Django management command for reminders and document how to schedule it locally. Store delivery information so repeated runs do not duplicate reminders.

**Done when:** clock-controlled tests verify due dates, reminder timing, duplicate prevention, pause/resume, and stopping after resubmission; opening a notification updates its read state.

**Verification:** 50 backend tests pass, including clock-controlled due/rejected reminders, admin delay, duplicate suppression, pause/resume, resubmission stopping reminders, and notification ownership/read behavior.

## 8. Add live updates with Django Channels

- [x] Install/configure Channels, ASGI serving, WebSocket routes, and an in-memory channel layer for a single local server process.
- [x] Use authenticated sessions and authorized subscriptions so members receive only their own updates while admins receive household updates.
- [x] Publish updates after successful database changes for assignments, completions, status changes, approvals/rejections, and notifications.
- [x] Refresh affected dashboard sections and badges without a full-page reload; reconnect cleanly and refresh state after disconnection.

**Done when:** changes in an admin browser appear in the assigned member's browser, and tests verify that another member cannot subscribe to or receive those events.

**Verification:** 55 backend/WebSocket tests and 2 ASGI Chromium flows pass. Assignments appear without reload; foreign origins and unauthorized subscriptions are rejected. Session invalidation and post-commit publication are tested.

## 9. Expose and document the REST API

- [x] Add Django REST Framework endpoints for the planned household operations, reusing the business logic used by the pages.
- [x] Cover member management, chores/actions, recurring schedules, dashboards/workload, completion review, history, and notifications/reminder controls.
- [x] Add OpenAPI/Swagger documentation with request/response schemas and example request and response payloads for every endpoint, including validation errors where relevant.
- [x] Keep API authentication out of scope as specified. Explicitly document the unauthenticated local-demo boundary; do not describe API callers as protected by the browser's member permissions.

**Done when:** API tests exercise the main operations and invalid transitions, Swagger covers every endpoint, and documented examples match actual responses.

**Decision before implementation:** specify how local demo API calls identify the acting user for business rules and audit records without claiming that supplied identity is authenticated.

**Implemented decision:** X-Demo-Actor asserts the acting user ID without authenticating it. Swagger and README explicitly document impersonation and the localhost-only demo boundary.

**Verification:** 61 backend/API/WebSocket tests pass. Tests exercise all operation families and check schema/example coverage for every API operation; OpenAPI validation passes with no warnings.

## 10. Package and verify the end-to-end demo

- [x] Add a repeatable seed command with one household, a primary admin, secondary admin, several members, one-time and recurring chores, varied categories/priorities, overdue work, pending approval, and completed work.
- [x] Write README instructions for environment setup, dependency installation, migrations, seed data, local demo credentials, ASGI server startup, reminder scheduling, tests, and Swagger access.
- [x] Run the complete backend and browser test suites. Close gaps in assignment, recurrence, completion/review, undo, audit history, PINs, lockout, sessions, and reminders.
- [x] Verify a fresh local setup, database persistence after restart, photo handling, and the admin-to-member-to-admin flow in two browser sessions.

**Done when:** a new developer can follow the README to run and demonstrate the complete app locally, with all required tests passing.

**Final verification (2026-09-07):** Checked out the staged source into an isolated directory with no existing environment, database, or uploads. `uv sync --locked` installed dependencies into a new Python 3.13.2 environment. Fresh migrations and demo seeding succeeded; rerunning the seed created zero additional chores. Started and stopped the ASGI server twice and verified unchanged member, chore, and audit API data plus saved photo bytes across restart and reseeding. Login and Swagger pages served successfully. The reminder command delivered two reminders, then zero on its repeat run. All 82 tests passed with `RUN_BROWSER_TESTS=1`, including desktop/mobile flows in separate admin/member browser sessions, required photo upload, rejection/resubmission, approval, filtering, workload, and live assignment. Django checks, migration drift checks, and OpenAPI validation passed. Reminder scheduling remains a documented per-installation setup step, consistent with the local-development scope.

## Scope guardrails

Keep this to one household and local development with Django templates, HTMX, SQLite, DRF, and Channels. Do not add deployment, Docker, API authentication, multiple households, member removal/deactivation, primary-admin transfer, payments, chat, calendar integrations, gamification, external notification channels, or history export. Django's internal admin remains separate from the user-facing admin dashboard.

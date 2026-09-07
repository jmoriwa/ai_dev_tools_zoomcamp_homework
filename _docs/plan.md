# Shared Household Chores — Homework Plan

## Goal

Build a responsive household chore management web app focused on:

1. Assigning chores to household members.
2. Tracking what is due, completed, overdue, or awaiting approval.

The scope is intentionally limited to a single household and a Django-based local-development project.

---

## Core Product Scope

### Household

- One household only.
- No multi-household support.

### Roles

- One primary admin.
- Optional secondary admins.
- Primary and secondary admins have identical operational permissions.
- Only the primary admin can promote a member to admin.
- The primary admin can demote a secondary admin back to member.
- Primary-admin role transfer is out of scope for the MVP.

### Member permissions

Members can:

- View only their own assigned chores.
- Mark their chores as done.
- Add an optional completion note.
- Attach an optional completion photo.
- View their own completion history.
- Filter chores by category and priority.
- View one month of upcoming recurring chores.
- Undo a completion within 15 minutes.
- Change their own PIN after entering their current PIN.

Members cannot:

- Reassign chores.
- Reject chores.
- Edit or delete chores assigned to them.

### Admin permissions

Admins can:

- See all household chores.
- Create chores.
- Assign chores.
- Edit chores.
- Delete chores.
- Duplicate chores.
- Mark chores complete on behalf of a member.
- Search chores by title.
- Review overdue chores.
- Review pending approvals.
- View the full household history.
- Sort members by workload.
- Pause and resume reminders.
- Unlock locked member accounts.

---

## Chore Data

Each chore includes:

- Title.
- Optional description.
- Category.
- Priority.
- One assigned member.
- Due date.
- Optional recurrence.
- Optional completion-photo requirement.
- Optional admin-approval requirement.

### Categories

Use simple predefined categories such as:

- Kitchen
- Bathroom
- Laundry

### Priority

Priority values:

- Low
- Medium
- High

No numeric weighting is required.

For workload displays, show counts grouped by priority rather than calculating a score.

### Due dates

- Due date only.
- No due time.

---

## Chore Assignment

- A chore is assigned to one specific household member.
- Members do not claim unassigned chores.
- Members cannot reassign chores.

### Bulk assignment

- Bulk assignment is supported only for recurring chores.
- Bulk-assigning a recurring chore to several members creates an independent recurring series for each member.

---

## Editing and Deleting

Admins can edit and delete chores after assignment.

### Major edits

Changes to any of the following are treated as major edits:

- Due date
- Priority
- Assignment

For a major edit:

- The admin must enter an edit note.
- The member receives an in-app notification.
- The edit note is shown in that notification.
- The edit note is also stored in audit history.

### Deleting chores

- Deleting a chore does not delete its history.
- The chore is marked as deleted in history.
- Deleted chores cannot be restored.

---

## Duplicating Chores

Admins can duplicate an existing chore.

Duplication copies:

- Title
- Description
- Category
- Priority
- Recurrence settings
- Other chore details

Duplication does not copy:

- Assignee
- Due date

The admin chooses a new assignee and due date.

---

## Recurring Chores

Supported recurrence:

- Daily
- Weekly

### Recurrence behavior

When a recurring chore is completed:

- The next occurrence is created automatically.
- The next date follows the original schedule.
- It is not calculated relative to the completion date.

Example:

If a weekly chore is scheduled for every Monday and completed on Wednesday, the next occurrence is still the following Monday.

### Missed recurring occurrences

If an overdue recurring chore is eventually completed and scheduled occurrences were missed:

- Ask the admin whether to:
  - Create all missed occurrences, or
  - Skip missed occurrences and continue with the next scheduled occurrence.

### Future schedule

Members can see a simple preview of upcoming recurring chores:

- One month ahead.

### Undo and recurrence

If a recurring chore is marked done and then undone:

- Keep the next occurrence that was already created.
- Record the undo in audit history.

---

## Dashboard

### Member dashboard

Sections:

- Today
- Upcoming
- Overdue
- Pending approval

Completed chores do not stay on the main dashboard.

They move to a separate:

- History view

### Dashboard summary

Show counts for:

- Today
- Overdue
- Upcoming

### Admin dashboard

Use a dedicated admin dashboard.

Primary emphasis:

- Create chore
- Assign chore
- Review overdue chores
- Review pending approvals

Also show:

- Count of currently locked-out members.
- Small member workload overview.
- Ability to sort members by workload.

### Workload overview

For each member, show active chore counts grouped by:

- Low priority
- Medium priority
- High priority

No numeric workload score is required.

---

## Completion Flow

### Standard completion

Members can:

- Mark a chore done.
- Add an optional short note.
- Add an optional completion photo.

Admins can also mark a chore complete on behalf of a member.

If an admin does this:

- Record in audit history that the admin completed it.

---

## Completion Photos

- Members may attach an optional completion photo.
- Admins can configure specific chores to require a completion photo.

---

## Optional Admin Approval

Each chore can optionally require admin approval.

### If approval is not required

Marking the chore done completes it immediately.

### If approval is required

The member submits the chore for review.

The admin must:

- Open the chore before acting.
- Approve or reject it from the chore view.

Approval/rejection is not performed directly from the notification center.

### Pending approval

Chores awaiting review appear in:

- Pending approval

### Submitted on time

If a member submits a chore on or before the due date but the admin has not reviewed it yet:

- Use status: `Submitted on time`
- Do not treat it as overdue merely because approval is pending.

### Rejection

If the admin rejects a submission:

- A rejection reason is required.
- The reason is shown on the chore.
- The reason is not included in the member's notification.
- The chore remains pending until the member resubmits.

### Rejected after due date

If a submission is rejected after the due date:

- Use status: `Rejected — overdue`

### Rejected attempts

Rejected completion attempts remain in audit history.

Preserve:

- Submitted note
- Submitted photo

### Resubmission

When resubmitting:

- The member can see the previous attempt.
- The previous note/photo are not reused automatically.
- A new submission is required.

---

## Undo Completion

Members can undo `Mark done` for:

- 15 minutes after completion.

Every undo is recorded in audit history.

After the 15-minute window:

- The member cannot undo it.
- An admin can reactivate the chore.
- Reactivation requires an audit note.

---

## Reminders and Notifications

Notification channels:

- Dashboard notification badge.
- In-app notification center.

Not included:

- Email
- SMS
- Push notifications

### Read behavior

- Notifications automatically become read when opened.

### Retention

- Keep all notifications.

### Due-date reminder

Members receive an in-app reminder:

- On the chore's due date.

### Admin completion notification

The admin receives an in-app notification whenever:

- A member completes a chore.

### Edit notifications

Members are notified when the admin changes:

- Due date
- Priority
- Assignment

The required edit note appears directly in the notification.

### Rejected-overdue reminders

If a chore becomes `Rejected — overdue`:

Member:

- Receives an immediate reminder.
- Then receives a reminder daily until resubmission.

Admin:

- Receives the first reminder after 1 day if the chore is still not resubmitted.
- Then receives a reminder daily until resubmission.

### Pausing reminders

Admins can pause reminders for a specific chore.

Paused reminders:

- Stay paused until the admin manually resumes them.
- Do not automatically resume.

For overdue chores:

- A pause reason is required.

Members can see:

- That reminders are paused.
- Which admin paused them.

Audit history records:

- Reminder pause.
- Reminder resume.

---

## Authentication

### Account creation

- Admin creates member accounts.
- No invite-link flow.

### Login

All users, including admins, use:

- Username
- PIN

### Username rules

- Username is unique only within the household.
- Username comparison is case-sensitive.

Example:

- `Alex`
- `alex`

may be different users.

### PIN rules

PIN must:

- Be exactly 6 digits.
- Not begin with `0`.

### PIN storage

- Store PINs hashed using Django's password hashing system.
- Never store the raw PIN.

### PIN history

When a user changes their PIN:

- They cannot reuse their immediately previous PIN.

Audit history records:

- That the PIN changed.
- Never the PIN value itself.

### Admin PIN reset

Admins can reset a member's PIN.

Reset behavior:

- Generate a new random PIN.
- Reset PIN does not expire.
- Resetting the PIN force-logs the member out.

### Self-service PIN change

Members can change their own PIN after entering the current PIN.

After changing their PIN:

- End all of their active sessions.
- End the current session too.
- Require login again.

---

## Login Lockout

- Lock an account after 10 failed PIN attempts.
- Account remains locked until an admin manually unlocks it.

Admin dashboard:

- Shows a count of currently locked-out members.
- Does not list them directly on the dashboard.

Admins unlock users from:

- Member management page.

Audit history:

- Do not record every failed login.
- Record the event when failed attempts trigger an account lock.
- Record account unlocks.

Successful logins:

- Not audited.

Logout events:

- Not audited.

---

## Sessions

Users remain logged in between visits unless:

- They log out.
- Their session expires.
- Their PIN is reset or changed.

### Session expiry

Use:

- Sliding 24-hour inactivity timeout.

Each valid user activity resets the inactivity timer.

No warning is shown before session expiration.

---

## History and Audit Log

Keep a detailed history.

Members can see:

- Their own completion history.

Admins can see:

- Full household history.

Audit/history should include relevant events such as:

- Chore creation
- Chore edits
- Assignment changes
- Completion
- Admin completion on behalf of a member
- Rejection
- Resubmission
- Rejected completion attempts
- Completion notes
- Completion photos
- Undo completion
- Admin reactivation
- Deleted chores
- Required edit notes
- Reminder pause
- Reminder resume
- PIN changes without PIN values
- Account lockout
- Account unlock

---

## Search and Filtering

### Members

Members can filter their chores by:

- Category
- Priority

### Admins

Admins can:

- Search chores by title.
- Sort members by workload.

---

## Real-Time Updates

Changes should appear to users in real time.

Use:

- Django Channels
- WebSockets
- In-memory channel layer

Examples of real-time changes:

- New chore assignment
- Chore completion
- Chore status changes
- Approval/rejection updates
- Notifications

---

## REST API

Provide a REST API using:

- Django REST Framework

### API authentication

- API authentication is out of scope for this homework.

### Documentation

Use:

- OpenAPI / Swagger

Swagger documentation must include:

- All endpoints.
- Request schemas.
- Response schemas.
- Example request payloads for every endpoint.
- Example response payloads for every endpoint.

---

## Django Admin

Include configured Django admin screens.

Purpose:

- Internal management
- Debugging
- Development

Django admin superusers may bypass normal application business rules.

The user-facing admin dashboard remains a separate part of the app.

---

## Data Storage

Use:

- SQLite

Requirements:

- Persistent storage.
- Data survives server restarts.

Database migrations beyond the initial schema are not required as part of the homework requirements.

---

## Demo / Seed Data

Provide seed/demo data including:

- One household.
- Primary admin.
- Optional secondary admin.
- Several members.
- Example one-time chores.
- Example recurring chores.
- Different priorities.
- Different categories.
- At least one overdue chore.
- At least one approval-required chore.
- At least one completed chore.

---

## Testing

Include automated tests for:

### Backend

Core business logic such as:

- Assignment
- Recurrence
- Completion
- Approval/rejection
- Undo window
- Audit history
- PIN rules
- Lockout
- Session behavior
- Reminder behavior

### UI

Key user flows such as:

- Login
- Admin creates/assigns chore
- Member views chores
- Member completes chore
- Admin approves/rejects completion
- Chore filtering
- Admin workload view

---

## Technology Stack

### Backend

- Django
- Django REST Framework
- Django Channels

### Frontend

- Django templates
- HTMX

### Real-time

- WebSockets
- Django Channels
- In-memory channel layer

### Database

- SQLite

### Authentication

- Custom Django user model
- Username + hashed 6-digit PIN

---

## Application Type

Build:

- Responsive web app.

Do not build:

- Native mobile app.
- Desktop-only app.

---

## Development / Delivery Scope

Environment:

- Local development only.

Not required:

- Production deployment.
- Docker.
- Docker Compose.
- Cloud hosting.

---

## Explicitly Out of Scope

The following are explicitly excluded from the homework:

- Multiple households.
- Member removal/deactivation.
- Primary-admin role transfer.
- Payments.
- Chat/messaging.
- Calendar integrations.
- Gamification.
- Email notifications.
- SMS notifications.
- Push notifications.
- History export.
- CSV export.
- PDF export.
- Deployment.
- Docker/containerization.
- REST API authentication.

---

## Scope Summary

The homework should demonstrate a complete but bounded chore-management system.

The core experience is:

1. Admin creates household users.
2. Admin creates and assigns chores.
3. Members see only their assigned work.
4. Members complete chores and optionally provide notes/photos.
5. Some chores require admin approval.
6. Daily/weekly chores recur automatically.
7. Dashboards clearly show what is due, upcoming, overdue, or pending.
8. In-app notifications keep members and admins informed.
9. Audit history preserves meaningful changes and completion events.
10. Django, HTMX, DRF, Channels, SQLite, Swagger, seed data, and automated tests form the implementation baseline.

The product should prioritize chore assignment and completion tracking rather than expanding into general household management.

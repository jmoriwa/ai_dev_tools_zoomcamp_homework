# Mini Kanban Board — Homework Specification

## Goal

Build a simple, general-purpose Kanban board for tracking project tasks.

The app should be useful enough to demonstrate core CRUD, filtering, drag-and-drop, and basic collaboration concepts without becoming a full project-management platform.

---

## Board

The app has one Kanban board with four fixed columns:

- Backlog
- To Do
- In Progress
- Done

Each column shows the number of tasks currently inside it.

Users can move tasks between columns using drag-and-drop.

Task order inside each column is manual and controlled by drag-and-drop.

---

## Tasks

Users can:

- Create tasks
- Edit tasks
- Delete tasks
- Move tasks between columns
- Archive completed tasks

Each task contains:

- Title
- Description
- Priority
- Optional due date
- Optional assignee

Priority values:

- Low
- Medium
- High

Assignees come from a fixed demo list of names.

There are no user accounts or login system for this homework.

---

## Due Dates

Due dates are optional.

If a task is past its due date and is not in Done:

- Visually highlight it as overdue.

No reminder system is required.

---

## Assignees

Tasks can have one assignee.

Assignees are selected from a fixed demo list.

The app does not need:

- User registration
- Authentication
- Role management
- Assignee management screens

---

## Search and Filtering

Users can:

- Search tasks by title
- Filter tasks by assignee
- Filter tasks by priority

Search and filters should apply to the active board.

---

## Comments

Each task can have simple comments.

A comment contains:

- Comment text
- Commenter name selected from the fixed assignee list

Users can:

- Add comments
- Edit comments
- Delete comments

No comment history or audit log is required.

---

## Archive

Tasks in Done can be archived.

Archived tasks:

- Disappear from the main board
- Remain available in a separate Archive view

Archived tasks do not need advanced restore/history behavior unless convenient to implement.

---

## UI Expectations

The app should be a responsive web app.

Main screen:

- One board
- Four columns
- Task cards
- Drag-and-drop
- Search
- Filters

Task card should show, at minimum:

- Title
- Assignee
- Priority
- Due date, if present

Opening/editing a task should show:

- Description
- Assignee
- Priority
- Due date
- Comments

---

## Technical Scope

Recommended stack:

- Django
- Django templates
- HTMX where useful
- SQLite

Use JavaScript only where needed for drag-and-drop behavior.

Persistent storage is required.

---

## Testing

Include basic automated tests for the most important flows:

- Create task
- Edit task
- Delete task
- Move task between columns
- Filter by assignee
- Filter by priority
- Search by title
- Add/edit/delete comment
- Archive a Done task

Keep the tests focused on core behavior.

---

## Seed Data

Provide simple demo data so the app is easy to run and inspect.

Include:

- A few demo assignees
- Tasks across all four columns
- Different priorities
- At least one overdue task
- At least one task with comments
- At least one archived task

---

## Explicitly Out of Scope

Do not add:

- Multiple boards
- Custom columns
- User accounts
- Authentication
- Permissions or roles
- Multiple assignees per task
- Labels or tags
- Notifications
- Email
- Activity history
- Audit logs
- File attachments
- Subtasks
- Recurring tasks
- Dependencies
- Time tracking
- Analytics dashboards
- Calendar integrations
- Real-time multi-user collaboration
- Complex workflow rules
- Deployment requirements

---

## MVP Summary

The finished homework should let a user:

1. See one Kanban board with Backlog, To Do, In Progress, and Done.
2. Create, edit, and delete tasks.
3. Drag tasks between columns and reorder them.
4. Assign one person from a fixed demo list.
5. Set priority and an optional due date.
6. See overdue tasks clearly.
7. Search by title.
8. Filter by assignee and priority.
9. Add, edit, and delete simple comments.
10. Archive Done tasks and view them later.

This is the full scope. Anything beyond this should be treated as optional.

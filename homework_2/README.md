# Homework 2 - Littleboard

Interactive frontend for [spec1.md](spec1.md). The referenced `_docs/specs.md`
was not present, so `spec1.md` is the source of requirements.

## Run

Requires Node.js 22 or newer. No dependencies or installation required.

```powershell
cd homework_2/frontend
npm.cmd start
```

On macOS/Linux, use `npm start` and `npm test` instead.
Open http://localhost:3000. The Node server serves the frontend and proxies `/api/*` to FastAPI.
The [FastAPI backend](backend/README.md) runs separately with uv on port 8000.

## Features

- Four fixed columns with counts, task creation/editing/deletion, and descriptions.
- Drag cards onto another card to insert before it, or into column space to append.
- Use the task dialog's Status and Move up / Move down controls on touch devices
  or with a keyboard. Task titles are keyboard-focusable buttons.
- Optional assignee/due date, priorities, overdue indicators, title search, and combined filters.
- Add, edit, and delete comments using demo commenter names.
- Archive Done tasks and restore them from the Archive view.
- Responsive layout with seeded tasks, comments, assignees, and an archived task.

## Data boundary

All data access is centralized in `frontend/api.js` and uses HTTP requests to `/api`.
Start the backend in a second terminal using the commands in [backend/README.md](backend/README.md).
The frontend server forwards requests to `http://127.0.0.1:8000`; set `BACKEND_URL`
to use another HTTP backend address. Set `PORT` to change the frontend port.
Data is shared by all browsers connected to this backend and survives page refreshes.
The backend uses SQLAlchemy with persistent SQLite by default; set `DATABASE_URL`
to select another database. Restarting preserves tasks, comments, and ordering.
Existing localStorage demo data is not imported. API and connection errors appear in the UI.

## Backend contract

[openapi.yaml](openapi.yaml) defines the HTTP API derived from `frontend/api.js`.
The browser API base URL is `/api`, proxied to `http://127.0.0.1:8000/api`.

| Frontend method | HTTP endpoint |
| --- | --- |
| `list(filters)` | `GET /tasks` |
| `create(fields)` | `POST /tasks` |
| `update(id, fields)` | `PATCH /tasks/{taskId}` |
| `remove(id)` | `DELETE /tasks/{taskId}` |
| `move(id, status, beforeId)` | `POST /tasks/{taskId}/move` |
| `archive(id, archived)` | `PATCH /tasks/{taskId}/archive` |
| `saveComment(id, comment)` without comment ID | `POST /tasks/{taskId}/comments` |
| `saveComment(id, comment)` with comment ID | `PUT /tasks/{taskId}/comments/{commentId}` |
| `deleteComment(id, commentId)` | `DELETE /tasks/{taskId}/comments/{commentId}` |

For comment edits, put the comment ID in the path and send only `name` and
`text` in the body. Comment mutations return the complete updated task.
Task deletion returns JSON `true`, matching the mock.

The contract preserves camelCase fields, empty strings for unset assignees and
dates, manual ordering, and archive/restore behavior. HTTP validation makes
implicit UI constraints explicit: unknown body fields and null task fields are
rejected, dates must be real calendar dates, and omitted optional creation fields
default to empty strings. Validation errors use HTTP 422 with a `detail` array;
missing resources use 404 and state conflicts use 409 with a `detail` string.
The HTTP adapter turns these responses into user-facing errors.

The [FastAPI backend](backend/README.md) implements this contract with a
SQLAlchemy database connected to the frontend HTTP adapter.

## Verification

```powershell
cd homework_2/frontend
npm.cmd test
```

Node tests cover HTTP methods, paths, filters, request bodies, response handling, and errors.

Manual UI check: create and edit a task; move and reorder it; filter by title,
assignee and priority; add/edit/delete a comment; mark it Done, archive and
restore it; refresh to verify persistence; delete it. Check the layout at
desktop and phone widths and navigate the dialog with Tab/Escape.

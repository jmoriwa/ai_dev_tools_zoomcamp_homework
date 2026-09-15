# Homework 2

The second homework project will live in this folder, within the shared
AI Dev Tools Zoomcamp repository.

Add the project files here and update this README with setup, run, and
verification instructions as the homework is implemented.

## Backend contract

[openapi.yaml](openapi.yaml) defines the HTTP API derived from `frontend/api.js`.
The proposed API base URL is `http://localhost:8000/api`.

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
The future HTTP adapter should turn these responses into user-facing errors.

The frontend still uses localStorage. The contract targets a FastAPI backend
with an initial replaceable in-memory database; it does not add HTTP integration.

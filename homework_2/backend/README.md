# Littleboard FastAPI backend

Implements all nine operations in [openapi.yaml](../openapi.yaml).
Requires Python 3.11+ and uv. Run these commands from this directory:

```powershell
uv sync --locked
uv run uvicorn littleboard.main:app --reload --port 8000
```

- API: http://localhost:8000/api/tasks
- Interactive documentation: http://localhost:8000/docs
- Generated OpenAPI: http://localhost:8000/openapi.json

The frontend currently uses its own localStorage mock. This backend runs
independently; the frontend HTTP adapter has not been wired up.

## Tests

```powershell
uv run --locked pytest -q
```

Endpoint tests were written and run before implementation, initially failing
because the backend module did not exist. They cover CRUD, combined filters,
manual ordering, archive/restore, comment operations, invalid input, missing
resources, atomic failed writes, independent app instances, and contract checks.

## Mock database

Each app instance starts with ten demo tasks, including an overdue task, comments,
and an archived task. Changes last only for the life of the process. Use a single
worker: multiple workers would each have their own independent data.

`littleboard/repository.py` defines `TaskRepository`, the storage interface.
`MemoryRepository` protects operations with a lock and returns detached copies.
State checks happen before mutation while holding the lock, so rejected writes
do not change data.

To replace the mock, implement `TaskRepository` and pass the implementation to
`create_app(repository)`. Preserve atomic operations, manual ordering, detached
results, and the `NotFound`/`Conflict` exceptions. Routes and request validation
can stay the same. Tests inject an empty `MemoryRepository` to isolate each test.

Task IDs are opaque strings. Dates remain strings, with `""` representing no due
date. Null fields, unknown body fields, invalid calendar dates, and blank titles
or comments return 422. Missing resources return 404 and state conflicts 409.

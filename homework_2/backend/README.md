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

The frontend uses this API through its Node server proxy. Start the frontend with
`npm.cmd start` from `../frontend`, then open http://localhost:3000.

## Tests

```powershell
uv run --locked pytest -q
```

Endpoint tests were written and run before implementation, initially failing
because the backend module did not exist. They cover CRUD, combined filters,
manual ordering, archive/restore, comment operations, invalid input, missing
resources, atomic failed writes, isolated databases, and contract checks.

## Database

The backend uses SQLAlchemy with a persistent SQLite database at
`backend/littleboard.db` by default. Tables are created at startup and demo data
is seeded once per database. Restarting, or deleting all tasks, does not reset it.

Set `DATABASE_URL` to select another SQLAlchemy database and install its driver:

```powershell
# PostgreSQL example (requires a running database)
uv add "psycopg[binary]"
$env:DATABASE_URL = "postgresql+psycopg://user:password@localhost/littleboard"
uv run uvicorn littleboard.main:app --port 8000
```

Routes depend on `TaskRepository`; `SQLAlchemyRepository` stores tasks and
comments in separate tables with explicit ordering. Each operation uses its own
session and transaction, and returns detached values. A database-level board
row lock serializes writes, including validation and reorder operations across
workers. This favors correctness for a small board over high write throughput.
Task deletion cascades to comments through the ORM.

App-owned connections are disposed on shutdown. Tests inject repositories backed
by temporary SQLite files. They cover restart persistence, seed-once behavior,
rollback, comment cleanup, concurrent writers, and the full endpoint contract.
PostgreSQL and MySQL have optional integration coverage (see below). The SQL
uses SQLAlchemy types and expressions without vendor-specific queries. Startup
creates missing tables; future schema changes require migrations. Initialize a
new database before starting multiple workers to avoid concurrent schema creation.

Task IDs are opaque strings. Dates remain strings, with `""` representing no due
date. Null fields, unknown body fields, invalid calendar dates, and blank titles
or comments return 422. Missing resources return 404 and state conflicts 409.

## PostgreSQL and MySQL integration tests

The endpoint and persistence tests are parameterized over SQLite, PostgreSQL,
and MySQL. External engines are skipped unless their test URLs are configured;
a configured but unreachable server fails the suite. Each test creates and drops
its own uniquely named database, so the test account needs CREATE/DROP DATABASE
permissions. Use dedicated test servers.

From this directory, with Docker Desktop running:

```powershell
uv sync --locked --group integration
docker compose -p littleboard-integration -f compose.test.yaml up -d --wait
$env:TEST_POSTGRESQL_URL = "postgresql+psycopg://littleboard:integration-only@127.0.0.1:15432/postgres"
$env:TEST_MYSQL_URL = "mysql+pymysql://root:integration-only@127.0.0.1:53306/mysql?charset=utf8mb4"
uv run --locked --group integration pytest -q
# Remove the disposable test containers when finished.
docker compose -p littleboard-integration -f compose.test.yaml down -v
```

The Compose services run PostgreSQL 17 and MySQL 8.4 with temporary database
storage and ports bound to localhost. Tests cover the API contract, restart
persistence, seed-once behavior, rollback, cascading comment deletion, literal
Unicode search, and concurrent task/comment writes on each engine.

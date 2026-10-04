# TimeTrack Runbook

## 1. Purpose

This runbook covers how to set up, run, verify, and troubleshoot the TimeTrack application in a local development environment.

## 2. Project Summary

TimeTrack is a Python time-tracking application with:

- browser-based reporting and entry management
- FastAPI REST endpoints
- FastMCP AI integration
- shared SQLite persistence

## 3. Prerequisites

- Python 3.13+
- uv installed and available on PATH
- Git for source control
- optional: browser access to http://127.0.0.1:8000

## 4. Setup

From the project root:

```bash
uv sync
```

If dependencies are not already present:

```bash
uv add fastmcp fastapi "uvicorn[standard]"
```

## 5. Run the app

Start the API and web app with:

```bash
uv run uvicorn main:app --reload
```

If port 8000 is blocked on Windows, use:

```bash
uv run uvicorn main:app --reload --port 8001
```

Then open:

- http://127.0.0.1:8000 for the browser UI
- http://127.0.0.1:8000/mcp for the MCP endpoint

## 6. Verify the app

Run the regression suite:

```bash
uv run python -m unittest test_database_filters.py
```

Expected result: all tests pass.

## 7. Common endpoints

### Entries

- GET /api/entries
- POST /api/entries
- PUT /api/entries/{id}
- DELETE /api/entries/{id}

### Project data

- GET /api/projects
- GET /api/projects/{project}/summary
- GET /api/projects/{project}/budget
- PUT /api/projects/{project}/budget
- GET /api/projects/alerts

### Reports

- GET /api/reports/weekly/{employee_name}
- GET /api/reports/monthly

### CSV

- GET /api/entries/export
- POST /api/entries/import

## 8. Database behavior

The app uses a SQLite database stored in the project directory as `timetrack.db` by default.

This can be overridden with:

```bash
TIMETRACK_DB_PATH=/path/to/custom.db
```

The database is initialized automatically when the app starts via `db.init_db()`.

## 9. Troubleshooting

### 9.1 Port conflicts

If uvicorn fails because 8000 is in use:

- stop the other application, or
- run on a different port, such as 8001

### 9.2 Empty or stale database state

Delete the database file and restart the app if you want a clean local state:

```bash
rm timetrack.db
```

On Windows PowerShell:

```powershell
Remove-Item .\timetrack.db
```

### 9.3 Import or validation errors

Common causes:

- missing employee name or project name
- hours value is 0 or negative
- malformed CSV headers
- invalid date format

### 9.4 MCP route not loading

Confirm that the app is running and that the mounted route is available at:

```text
http://127.0.0.1:8000/mcp
```

## 10. Typical local workflow

1. Start the app
2. Create entries in the browser or via MCP tools
3. Validate totals and budgets in the UI
4. Run the test suite before sharing changes

## 11. Operational notes

- database logic is centralized in [database.py](database.py)
- API and MCP entry points are centralized in [main.py](main.py)
- browser UI logic is centralized in [static/app.js](static/app.js)

This repo is intended to be a lightweight internal MVP rather than a production multi-user system.

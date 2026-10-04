# TimeTrack Technical Documentation

## 1. Overview

TimeTrack is a Python-based time-tracking application that supports two front doors into the same SQLite database:

- A browser-based web UI served from the `static/` folder
- An MCP server exposed through FastMCP for AI assistants and tools

The key design goal is to keep all state in a single shared database so that actions taken via the web interface and AI tools remain consistent.

This project is intentionally practical and product-oriented rather than purely academic. It combines:

- a FastAPI application
- a shared SQLite persistence layer
- a static HTML/JS/CSS frontend
- MCP tool/resource/prompt interfaces for AI interactions
- regression tests covering core product behaviors

## 2. System Architecture

### 2.1 High-level components

The application is split into three main layers:

1. Persistence layer — `database.py`
   - Creates and manages the SQLite database
   - Executes all insert, update, delete, and aggregation queries
   - Handles CSV import/export
   - Manages project budget data

2. API + MCP layer — `main.py`
   - Creates the FastAPI app
   - Mounts the MCP HTTP endpoint at `/mcp`
   - Exposes REST endpoints for browser interactions
   - Exposes MCP tools and resources for AI clients

3. Frontend layer — `static/`
   - `index.html` defines tabs and UI structure
   - `app.js` handles fetch calls, rendering, and interactions
   - `style.css` styles the application

### 2.2 Runtime data flow

The runtime flow is intentionally simple:

- The browser makes REST requests to `/api/...`
- The API layer delegates to `database.py`
- The database layer writes to `timetrack.db`
- MCP tools call the same database functions directly
- UI state is refreshed after create/update/delete actions

This makes the application behave like a single source of truth for time-entry data.

## 3. Project Structure

```text
.
├── database.py              # SQLite access layer and business logic
├── main.py                  # FastAPI + FastMCP application entrypoint
├── static/
│   ├── index.html           # Browser UI layout
│   ├── app.js               # Browser behavior and API client logic
│   └── style.css            # UI styling
├── test_database_filters.py  # Regression tests for app behavior
├── pyproject.toml           # Python package and dependency config
├── README.md                # Setup and basic usage notes
├── TECHNICAL.md             # This technical document
├── timetrack.db             # SQLite database file
└── uv.lock                  # Resolved dependency lockfile
```

## 4. Technology Stack

### Backend

- Python 3.13+
- FastAPI
- FastMCP
- SQLite
- Uvicorn

### Frontend

- Plain HTML
- CSS
- vanilla JavaScript

### Dev/test tooling

- `unittest`
- `uv` for dependency and environment management

## 5. Database Design

The application uses a single SQLite database with one main table and one supporting budget table.

### 5.1 `time_entries`

Table schema:

```sql
CREATE TABLE IF NOT EXISTS time_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name TEXT NOT NULL,
    project TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    hours REAL NOT NULL,
    description TEXT NOT NULL DEFAULT ''
)
```

Purpose:

- stores each logged time record
- maps employees to projects and dates
- supports aggregation by employee, project, range, or month

### 5.2 `project_budgets`

```sql
CREATE TABLE IF NOT EXISTS project_budgets (
    project TEXT PRIMARY KEY,
    budget_hours REAL NOT NULL DEFAULT 0
)
```

Purpose:

- stores a project budget in hours
- is used to compare actual logged work against planned capacity
- powers project health and over-budget detection

### 5.3 Seed data

`init_db()` inserts seed entries only if the table is empty. This makes local development easy while keeping the database ready for testing and demos.

## 6. Persistence Layer (`database.py`)

The persistence layer contains the real business logic and is used by both the browser API and the MCP server.

### Core functions

- `get_connection()`
  - creates a `sqlite3` connection with `row_factory = sqlite3.Row`

- `init_db()`
  - creates tables if missing
  - seeds demo data when empty

- `list_all_entries(...)`
  - returns entries filtered by employee, project, start date, and/or end date

- `log_time(...)`
  - inserts one time entry
  - validates positivity of hours

- `update_entry(...)`
  - updates an existing entry by id

- `delete_entry(entry_id)`
  - removes an entry

- `get_timesheet(...)`
  - returns entries for one employee, optionally restricted by date range

- `list_projects()`
  - returns distinct projects with logged entries

- `get_project_summary(project)`
  - computes total hours and per-employee totals for a project

- `set_project_budget(project, budget_hours)`
  - stores project budget hours

- `get_project_budget(project)`
  - retrieves the configured budget for a project

- `get_weekly_summary(employee_name, week_start)`
  - aggregates total hours by project for a weekly report

- `get_monthly_dashboard_summary(month)`
  - returns totals by employee and by project for a month in `YYYY-MM` format

- `export_entries_csv(entries=None)`
  - exports rows as CSV text

- `import_entries_csv(csv_text)`
  - imports rows from CSV and logs them into the database

- `get_project_budget_alerts()`
  - computes status for all projects: `on track`, `near limit`, or `over budget`

## 7. API Layer (`main.py`)

`main.py` builds both FastMCP and FastAPI and then mounts them in the same app.

### 7.1 MCP tools

The following MCP tools are exposed:

- `log_time(employee_name, project, entry_date, hours, description)`
- `get_timesheet(employee_name, start_date, end_date)`
- `get_project_summary(project)`
- `get_weekly_summary(employee_name, week_start)`
- `get_monthly_dashboard_summary(month)`
- `list_projects()`

There are also:

- `timesheet://projects` as a resource
- `generate_weekly_report(...)` as a prompt

### 7.2 REST endpoints

The browser uses the following API routes:

- `GET /api/entries`
  - lists entries with optional filters

- `POST /api/entries`
  - creates a new entry

- `GET /api/entries/export`
  - exports all entries to CSV

- `POST /api/entries/import`
  - imports CSV content

- `PUT /api/entries/{entry_id}`
  - updates an entry

- `DELETE /api/entries/{entry_id}`
  - deletes an entry

- `GET /api/projects`
  - lists all project names

- `GET /api/projects/{project}/summary`
  - returns total hours, employee breakdown, budget, and remaining hours

- `GET /api/projects/{project}/budget`
  - returns the project budget

- `PUT /api/projects/{project}/budget`
  - sets the project budget

- `GET /api/projects/alerts`
  - returns health status for each project

- `GET /api/reports/weekly/{employee_name}`
  - returns a weekly summary for one employee

- `GET /api/reports/monthly`
  - returns month-level totals grouped by employee/project

- `GET /api/timesheet/{employee_name}`
  - returns time entries for one employee

### 7.3 Static asset routes

- `/` serves the app shell from `static/index.html`
- `/static` serves static resources from the `static/` directory
- `/mcp` hosts the MCP server route

## 8. Frontend Design (`static/`)

The frontend is intentionally lightweight and browser-native.

### Main UI views

- All Entries
  - filters by employee, project, date range
  - includes edit and delete actions
  - export/import controls

- Project Summary
  - show total hours by project
  - show employee breakdown
  - show budget and remaining hours
  - show project health status

- Weekly Report
  - employee-focused time aggregation

- Monthly Dashboard
  - total hours by month
  - breakdown by employee and project

- Log Time
  - form for creating a new time entry

### Frontend logic

The client-side behavior is implemented in `static/app.js`.

It performs:

- tab switching
- fetch requests to the REST API
- table rendering
- edit and delete action handlers
- toast notifications
- CSV export/import UI flow

## 9. Data Contracts

### Example project summary response

```json
{
  "project": "Website Redesign",
  "total_hours": 21.5,
  "by_employee": {
    "Asha Patel": 13.5,
    "Rahul Mehta": 8.0
  },
  "budget_hours": 30.0,
  "remaining_hours": 8.5,
  "budget_status": "on track",
  "is_over_budget": false
}
```

### Example monthly dashboard summary response

```json
{
  "month": "2026-10",
  "total_hours": 12.0,
  "by_employee": {
    "Lena Ortiz": 9.0,
    "Nina Shah": 3.0
  },
  "by_project": {
    "Website Redesign": 9.0,
    "Client Onboarding": 3.0
  }
}
```

## 10. Testing Strategy

The project uses a focused regression suite in `test_database_filters.py`.

The tests cover:

- filter behavior on `list_all_entries`
- update and delete flows
- weekly summary generation
- CSV export/import support
- project budgets
- month-level dashboard aggregation
- project alert status behavior

The tests invalidate the SQLite DB between runs to keep the environment isolated and prevent seeded data from leaking across tests.

## 11. Operational Notes

### 11.1 Database location

The database path resolves to a file next to the project root by default:

```python
DB_PATH = Path(__file__).resolve().parent / "timetrack.db"
```

It can be overridden using the `TIMETRACK_DB_PATH` environment variable.

### 11.2 Startup

The app is typically started with:

```bash
uv run uvicorn main:app --reload
```

Then the browser is opened at:

- `http://127.0.0.1:8000`

The MCP endpoint is exposed at:

- `http://127.0.0.1:8000/mcp`

### 11.3 Windows note

In local Windows testing, port 8000 may be unavailable due to socket conflicts, so the app can be started on an alternate port such as 8001:

```bash
uv run uvicorn main:app --reload --port 8001
```

## 12. Design Strengths

- Shared database architecture keeps browser and AI workflows consistent
- Simple SQLite persistence avoids operational complexity
- API and MCP layers share the same business logic
- UI and AI both access the same data model
- Regression tests validate the actual product behavior

## 13. Known Limitations / Enhancement Opportunities

- No authentication or user management yet
- No role-based permissions
- No charting library or richer analytics visualization
- No scheduled reports or email notifications
- No production deployment config beyond local dev usage
- No advanced validation for duplicate entries or inconsistent date formats

## 14. Summary

TimeTrack is a compact but complete MVP for time entry management that demonstrates a strong integration pattern:

- browser UI for humans
- MCP tool layer for AI assistants
- same SQLite data layer for both

This design is useful for internal productivity apps, AI-enabled operations tooling, and low-friction team reporting systems.

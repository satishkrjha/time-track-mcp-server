"""
TimeTrack -- one running application, two front doors onto the same
SQLite database of logged time entries:

  1. A real website (served from ./static) -- for people, in a browser
  2. An MCP server, mounted at /mcp -- for AI assistants, over HTTP

Both talk to the exact same database.py functions.

Setup:
    uv init .
    uv add fastmcp fastapi "uvicorn[standard]"
    uv run uvicorn main:app --reload

Then visit http://127.0.0.1:8000 for the website,
and http://127.0.0.1:8000/mcp is the MCP endpoint (Streamable HTTP).
"""
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastmcp import FastMCP

import database as db

# ---------- persistence, initialized once at startup ----------
db.init_db()

# ---------- Step 1: build the MCP server FIRST ----------
# Hand-curated tools, calling the SAME database functions the REST API
# below uses -- nothing duplicated between the two front doors.
mcp = FastMCP("TimeTrack")


@mcp.tool
def log_time(employee_name: str, project: str, entry_date: str, hours: float, description: str = "") -> dict:
    """Log a time entry. entry_date must be YYYY-MM-DD. Shows up on the website immediately."""
    return db.log_time(employee_name, project, entry_date, hours, description)


@mcp.tool
def get_timesheet(employee_name: str, start_date: str = "", end_date: str = "") -> list[dict]:
    """Get one employee's logged entries, optionally filtered to a date range (YYYY-MM-DD)."""
    return db.get_timesheet(employee_name, start_date or None, end_date or None)


@mcp.tool
def get_project_summary(project: str) -> dict:
    """Get total hours logged against a project, broken down by employee."""
    return db.get_project_summary(project)


@mcp.tool
def get_weekly_summary(employee_name: str, week_start: str) -> dict:
    """Get one employee's total hours grouped by project for a given week."""
    return db.get_weekly_summary(employee_name, week_start)


@mcp.tool
def get_monthly_dashboard_summary(month: str) -> dict:
    """Get totals by employee and project for a given month in YYYY-MM format."""
    return db.get_monthly_dashboard_summary(month)


@mcp.tool
def list_projects() -> list[str]:
    """List every project that has at least one logged time entry."""
    return db.list_projects()


@mcp.resource("timesheet://projects")
def known_projects() -> list[str]:
    """The current set of projects with logged time, for consistent naming."""
    return db.list_projects()


@mcp.prompt
def generate_weekly_report(employee_name: str, week_start: str) -> str:
    """Guides the AI to build a structured weekly hours report from this server's own tools."""
    return f"""Build a weekly report for {employee_name}, starting {week_start}.

1. Call get_timesheet with employee_name='{employee_name}', start_date='{week_start}'
2. Group the results by project
3. Present it as:
   {{employee_name}} -- Week of {week_start}
   [Project]: {{total hours for that project}}h
   Total: {{sum of all hours}}h

If no entries are found for that week, say so plainly instead of inventing data.
"""


# path="/" here, NOT "/mcp" -- app.mount() below adds that prefix.
# Setting both would double up into /mcp/mcp -- a real, easy-to-miss bug,
# verified against FastMCP's own documentation.

mcp_app = mcp.http_app(path="/")


# ---------- Step 2: build the FastAPI app, lifespan wired in AT CONSTRUCTION ----------
app = FastAPI(title="TimeTrack", lifespan=mcp_app.lifespan)


class NewEntry(BaseModel):
    employee_name: str
    project: str
    entry_date: str
    hours: float
    description: str = ""


class UpdateEntry(BaseModel):
    employee_name: Optional[str] = None
    project: Optional[str] = None
    entry_date: Optional[str] = None
    hours: Optional[float] = None
    description: Optional[str] = None


class CsvImportRequest(BaseModel):
    csv: str


@app.get("/api/entries")
def api_list_entries(
    employee_name: str | None = None,
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return db.list_all_entries(employee_name, project, start_date, end_date)


@app.post("/api/entries")
def api_log_entry(entry: NewEntry):
    return db.log_time(entry.employee_name, entry.project, entry.entry_date, entry.hours, entry.description)


@app.get("/api/entries/export")
def api_export_entries():
    return db.export_entries_csv()


@app.post("/api/entries/import")
def api_import_entries(payload: CsvImportRequest):
    return {"imported": db.import_entries_csv(payload.csv)}


@app.put("/api/entries/{entry_id}")
def api_update_entry(entry_id: int, entry: UpdateEntry):
    return db.update_entry(
        entry_id,
        employee_name=entry.employee_name,
        project=entry.project,
        entry_date=entry.entry_date,
        hours=entry.hours,
        description=entry.description,
    )


@app.delete("/api/entries/{entry_id}")
def api_delete_entry(entry_id: int):
    deleted = db.delete_entry(entry_id)
    return {"deleted": deleted, "id": entry_id}


@app.get("/api/projects")
def api_list_projects():
    return db.list_projects()


@app.get("/api/projects/{project}/summary")
def api_project_summary(project: str):
    summary = db.get_project_summary(project)
    budget = db.get_project_budget(project)
    remaining_hours = budget["budget_hours"] - summary["total_hours"]
    if remaining_hours < 0:
        budget_status = "over budget"
    elif remaining_hours <= 10:
        budget_status = "near limit"
    else:
        budget_status = "on track"

    summary["budget_hours"] = budget["budget_hours"]
    summary["remaining_hours"] = remaining_hours
    summary["budget_status"] = budget_status
    summary["is_over_budget"] = remaining_hours < 0
    return summary


@app.get("/api/projects/{project}/budget")
def api_project_budget(project: str):
    return db.get_project_budget(project)


@app.get("/api/projects/alerts")
def api_project_budget_alerts():
    return db.get_project_budget_alerts()


@app.put("/api/projects/{project}/budget")
def api_set_project_budget(project: str, budget_hours: float):
    return db.set_project_budget(project, budget_hours)


@app.get("/api/reports/weekly/{employee_name}")
def api_weekly_report(employee_name: str, week_start: str):
    return db.get_weekly_summary(employee_name, week_start)


@app.get("/api/reports/monthly")
def api_monthly_dashboard(month: str):
    return db.get_monthly_dashboard_summary(month)


@app.get("/api/timesheet/{employee_name}")
def api_get_timesheet(employee_name: str, start_date: str = None, end_date: str = None):
    return db.get_timesheet(employee_name, start_date, end_date)


@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/mcp", mcp_app)

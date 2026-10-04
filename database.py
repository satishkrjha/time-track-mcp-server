"""
TimeTrack's persistence layer -- SQLite, shared by the website and the MCP
server, exactly like RecipeBox's was. One real, professional use case this
time: logging billable hours against projects, and summarizing them.
"""
# import sqlite3
# from pathlib import Path

# DB_PATH = Path(__file__).parent / "timetrack.db"

import csv
import io
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(
    os.environ.get(
        "TIMETRACK_DB_PATH",
        str(Path(__file__).resolve().parent / "timetrack.db")
    )
).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            project TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            hours REAL NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_budgets (
            project TEXT PRIMARY KEY,
            budget_hours REAL NOT NULL DEFAULT 0
        )
    """)
    count = conn.execute("SELECT COUNT(*) FROM time_entries").fetchone()[0]
    if count == 0:
        seed = [
            ("Asha Patel", "Website Redesign", "2026-09-08", 6.5, "Homepage layout"),
            ("Asha Patel", "Website Redesign", "2026-09-09", 7.0, "Mobile responsive fixes"),
            ("Asha Patel", "Client Onboarding", "2026-09-10", 3.0, "Kickoff call + notes"),
            ("Rahul Mehta", "Website Redesign", "2026-09-08", 5.5, "API integration"),
            ("Rahul Mehta", "Internal Tools", "2026-09-09", 8.0, "Dashboard bug fixes"),
        ]
        conn.executemany(
            "INSERT INTO time_entries (employee_name, project, entry_date, hours, description) "
            "VALUES (?, ?, ?, ?, ?)",
            seed,
        )
        conn.commit()
    conn.close()


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "employee_name": row["employee_name"],
        "project": row["project"],
        "entry_date": row["entry_date"],
        "hours": row["hours"],
        "description": row["description"],
    }


def list_all_entries(
    employee_name: str | None = None,
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    filters: list[str] = []
    params: list[str] = []

    if employee_name:
        filters.append("employee_name = ?")
        params.append(employee_name)
    if project:
        filters.append("project = ?")
        params.append(project)
    if start_date:
        filters.append("entry_date >= ?")
        params.append(start_date)
    if end_date:
        filters.append("entry_date <= ?")
        params.append(end_date)

    query = "SELECT * FROM time_entries"
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY entry_date DESC, id DESC"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def log_time(employee_name: str, project: str, entry_date: str, hours: float, description: str = "") -> dict:
    if hours <= 0:
        raise ValueError("hours must be a positive number")
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO time_entries (employee_name, project, entry_date, hours, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (employee_name, project, entry_date, hours, description),
    )
    conn.commit()
    new_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM time_entries WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def update_entry(
    entry_id: int,
    employee_name: str | None = None,
    project: str | None = None,
    entry_date: str | None = None,
    hours: float | None = None,
    description: str | None = None,
) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"Entry {entry_id} not found")

    updated = {
        "employee_name": employee_name if employee_name is not None else row["employee_name"],
        "project": project if project is not None else row["project"],
        "entry_date": entry_date if entry_date is not None else row["entry_date"],
        "hours": hours if hours is not None else row["hours"],
        "description": description if description is not None else row["description"],
    }

    if updated["hours"] <= 0:
        conn.close()
        raise ValueError("hours must be a positive number")

    conn.execute(
        "UPDATE time_entries SET employee_name = ?, project = ?, entry_date = ?, hours = ?, description = ? WHERE id = ?",
        (
            updated["employee_name"],
            updated["project"],
            updated["entry_date"],
            updated["hours"],
            updated["description"],
            entry_id,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def delete_entry(entry_id: int) -> bool:
    conn = get_connection()
    cursor = conn.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_timesheet(employee_name: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM time_entries WHERE employee_name = ?"
    params: list = [employee_name]
    if start_date:
        query += " AND entry_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND entry_date <= ?"
        params.append(end_date)
    query += " ORDER BY entry_date"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def execute_query(query: str, params: list = []) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def list_projects() -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT project FROM time_entries ORDER BY project").fetchall()
    conn.close()
    return [r["project"] for r in rows]


def get_project_summary(project: str) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT employee_name, SUM(hours) as total_hours FROM time_entries "
        "WHERE project = ? GROUP BY employee_name ORDER BY employee_name",
        (project,),
    ).fetchall()
    conn.close()
    if not rows:
        raise ValueError(f"No time logged against project '{project}'")
    by_employee = {r["employee_name"]: r["total_hours"] for r in rows}
    return {
        "project": project,
        "total_hours": sum(by_employee.values()),
        "by_employee": by_employee,
    }


def set_project_budget(project: str, budget_hours: float) -> dict:
    if budget_hours < 0:
        raise ValueError("budget_hours must be a non-negative number")
    conn = get_connection()
    conn.execute(
        "INSERT INTO project_budgets (project, budget_hours) VALUES (?, ?) "
        "ON CONFLICT(project) DO UPDATE SET budget_hours = excluded.budget_hours",
        (project, budget_hours),
    )
    conn.commit()
    row = conn.execute("SELECT project, budget_hours FROM project_budgets WHERE project = ?", (project,)).fetchone()
    conn.close()
    return {"project": row["project"], "budget_hours": row["budget_hours"]}


def get_project_budget(project: str) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT project, budget_hours FROM project_budgets WHERE project = ?", (project,)).fetchone()
    conn.close()
    if row is None:
        return {"project": project, "budget_hours": 0.0}
    return {"project": row["project"], "budget_hours": row["budget_hours"]}


def get_project_budget_alerts() -> list[dict]:
    alerts: list[dict] = []
    for project in list_projects():
        summary = get_project_summary(project)
        budget = get_project_budget(project)
        remaining_hours = budget["budget_hours"] - summary["total_hours"]
        if remaining_hours < 0:
            budget_status = "over budget"
        elif remaining_hours <= 10:
            budget_status = "near limit"
        else:
            budget_status = "on track"

        alerts.append({
            "project": project,
            "total_hours": summary["total_hours"],
            "budget_hours": budget["budget_hours"],
            "remaining_hours": remaining_hours,
            "budget_status": budget_status,
            "is_over_budget": remaining_hours < 0,
        })

    return sorted(alerts, key=lambda item: (0 if item["is_over_budget"] else 1, item["remaining_hours"]))


def export_entries_csv(entries: list[dict] | None = None) -> str:
    rows = entries if entries is not None else list_all_entries()
    output = io.StringIO()
    fieldnames = ["id", "employee_name", "project", "entry_date", "hours", "description"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return output.getvalue()


def import_entries_csv(csv_text: str) -> list[dict]:
    if not csv_text or not csv_text.strip():
        return []

    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CSV file is missing headers")

    required = {"employee_name", "project", "entry_date", "hours", "description"}
    missing = sorted(required - set(reader.fieldnames))
    if missing:
        raise ValueError(f"CSV file is missing required columns: {', '.join(missing)}")

    inserted: list[dict] = []
    for row in reader:
        if not row or all((value or "").strip() == "" for value in row.values()):
            continue
        entry = log_time(
            employee_name=row["employee_name"].strip(),
            project=row["project"].strip(),
            entry_date=row["entry_date"].strip(),
            hours=float(row["hours"]),
            description=row.get("description", "") or "",
        )
        inserted.append(entry)
    return inserted


def get_weekly_summary(employee_name: str, week_start: str) -> dict:
    import datetime as dt

    start_date = dt.date.fromisoformat(week_start)
    end_date = start_date + dt.timedelta(days=6)

    conn = get_connection()
    rows = conn.execute(
        "SELECT project, SUM(hours) as total_hours FROM time_entries "
        "WHERE employee_name = ? AND entry_date >= ? AND entry_date <= ? "
        "GROUP BY project ORDER BY project",
        (employee_name, start_date.isoformat(), end_date.isoformat()),
    ).fetchall()
    conn.close()

    by_project = {r["project"]: r["total_hours"] for r in rows}
    total_hours = sum(by_project.values())

    return {
        "employee_name": employee_name,
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "total_hours": total_hours,
        "by_project": by_project,
    }


def get_monthly_dashboard_summary(month: str) -> dict:
    year, month_number = month.split("-")
    start_date = f"{year}-{month_number}-01"
    if month_number == "12":
        next_month = f"{int(year) + 1}-01-01"
    else:
        next_month = f"{year}-{int(month_number) + 1:02d}-01"

    conn = get_connection()
    by_employee_rows = conn.execute(
        "SELECT employee_name, SUM(hours) as total_hours FROM time_entries "
        "WHERE entry_date >= ? AND entry_date < ? GROUP BY employee_name ORDER BY employee_name",
        (start_date, next_month),
    ).fetchall()
    by_project_rows = conn.execute(
        "SELECT project, SUM(hours) as total_hours FROM time_entries "
        "WHERE entry_date >= ? AND entry_date < ? GROUP BY project ORDER BY project",
        (start_date, next_month),
    ).fetchall()
    total_hours_row = conn.execute(
        "SELECT COALESCE(SUM(hours), 0) as total_hours FROM time_entries WHERE entry_date >= ? AND entry_date < ?",
        (start_date, next_month),
    ).fetchone()
    conn.close()

    return {
        "month": month,
        "total_hours": total_hours_row["total_hours"],
        "by_employee": {row["employee_name"]: row["total_hours"] for row in by_employee_rows},
        "by_project": {row["project"]: row["total_hours"] for row in by_project_rows},
    }

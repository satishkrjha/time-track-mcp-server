import unittest

from fastapi.testclient import TestClient

import database
from main import app


class ListEntriesFiltersTests(unittest.TestCase):
    def setUp(self):
        if database.DB_PATH.exists():
            database.DB_PATH.unlink()
        database.init_db()

    def test_list_all_entries_supports_filters(self):
        results = database.list_all_entries(
            employee_name="Asha Patel",
            project="Website Redesign",
            start_date="2026-09-09",
            end_date="2026-09-09",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["employee_name"], "Asha Patel")
        self.assertEqual(results[0]["project"], "Website Redesign")
        self.assertEqual(results[0]["entry_date"], "2026-09-09")

    def test_update_entry_and_delete_entry(self):
        created = database.log_time("Sam Lee", "QA Review", "2026-09-20", 2.5, "Test case triage")
        updated = database.update_entry(
            created["id"],
            employee_name="Sam Lee",
            project="QA Review",
            entry_date="2026-09-21",
            hours=3.5,
            description="Updated triage",
        )
        self.assertEqual(updated["entry_date"], "2026-09-21")
        self.assertEqual(updated["hours"], 3.5)
        self.assertEqual(updated["description"], "Updated triage")

        deleted = database.delete_entry(created["id"])
        self.assertTrue(deleted)
        self.assertEqual(database.list_all_entries(employee_name="Sam Lee", project="QA Review"), [])

    def test_get_weekly_summary_groups_hours_by_project(self):
        database.log_time("Nina Shah", "Website Redesign", "2026-09-08", 4.0, "Wireframes")
        database.log_time("Nina Shah", "Website Redesign", "2026-09-09", 3.5, "Build")
        database.log_time("Nina Shah", "Client Onboarding", "2026-09-10", 2.0, "Kickoff")

        summary = database.get_weekly_summary("Nina Shah", "2026-09-08")
        self.assertEqual(summary["total_hours"], 9.5)
        self.assertEqual(summary["by_project"]["Website Redesign"], 7.5)
        self.assertEqual(summary["by_project"]["Client Onboarding"], 2.0)

    def test_csv_export_and_project_budget_support(self):
        database.log_time("Dana Kim", "Client Onboarding", "2026-09-12", 3.0, "Kickoff")
        csv_output = database.export_entries_csv()
        self.assertIn("employee_name,project,entry_date,hours,description", csv_output)
        self.assertIn("Dana Kim", csv_output)

        imported = database.import_entries_csv(
            "employee_name,project,entry_date,hours,description\n"
            "Milo Hart,QA Review,2026-09-15,2.5,Regression pass\n"
        )
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0]["project"], "QA Review")

        database.set_project_budget("QA Review", 50.0)
        budget = database.get_project_budget("QA Review")
        self.assertEqual(budget["budget_hours"], 50.0)

    def test_get_monthly_dashboard_summary(self):
        database.log_time("Lena Ortiz", "Website Redesign", "2026-10-01", 4.0, "Design")
        database.log_time("Lena Ortiz", "Website Redesign", "2026-10-08", 5.0, "Build")
        database.log_time("Nina Shah", "Client Onboarding", "2026-10-09", 3.0, "Kickoff")

        summary = database.get_monthly_dashboard_summary("2026-10")
        self.assertEqual(summary["total_hours"], 12.0)
        self.assertEqual(summary["by_employee"]["Lena Ortiz"], 9.0)
        self.assertEqual(summary["by_project"]["Website Redesign"], 9.0)

    def test_project_summary_exposes_budget_health_status(self):
        project_name = "Budget Alert Project"
        database.log_time("Asha Patel", project_name, "2026-10-12", 6.0, "Budget check")
        database.set_project_budget(project_name, 5.0)

        client = TestClient(app)
        response = client.get(f"/api/projects/{project_name.replace(' ', '%20')}/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertLess(payload["remaining_hours"], 0)
        self.assertEqual(payload["budget_status"], "over budget")
        self.assertTrue(payload["is_over_budget"])

    def test_project_alerts_list_health_for_all_projects(self):
        project_one = "Budget Alert Project"
        project_two = "Low Risk Project"
        database.log_time("Asha Patel", project_one, "2026-10-12", 6.0, "Alert")
        database.set_project_budget(project_one, 5.0)
        database.log_time("Nina Shah", project_two, "2026-10-13", 2.0, "Low")
        database.set_project_budget(project_two, 20.0)

        client = TestClient(app)
        response = client.get("/api/projects/alerts")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["project"] == project_one and item["budget_status"] == "over budget" for item in payload))
        self.assertTrue(any(item["project"] == project_two and item["budget_status"] == "on track" for item in payload))


if __name__ == "__main__":
    unittest.main()

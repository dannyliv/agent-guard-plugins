"""Tests for the Flask dashboard app."""
import sqlite3
import tempfile
import pathlib
import unittest
from unittest.mock import patch


class TestDashboard(unittest.TestCase):
    def _make_app_with_db(self, db_path: pathlib.Path):
        """Patch the DB path and return a Flask test client."""
        with patch("agent_guard_plugins.dashboard.app.DB", db_path):
            from agent_guard_plugins.dashboard.app import _build_app
            app = _build_app()
        app.config["TESTING"] = True
        return app.test_client(), app

    def test_dashboard_returns_200(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = pathlib.Path(tmpdir) / "detections.sqlite"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""CREATE TABLE detections (
                ts REAL, text TEXT, flagged INTEGER, prob REAL,
                owasp TEXT, atlas TEXT, latency_ms REAL, source TEXT
            )""")
            conn.commit()
            conn.close()

            client, _ = self._make_app_with_db(db_path)
            resp = client.get("/")
            self.assertEqual(resp.status_code, 200)

    def test_html_tag_in_logged_text_is_escaped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = pathlib.Path(tmpdir) / "detections.sqlite"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""CREATE TABLE detections (
                ts REAL, text TEXT, flagged INTEGER, prob REAL,
                owasp TEXT, atlas TEXT, latency_ms REAL, source TEXT
            )""")
            # Seed a detection containing a raw script tag.
            conn.execute(
                "INSERT INTO detections VALUES (?,?,?,?,?,?,?,?)",
                (1700000000.0, "<script>alert('xss')</script>", 1, 0.95,
                 "LLM01_direct", "", 12.0, "test"),
            )
            conn.commit()
            conn.close()

            client, _ = self._make_app_with_db(db_path)
            resp = client.get("/")
            self.assertEqual(resp.status_code, 200)
            body = resp.data.decode("utf-8")
            # Flask autoescape converts < and > to HTML entities.
            # The raw unescaped tag must not appear literally.
            self.assertNotIn("<script>alert('xss')</script>", body)


if __name__ == "__main__":
    unittest.main()

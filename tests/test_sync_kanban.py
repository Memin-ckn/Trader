#!/usr/bin/env python3
"""
tests/test_sync_kanban.py
Kanban Senkronizasyon Modülü (sync_kanban.py) için Birim Test Paketi

Tüm testler deterministik ve çevrimdışıdır (Zero Network Call).
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.sync_kanban import (
    _normalize_title,
    check_sync_status,
    parse_kanban_markdown,
    render_kanban_markdown,
)


class TestSyncKanban(unittest.TestCase):
    def test_normalize_title(self) -> None:
        self.assertEqual(_normalize_title("  `UI`  "), "ui")
        self.assertEqual(_normalize_title("Dosya Mimarisi (`src/`)"), "dosya mimarisi (src/)")
        self.assertEqual(_normalize_title("Borsa   (S&P 500)"), "borsa (s&p 500)")

    def test_parse_and_render_roundtrip(self) -> None:
        sample_markdown = """# To do
- UI
    - 11 agent kararını gösteren arayüz.
    - Web app veya markdown.
- Borsa (S&P 500 Takibi)
    - 50 hisse yerine tam endeks takibi.

# In Progress
- Görev 1

# Testing
- Test Görevi

# Complete
- Biten Görev 1
    - Başarıyla tamamlandı.
"""
        sections = parse_kanban_markdown(sample_markdown)
        self.assertEqual(len(sections["Backlog"]), 2)
        self.assertEqual(sections["Backlog"][0]["title"], "UI")
        self.assertIn("11 agent kararını", sections["Backlog"][0]["body"])
        self.assertEqual(sections["Backlog"][1]["title"], "Borsa (S&P 500 Takibi)")

        self.assertEqual(len(sections["In progress"]), 1)
        self.assertEqual(sections["In progress"][0]["title"], "Görev 1")

        self.assertEqual(len(sections["In review"]), 1)
        self.assertEqual(sections["In review"][0]["title"], "Test Görevi")

        self.assertEqual(len(sections["Done"]), 1)
        self.assertEqual(sections["Done"][0]["title"], "Biten Görev 1")

        # Render test
        rendered = render_kanban_markdown(sections)
        self.assertIn("# To do", rendered)
        self.assertIn("- UI", rendered)
        self.assertIn("# In Progress", rendered)
        self.assertIn("# Testing", rendered)
        self.assertIn("# Complete", rendered)

    @patch("src.sync_kanban.fetch_github_items")
    def test_check_sync_status_in_sync(self, mock_fetch) -> None:
        mock_fetch.return_value = [
            {"id": "1", "title": "UI", "status": "Backlog", "body": "body"},
            {"id": "2", "title": "Biten Görev", "status": "Done", "body": "done body"},
        ]

        sample_markdown = """# To do
- UI
    - body

# In Progress

# Testing

# Complete
- Biten Görev
    - done body
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write(sample_markdown)
            tmp.flush()

            diff = check_sync_status(Path(tmp.name))
            self.assertTrue(diff["in_sync"])
            self.assertEqual(len(diff["status_diffs"]), 0)
            self.assertEqual(len(diff["missing_on_github"]), 0)
            self.assertEqual(len(diff["missing_locally"]), 0)

    @patch("src.sync_kanban.fetch_github_items")
    def test_check_sync_status_detects_drift(self, mock_fetch) -> None:
        # GitHub'da UI 'In progress' olarak değiştirilmiş ama yerelde hala 'Backlog'
        mock_fetch.return_value = [
            {"id": "1", "title": "UI", "status": "In progress", "body": "body"},
        ]

        sample_markdown = """# To do
- UI
    - body

# In Progress

# Testing

# Complete
"""
        with tempfile.NamedTemporaryFile("w+", suffix=".md") as tmp:
            tmp.write(sample_markdown)
            tmp.flush()

            diff = check_sync_status(Path(tmp.name))
            self.assertFalse(diff["in_sync"])
            self.assertEqual(len(diff["status_diffs"]), 1)
            self.assertEqual(diff["status_diffs"][0]["local_status"], "Backlog")
            self.assertEqual(diff["status_diffs"][0]["github_status"], "In progress")


if __name__ == "__main__":
    unittest.main()

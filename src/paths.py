#!/usr/bin/env python3
"""
src/paths.py
Merkezi ve Çalışma Dizininden Bağımsız (CWD-Independent) Yol Çözümleyici

Tüm kaynak betikler, veri dosyaları, dokümanlar ve testler proje kök dizinini
bu modül üzerinden dinamik olarak çözümler.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
TESTS_DIR = BASE_DIR / "tests"

STATE_FILE = DATA_DIR / "state.json"
UNIVERSE_FILE = DATA_DIR / "universe.json"
BRIEFING_FILE = DATA_DIR / "daily_briefing.json"
DECISIONS_FILE = DATA_DIR / "decisions.json"

DASHBOARD_FILE = DOCS_DIR / "PORTFOLIO_DASHBOARD.md"
HTML_DASHBOARD_FILE = DOCS_DIR / "dashboard.html"
KANBAN_FILE = DOCS_DIR / "Kanban.md"
COMMITTEE_FILE = DOCS_DIR / "COMMITTEE_PROMPT.md"
PROJECT_CONTEXT_FILE = DOCS_DIR / "PROJECT_CONTEXT.md"
TEST_SCENARIOS_FILE = DOCS_DIR / "test_senaryolari.md"

SKILLS_DIR = BASE_DIR / "claude-trading-skills" / "skills"

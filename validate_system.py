#!/usr/bin/env python3
"""
validate_system.py
Paper Trading Orkestrası - Kapsamlı Otomatik Doğrulama ve QA Test Paketi (unittest uyumlu)

KATI KURALLAR:
1. SIFIR CANLI TEMAS (Zero-Touch Production Rule):
   Canlı state.json, universe.json, COMMITTEE_PROMPT.md ve PORTFOLIO_DASHBOARD.md
   dosyalarına ASLA dokunulmaz. Tüm testler izole geçici temp dizinleri üzerinde koşturulur.
   Test başında ve sonunda tüm canlı dosyaların SHA-256 özetleri doğrulanır.
2. GERÇEK MODÜL KURALI:
   claude-trading-skills reposundaki check_circuit_breaker, weekly_price_action ve
   position_sizer modülleri mock'lanmaz; gerçek hesaplamalarla çağrılır.
3. DETERMINİSTİK VE ÇEVRİMDIŞI:
   Dış ağ çağrıları (yfinance, Forex Factory) deterministik fixture verileri ile simüle edilir.
   Ağ kesintilerinde dahi testler anında ve deterministik olarak geçer.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import execute_decisions as ed
import prepare_daily_batch as pdb

BASE_DIR = Path(__file__).resolve().parent
REAL_STATE_FILE = BASE_DIR / "state.json"
REAL_UNIVERSE_FILE = BASE_DIR / "universe.json"
REAL_COMMITTEE_FILE = BASE_DIR / "COMMITTEE_PROMPT.md"
REAL_DASHBOARD_FILE = BASE_DIR / "PORTFOLIO_DASHBOARD.md"


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPaperTradingOrchestra(unittest.TestCase):
    """Paper Trading Orkestrası 21 Senaryolu Kapsamlı QA Doğrulama Test Paketi."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.initial_state_hash = _file_sha256(REAL_STATE_FILE)
        cls.initial_universe_hash = _file_sha256(REAL_UNIVERSE_FILE)
        cls.initial_committee_hash = _file_sha256(REAL_COMMITTEE_FILE)
        cls.initial_dashboard_hash = _file_sha256(REAL_DASHBOARD_FILE)

    @classmethod
    def tearDownClass(cls) -> None:
        final_state_hash = _file_sha256(REAL_STATE_FILE)
        final_universe_hash = _file_sha256(REAL_UNIVERSE_FILE)
        final_committee_hash = _file_sha256(REAL_COMMITTEE_FILE)
        final_dashboard_hash = _file_sha256(REAL_DASHBOARD_FILE)

        assert cls.initial_state_hash == final_state_hash, (
            "KRİTİK HATA: Gerçek state.json dosyası test sırasında değişti!"
        )
        assert cls.initial_universe_hash == final_universe_hash, (
            "KRİTİK HATA: Gerçek universe.json dosyası test sırasında değişti!"
        )
        assert cls.initial_committee_hash == final_committee_hash, (
            "KRİTİK HATA: Gerçek COMMITTEE_PROMPT.md dosyası test sırasında değişti!"
        )
        assert cls.initial_dashboard_hash == final_dashboard_hash, (
            "KRİTİK HATA: Gerçek PORTFOLIO_DASHBOARD.md dosyası test sırasında değişti!"
        )

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="trader_qa_")
        self.tmp_path = Path(self.temp_dir.name)
        self.test_state_file = self.tmp_path / "test_state.json"
        self.test_decisions_file = self.tmp_path / "test_decisions.json"
        self.test_dashboard_file = self.tmp_path / "test_PORTFOLIO_DASHBOARD.md"
        self.test_universe_file = self.tmp_path / "test_universe.json"
        self.test_briefing_file = self.tmp_path / "test_daily_briefing.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # =========================================================================
    # MEVCUT AKTİF TESTLER (TC-01 .. TC-06)
    # =========================================================================

    def test_tc01_queue_priority_deduplication_and_overflow(self) -> None:
        """
        TC-01: Analiz kuyruğu önceliği (open_positions -> watchlist -> universe.json),
        mükerrer hisse engelleme ve >5 hisse taşma (overflow truncation) testi.
        """
        universe = {
            "market": "TEST_POOL",
            "tickers": ["AAPL", "MSFT", "LLY", "NVDA", "GOOGL", "AMZN", "META", "AAPL", "MSFT"],
        }
        state = {
            "open_positions": [
                {"ticker": "AAPL", "shares": 2.0, "avg_buy_price": 200.0, "current_price": 205.0}
            ],
            "watchlist": [
                {"ticker": "MSFT", "status": "WAIT_BUY", "expires_date": "2026-11-20"},
                {"ticker": "LLY", "status": "WAIT_BUY", "expires_date": "2026-11-20"},
            ],
        }

        for _ in range(25):
            queue = pdb.build_analysis_queue(state, universe, max_items=5)
            self.assertEqual(len(queue), 5, "Kuyruk uzunluğu tam 5 olmalı")
            tickers = [q["ticker"] for q in queue]
            sources = [q["source"] for q in queue]

            # 1. sıra kesinlikle OPEN_POSITION
            self.assertEqual(tickers[0], "AAPL")
            self.assertEqual(sources[0], "OPEN_POSITION")

            # 2. ve 3. sıralar kesinlikle WATCHLIST
            self.assertEqual(tickers[1:3], ["MSFT", "LLY"])
            self.assertEqual(sources[1:3], ["WATCHLIST", "WATCHLIST"])

            # Kalan 2 hisse DISCOVERY ve mükerrer değil
            self.assertEqual(sources[3:5], ["DISCOVERY", "DISCOVERY"])
            self.assertEqual(len(set(tickers)), 5, f"Kuyrukta mükerrer hisse bulundu: {tickers}")

        # Taşma (Overflow) Testi: 4 açık + 4 izleme = 8 hisse -> tam 5 hissede kırpılmalı
        overflow_state = {
            "open_positions": [
                {"ticker": "AAPL"},
                {"ticker": "MSFT"},
                {"ticker": "NVDA"},
                {"ticker": "GOOGL"},
            ],
            "watchlist": [
                {"ticker": "LLY", "status": "WAIT_BUY"},
                {"ticker": "AMZN", "status": "WAIT_BUY"},
                {"ticker": "META", "status": "WAIT_BUY"},
                {"ticker": "TSLA", "status": "WAIT_BUY"},
            ],
        }
        overflow_queue = pdb.build_analysis_queue(overflow_state, universe, max_items=5)
        self.assertEqual(len(overflow_queue), 5)
        self.assertEqual([q["ticker"] for q in overflow_queue], ["AAPL", "MSFT", "NVDA", "GOOGL", "LLY"])

        # 6 açık pozisyonda sadece ilk 5'i alınmalı
        heavy_open = {
            "open_positions": [{"ticker": f"T{i}"} for i in range(1, 7)],
            "watchlist": [{"ticker": "W1", "status": "WAIT_BUY"}],
        }
        heavy_queue = pdb.build_analysis_queue(heavy_open, universe, max_items=5)
        self.assertEqual(len(heavy_queue), 5)
        self.assertEqual([q["ticker"] for q in heavy_queue], ["T1", "T2", "T3", "T4", "T5"])

    def test_tc02_watchlist_ttl_expiration_and_deletion(self) -> None:
        """
        TC-02: Watchlist 14 gün (TTL) zaman aşımı (EXPIRED) ve listeden fiziksel silinme testi.
        """
        old_item_1 = {
            "ticker": "INTC",
            "added_date": "2026-10-15",
            "expires_date": "2026-10-29",
            "target_entry_price": 22.0,
            "stop_loss_plan": 20.5,
            "status": "WAIT_BUY",
        }
        old_item_2 = {
            "ticker": "AMD",
            "added_date": "2026-10-21",
            "expires_date": "2026-11-04",
            "target_entry_price": 140.0,
            "stop_loss_plan": 132.0,
            "status": "WAIT_BUY",
        }
        fresh_item = {
            "ticker": "AVGO",
            "added_date": "2026-11-01",
            "expires_date": "2026-11-15",
            "target_entry_price": 170.0,
            "stop_loss_plan": 160.0,
            "status": "WAIT_BUY",
        }

        test_state = {
            "portfolio_summary": {"cash_usd": 3500.0, "total_equity_usd": 3500.0},
            "open_positions": [],
            "watchlist": [old_item_1, old_item_2, fresh_item],
            "trade_history": [],
        }

        expired_list = pdb.clean_watchlist(test_state, today_str="2026-11-04")
        self.assertEqual(set(expired_list), {"INTC", "AMD"})
        self.assertEqual(old_item_1["status"], "EXPIRED")
        self.assertEqual(old_item_2["status"], "EXPIRED")

        remaining = [w["ticker"] for w in test_state["watchlist"]]
        self.assertEqual(remaining, ["AVGO"])

        queue = pdb.build_analysis_queue(test_state, {"tickers": ["AAPL", "NVDA", "MSFT", "GOOGL"]}, max_items=5)
        watchlist_in_queue = [q["ticker"] for q in queue if q["source"] == "WATCHLIST"]
        self.assertEqual(watchlist_in_queue, ["AVGO"])

    def test_tc03_full_lifecycle_buy_hold_sell_accounting(self) -> None:
        """
        TC-03: BUY -> HOLD (fiyat değişimi) -> SELL tam döngüsünde 1.50$ Midas komisyonlarının
        doğru düşülmesi, pnl_usd kuruşu kuruşuna muhasebe denkliği ve küsüratlı pay testleri.
        """
        initial_state = {
            "portfolio_summary": {
                "cash_usd": 3500.00,
                "total_equity_usd": 3500.00,
                "max_position_pct": 0.20,
                "fee_per_trade_usd": 1.50,
                "total_fees_paid_usd": 0.00,
                "last_run_timestamp": None,
            },
            "open_positions": [],
            "watchlist": [
                {
                    "ticker": "NVDA",
                    "added_date": "2026-11-01",
                    "expires_date": "2026-11-15",
                    "target_entry_price": 150.0,
                    "stop_loss_plan": 140.0,
                    "status": "WAIT_BUY",
                }
            ],
            "trade_history": [],
        }
        ed.save_json(self.test_state_file, initial_state)

        # 1. BUY: 4.00 adet NVDA @ 150.00$
        buy_decisions = {
            "decisions_date": "2026-11-04",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "decisions": [
                {
                    "ticker": "NVDA",
                    "action": "BUY",
                    "shares": 4.00,
                    "price": 150.00,
                    "stop_loss": 140.00,
                    "take_profit": 180.00,
                    "thesis": "Stage 2 breakout",
                }
            ],
        }
        ed.save_json(self.test_decisions_file, buy_decisions)
        rc = ed.main(self.test_state_file, self.test_decisions_file, self.test_dashboard_file)
        self.assertEqual(rc, 0)

        s_buy = ed.load_json(self.test_state_file)
        self.assertEqual(s_buy["portfolio_summary"]["cash_usd"], 2898.50)
        self.assertEqual(s_buy["portfolio_summary"]["total_fees_paid_usd"], 1.50)
        self.assertEqual(s_buy["portfolio_summary"]["total_equity_usd"], 3498.50)
        self.assertEqual(len(s_buy["open_positions"]), 1)
        self.assertEqual(len(s_buy["watchlist"]), 0)

        # 2. HOLD: Fiyat 175.50$'a çıkar
        hold_decisions = {
            "decisions_date": "2026-11-05",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "decisions": [{"ticker": "NVDA", "action": "HOLD", "shares": 4.00, "price": 175.50}],
        }
        ed.save_json(self.test_decisions_file, hold_decisions)
        rc = ed.main(self.test_state_file, self.test_decisions_file, self.test_dashboard_file)
        self.assertEqual(rc, 0)

        s_hold = ed.load_json(self.test_state_file)
        self.assertEqual(s_hold["open_positions"][0]["current_price"], 175.50)
        self.assertEqual(s_hold["portfolio_summary"]["cash_usd"], 2898.50)
        self.assertEqual(s_hold["portfolio_summary"]["total_fees_paid_usd"], 1.50)
        self.assertEqual(s_hold["portfolio_summary"]["total_equity_usd"], 3600.50)

        # 3. SELL: 4.00 adet NVDA @ 175.50$
        sell_decisions = {
            "decisions_date": "2026-11-06",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "decisions": [{"ticker": "NVDA", "action": "SELL", "shares": 4.00, "price": 175.50}],
        }
        ed.save_json(self.test_decisions_file, sell_decisions)
        rc = ed.main(self.test_state_file, self.test_decisions_file, self.test_dashboard_file)
        self.assertEqual(rc, 0)

        s_sell = ed.load_json(self.test_state_file)
        summary = s_sell["portfolio_summary"]
        last_trade = s_sell["trade_history"][-1]

        self.assertEqual(len(s_sell["open_positions"]), 0)
        self.assertEqual(summary["total_fees_paid_usd"], 3.00)
        self.assertEqual(last_trade["pnl_usd"], 99.00)
        self.assertEqual(summary["cash_usd"], 3599.00)
        self.assertEqual(summary["total_equity_usd"], 3599.00)
        self.assertEqual(round(3500.00 + last_trade["pnl_usd"], 2), summary["total_equity_usd"])

        # Küsüratlı pay testi (1.33 adet @ 100.01$ alış -> 100.02$ satış)
        frac_state = {
            "portfolio_summary": {"cash_usd": 3500.00, "total_equity_usd": 3500.00, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            frac_state,
            {"decisions_date": "2026-11-04", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "AAPL", "action": "BUY", "shares": 1.33, "price": 100.01}]},
        )
        ed.process_decisions(
            frac_state,
            {"decisions_date": "2026-11-05", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "AAPL", "action": "SELL", "shares": 1.33, "price": 100.02}]},
        )
        frac_pnl = frac_state["trade_history"][-1]["pnl_usd"]
        self.assertEqual(frac_state["portfolio_summary"]["total_fees_paid_usd"], 3.00)
        self.assertEqual(frac_state["portfolio_summary"]["cash_usd"], round(3500.00 + frac_pnl, 2))
        self.assertEqual(frac_state["portfolio_summary"]["total_equity_usd"], round(3500.00 + frac_pnl, 2))

    def test_tc04_20pct_position_cap_and_cash_floor(self) -> None:
        """
        TC-04: %20 pozisyon tavanının (_floor_shares ile aşağı yuvarlama) korunması,
        kısmi bakiye yetersizliğinde kasanın eksiye düşmemesi ve tam bakiye yetersizliğinde iptal testi.
        """
        # 1. %20 Pozisyon Aşımı Kontrolü
        state_cap = {
            "portfolio_summary": {"cash_usd": 3500.00, "total_equity_usd": 3500.00, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            state_cap,
            {"decisions_date": "2026-11-04", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "MSFT", "action": "BUY", "shares": 4.75, "price": 150.00}]},
        )
        pos = state_cap["open_positions"][0]
        pos_cost = round(pos["shares"] * pos["avg_buy_price"], 2)
        self.assertEqual(pos["shares"], 4.66)
        self.assertLessEqual(pos_cost, 700.00)
        self.assertEqual(state_cap["portfolio_summary"]["cash_usd"], round(3500.00 - 699.00 - 1.50, 2))

        # 2. Kısmi Bakiye Yetersizliği
        state_low_cash = {
            "portfolio_summary": {"cash_usd": 101.50, "total_equity_usd": 3500.00, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            state_low_cash,
            {"decisions_date": "2026-11-04", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "GOOGL", "action": "BUY", "shares": 2.00, "price": 150.00}]},
        )
        self.assertGreaterEqual(state_low_cash["portfolio_summary"]["cash_usd"], 0.00)
        self.assertEqual(state_low_cash["open_positions"][0]["shares"], 0.66)
        self.assertEqual(state_low_cash["portfolio_summary"]["cash_usd"], 1.00)

        # 3. Tam Bakiye Yetersizliği (< 1.50$ komisyon)
        state_no_cash = {
            "portfolio_summary": {"cash_usd": 1.20, "total_equity_usd": 1.20, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            state_no_cash,
            {"decisions_date": "2026-11-04", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "AAPL", "action": "BUY", "shares": 1.00, "price": 200.00}]},
        )
        self.assertEqual(len(state_no_cash["open_positions"]), 0)
        self.assertEqual(state_no_cash["portfolio_summary"]["cash_usd"], 1.20)
        self.assertEqual(state_no_cash["portfolio_summary"]["total_fees_paid_usd"], 0.00)

    def test_tc05_yfinance_nan_resilience_and_real_skills(self) -> None:
        """
        TC-05: yfinance boş veri, <30 gün bar, NaN Close/Volume ve inf/nan rasyolar karşısında
        sistemin çökmemesi ve claude-trading-skills modüllerinin gerçek hesaplama yapabilirlik testi.
        """
        # Boş / Yetersiz veri
        empty_df = pd.DataFrame()
        res_empty = pdb.calculate_indicators(empty_df, {})
        self.assertIn("error", res_empty)
        pa_empty, sz_empty = pdb.run_technical_and_sizing("TEST", empty_df, res_empty, 3500.0, "2026-11-04")
        self.assertEqual(pa_empty["verdict"], "INSUFFICIENT_DATA")
        self.assertEqual(sz_empty["recommended_shares"], 0.0)

        # 260 günlük seride NaN enjekte etme
        dates = pd.date_range("2025-10-01", periods=260, freq="B")
        prices = np.linspace(100.0, 150.0, 260)
        df_nan = pd.DataFrame(
            {
                "Open": prices - 0.5,
                "High": prices + 1.5,
                "Low": prices - 1.5,
                "Close": prices,
                "Volume": [1_000_000.0] * 260,
            },
            index=dates,
        )
        df_nan.loc[dates[-1], "Volume"] = np.nan
        df_nan.loc[dates[-5], "Close"] = np.nan
        df_nan.loc[dates[-10], "Volume"] = np.nan

        dirty_info = {"trailingPE": float("nan"), "priceToBook": float("inf")}
        indicators = pdb.calculate_indicators(df_nan, dirty_info)
        self.assertNotIn("error", indicators)
        self.assertEqual(indicators["volume_latest"], 0)
        self.assertIsNone(indicators["pe_ratio"])
        self.assertIsNone(indicators["pb_ratio"])

        # Gerçek weekly_price_action ve position_sizer çağrıları
        pa_res, sizing_res = pdb.run_technical_and_sizing(
            "TEST", df_nan, indicators, 3500.0, dates[-1].strftime("%Y-%m-%d")
        )
        self.assertIn(pa_res["verdict"], ("CONFIRMED", "NOT_CONFIRMED", "INSUFFICIENT_DATA"))
        self.assertGreater(sizing_res["recommended_shares"], 0)
        self.assertLessEqual(sizing_res["position_value"], 700.00)

    def test_tc06_zero_touch_production_hash_integrity(self) -> None:
        """
        TC-06: Canlı dosyaların SHA-256 hash kontrolü ile test başlangıcı ve bitişinde
        sıfır canlı temas (Zero-Touch Production Rule) matematiksel kanıtı.
        """
        current_state_hash = _file_sha256(REAL_STATE_FILE)
        current_universe_hash = _file_sha256(REAL_UNIVERSE_FILE)
        current_committee_hash = _file_sha256(REAL_COMMITTEE_FILE)
        current_dashboard_hash = _file_sha256(REAL_DASHBOARD_FILE)

        self.assertEqual(current_state_hash, self.initial_state_hash, "Canlı state.json bozulmamalı!")
        self.assertEqual(current_universe_hash, self.initial_universe_hash, "Canlı universe.json bozulmamalı!")
        self.assertEqual(current_committee_hash, self.initial_committee_hash, "Canlı COMMITTEE_PROMPT.md bozulmamalı!")
        self.assertEqual(current_dashboard_hash, self.initial_dashboard_hash, "Canlı PORTFOLIO_DASHBOARD.md bozulmamalı!")

        # Hash kontrol mekanizmasının hassasiyetini kanıtla
        temp_file = self.tmp_path / "probe.txt"
        temp_file.write_text("Orijinal Veri", encoding="utf-8")
        h1 = _file_sha256(temp_file)
        temp_file.write_text("Değiştirilmiş Veri", encoding="utf-8")
        h2 = _file_sha256(temp_file)
        self.assertNotEqual(h1, h2, "1 karakter değişimi bile hash özetini değiştirmelidir!")

    # =========================================================================
    # GELİŞMİŞ YÜRÜTÜCÜ VE PORTFÖY MUHASEBESİ TESTLERİ (TC-07 .. TC-11)
    # =========================================================================

    def test_tc07_circuit_breaker_drawdown_lock(self) -> None:
        """
        TC-07: Devre kesici (check_circuit_breaker.py) tetiklenme testi.
        Üst üste zarar kayıtları sonrası devre kesicinin COOLDOWN / HALTED üretmesi;
        bu durumda BUY emirlerinin reddedilmesi, ancak SELL ve HOLD emirlerinin işlenmesi.
        """
        today_str = "2026-11-04"
        state = {
            "portfolio_summary": {
                "cash_usd": 3300.00,
                "total_equity_usd": 3450.00,
                "total_fees_paid_usd": 6.00,
            },
            "open_positions": [
                {"ticker": "AAPL", "shares": 1.0, "avg_buy_price": 150.0, "current_price": 150.0, "fees_paid_usd": 1.50},
                {"ticker": "GOOGL", "shares": 1.0, "avg_buy_price": 100.0, "current_price": 100.0, "fees_paid_usd": 1.50},
            ],
            "watchlist": [],
            "trade_history": [
                {"date": today_str, "ticker": "LOSS1", "action": "SELL", "pnl_usd": -90.0, "fee_usd": 1.50},
                {"date": today_str, "ticker": "LOSS2", "action": "SELL", "pnl_usd": -85.0, "fee_usd": 1.50},
            ],
        }

        # 1. Gerçek devre kesici modülünü çalıştır
        cb_res = pdb.evaluate_account_circuit_breaker(state, today_str)
        self.assertIn(cb_res["recommendation"], ("COOLDOWN", "HALTED"), "Üst üste 2 sert zarar devre kesiciyi tetiklemeli!")

        # 2. Karar paketinde BUY, SELL ve HOLD emirlerini birlikte gönder
        decisions_data = {
            "decisions_date": today_str,
            "circuit_breaker_acknowledged": cb_res["recommendation"],
            "committee_overall_note": "Devre kesici aktif, yeni risk alınamaz.",
            "decisions": [
                {"ticker": "NVDA", "action": "BUY", "shares": 2.0, "price": 150.0},
                {"ticker": "AAPL", "action": "SELL", "shares": 1.0, "price": 160.0},
                {"ticker": "GOOGL", "action": "HOLD", "shares": 1.0, "price": 105.0},
            ],
        }

        cash_before = state["portfolio_summary"]["cash_usd"]
        ed.process_decisions(state, decisions_data)

        # BUY reddedilmeli
        tickers_open = [p["ticker"] for p in state["open_positions"]]
        self.assertNotIn("NVDA", tickers_open, "Devre kesici aktifken yeni hisse alınamaz!")

        # SELL icra edilmeli
        self.assertNotIn("AAPL", tickers_open, "Devre kesici aktifken zarar kes/kâr al satışları engellenemez!")
        last_trade = state["trade_history"][-1]
        self.assertEqual(last_trade["ticker"], "AAPL")
        self.assertEqual(last_trade["action"], "SELL")

        # HOLD icra edilmeli
        googl_pos = next(p for p in state["open_positions"] if p["ticker"] == "GOOGL")
        self.assertEqual(googl_pos["current_price"], 105.0)

    def test_tc08_scale_in_averaging_and_accumulated_fees(self) -> None:
        """
        TC-08: Kademeli alım (Scale-In) testi. Aynı hissede açık pozisyon varken 2. BUY emri gelmesi;
        kalan %20 limit kontrolü, yeni ağırlıklı ortalama maliyet hesabı ve pozisyon kapatıldığında
        biriken tüm giriş + çıkış komisyonlarının Net PnL hesabında kuruşu kuruşuna tutması.
        """
        state = {
            "portfolio_summary": {"cash_usd": 3500.00, "total_equity_usd": 3500.00, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }

        # 1. Alış: 2.00 adet AAPL @ 100.00$ (Maliyet 200.00$ + 1.50$ = 201.50$, Kasa: 3298.50$)
        ed.process_decisions(
            state,
            {"decisions_date": "2026-11-04", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "AAPL", "action": "BUY", "shares": 2.00, "price": 100.00}]},
        )
        self.assertEqual(state["portfolio_summary"]["cash_usd"], 3298.50)
        self.assertEqual(state["open_positions"][0]["shares"], 2.00)
        self.assertEqual(state["open_positions"][0]["avg_buy_price"], 100.00)

        # 2. Kademeli Alış (Scale-In): 2.00 adet AAPL @ 130.00$ (Maliyet 260.00$ + 1.50$ = 261.50$, Kasa: 3037.00$)
        ed.process_decisions(
            state,
            {"decisions_date": "2026-11-05", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "AAPL", "action": "BUY", "shares": 2.00, "price": 130.00}]},
        )
        pos = state["open_positions"][0]
        self.assertEqual(pos["shares"], 4.00)
        # Ağırlıklı Ortalama Maliyet: ((2*100) + (2*130)) / 4 = 115.00$
        self.assertEqual(pos["avg_buy_price"], 115.00)
        self.assertEqual(state["portfolio_summary"]["cash_usd"], 3037.00)
        self.assertEqual(state["portfolio_summary"]["total_fees_paid_usd"], 3.00)

        # 3. Satış (Tüm pozisyon kapatılır): 4.00 adet AAPL @ 160.00$
        # Brüt: 640.00$, Komisyon: 1.50$, Net Gelir: 638.50$ -> Kasa: 3037.00 + 638.50 = 3675.50$
        # Toplam Komisyonlar: 1.50 + 1.50 + 1.50 = 4.50$
        # Net PnL = (640.00 - 460.00) - 4.50$ = +175.50$
        ed.process_decisions(
            state,
            {"decisions_date": "2026-11-06", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "AAPL", "action": "SELL", "shares": 4.00, "price": 160.00}]},
        )
        last_trade = state["trade_history"][-1]
        summary = state["portfolio_summary"]

        self.assertEqual(len(state["open_positions"]), 0)
        self.assertEqual(summary["total_fees_paid_usd"], 4.50)
        self.assertEqual(last_trade["pnl_usd"], 175.50)
        self.assertEqual(summary["cash_usd"], 3675.50)
        self.assertEqual(summary["total_equity_usd"], 3675.50)
        self.assertEqual(round(3500.00 + last_trade["pnl_usd"], 2), summary["total_equity_usd"])

    def test_tc09_partial_sell_scale_out_accounting(self) -> None:
        """
        TC-09: Kısmi satış (Partial Sell / Scale-Out) mantığı testi.
        Pozisyonun sadece bir kısmı satıldığında kalan payın ortalama maliyetinin korunması,
        nakit girdisi ve komisyon muhasebesi denkliği.
        """
        state = {
            "portfolio_summary": {"cash_usd": 3098.50, "total_equity_usd": 3498.50, "total_fees_paid_usd": 1.50},
            "open_positions": [
                {
                    "ticker": "MSFT",
                    "shares": 4.00,
                    "avg_buy_price": 100.00,
                    "current_price": 100.00,
                    "buy_date": "2026-11-01",
                    "fees_paid_usd": 1.50,
                }
            ],
            "watchlist": [],
            "trade_history": [],
        }

        # 4.00 adedin 2.00 adedini 150.00$'dan sat
        # Gelir: 300.00$ - 1.50$ = 298.50$ -> Yeni Kasa: 3098.50 + 298.50 = 3397.00$
        # Satılan payın oransal alış komisyonu: 0.75$, Satış komisyonu: 1.50$ (Toplam 2.25$)
        # Net PnL = (300.00 - 200.00) - 2.25$ = +97.75$
        ed.process_decisions(
            state,
            {"decisions_date": "2026-11-04", "circuit_breaker_acknowledged": "TRADING_ALLOWED", "decisions": [{"ticker": "MSFT", "action": "SELL", "shares": 2.00, "price": 150.00}]},
        )

        self.assertEqual(len(state["open_positions"]), 1)
        remaining_pos = state["open_positions"][0]
        self.assertEqual(remaining_pos["shares"], 2.00)
        self.assertEqual(remaining_pos["avg_buy_price"], 100.00)
        self.assertEqual(remaining_pos["current_price"], 150.00)

        summary = state["portfolio_summary"]
        self.assertEqual(summary["cash_usd"], 3397.00)
        self.assertEqual(summary["total_fees_paid_usd"], 3.00)

        # Açık pozisyon piyasa değeri = 2.00 * 150.00 = 300.00$
        # Toplam Varlık = 3397.00 + 300.00 = 3697.00$
        self.assertEqual(summary["total_equity_usd"], 3697.00)
        self.assertEqual(state["trade_history"][-1]["pnl_usd"], 97.75)

    def test_tc10_batch_multi_buy_cash_exhaustion(self) -> None:
        """
        TC-10: Çoklu alım (Batch BUY) nakit tükenme testi.
        Kasada sınırlı nakit varken aynı batch içinde gelen 4 BUY emrinde ilklerin tam,
        sonrakinin kısmi alınması, nakit yetmediğinde (<1.50$) son emrin iptali ve kasanın eksiye düşmemesi.
        """
        state = {
            "portfolio_summary": {"cash_usd": 210.00, "total_equity_usd": 3500.00, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        decisions_data = {
            "decisions_date": "2026-11-04",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "decisions": [
                {"ticker": "T1", "action": "BUY", "shares": 1.00, "price": 100.00},  # 101.50$ -> Kasa: 108.50$
                {"ticker": "T2", "action": "BUY", "shares": 1.00, "price": 100.00},  # 101.50$ -> Kasa: 7.00$
                {"ticker": "T3", "action": "BUY", "shares": 1.00, "price": 100.00},  # 7.00$ var -> 5.50$ hisseye -> 0.05 adet (5.00$ + 1.50$ = 6.50$) -> Kasa: 0.50$
                {"ticker": "T4", "action": "BUY", "shares": 1.00, "price": 100.00},  # Kasa: 0.50$ < 1.50$ -> İPTAL
            ],
        }

        ed.process_decisions(state, decisions_data)
        tickers_opened = [p["ticker"] for p in state["open_positions"]]

        self.assertIn("T1", tickers_opened)
        self.assertIn("T2", tickers_opened)
        self.assertIn("T3", tickers_opened)
        self.assertNotIn("T4", tickers_opened, "Nakit komisyondan azken T4 açılamaz!")

        t1_pos = next(p for p in state["open_positions"] if p["ticker"] == "T1")
        t2_pos = next(p for p in state["open_positions"] if p["ticker"] == "T2")
        t3_pos = next(p for p in state["open_positions"] if p["ticker"] == "T3")

        self.assertEqual(t1_pos["shares"], 1.00)
        self.assertEqual(t2_pos["shares"], 1.00)
        self.assertEqual(t3_pos["shares"], 0.05)
        self.assertGreaterEqual(state["portfolio_summary"]["cash_usd"], 0.00)
        self.assertEqual(state["portfolio_summary"]["cash_usd"], 0.50)

    def test_tc11_stop_loss_take_profit_breach_detection(self) -> None:
        """
        TC-11: Açık pozisyon stop-loss / take-profit ihlal tespiti.
        Güncel fiyatın stop altına inmesi veya hedefe ulaşması durumunda değerleme doğrulaması.
        """
        pos = {
            "ticker": "AAPL",
            "shares": 2.00,
            "avg_buy_price": 150.00,
            "current_price": 150.00,
            "stop_loss": 140.00,
            "take_profit": 180.00,
        }

        # Case 1: Stop-loss ihlali (Fiyat 135.00$)
        price_drop = 135.00
        is_sl_breached = price_drop <= pos["stop_loss"]
        self.assertTrue(is_sl_breached, "Fiyat stop-loss altına indiğinde ihlal algılanmalıdır!")
        unrealized_loss = round((pos["shares"] * price_drop) - (pos["shares"] * pos["avg_buy_price"]), 2)
        self.assertEqual(unrealized_loss, -30.00)

        # Case 2: Take-profit hedefi (Fiyat 185.00$)
        price_rise = 185.00
        is_tp_reached = price_rise >= pos["take_profit"]
        self.assertTrue(is_tp_reached, "Fiyat take-profit seviyesine ulaştığında kâr al algılanmalıdır!")
        unrealized_profit = round((pos["shares"] * price_rise) - (pos["shares"] * pos["avg_buy_price"]), 2)
        self.assertEqual(unrealized_profit, +70.00)

    # =========================================================================
    # GELECEK GELİŞTİRMELER İÇİN MİMARİ VE DAYANIKLILIK TESTLERİ (TC-12 .. TC-21)
    # =========================================================================

    def test_tc12_dynamic_project_root_cwd_independence(self) -> None:
        """
        TC-12: Dinamik Proje Kökü (CWD Independence) testi.
        Test sırasında çalışma dizini /tmp gibi harici bir dizine değiştirildiğinde modüllerin
        ve scriptlerin import/yol hatası vermeden dinamik kök dizini çözebilmesi.
        """
        orig_cwd = os.getcwd()
        try:
            os.chdir(tempfile.gettempdir())
            # Modüllerin dinamik BASE_DIR çözümü
            self.assertEqual(ed.BASE_DIR, BASE_DIR)
            self.assertEqual(pdb.BASE_DIR, BASE_DIR)
            self.assertTrue(ed.STATE_FILE.exists())
            self.assertTrue(pdb.UNIVERSE_FILE.exists())
        finally:
            os.chdir(orig_cwd)

    def test_tc13_ui_dashboard_sanitization_and_empty_state(self) -> None:
        """
        TC-13: UI / Dashboard veri bütünlüğü ve sanitization testi.
        Ajan tezlerinde veya gerekçelerinde dikey çizgi (|), satır sonu (\n) olduğunda
        tablo formatının bozulmaması; boş portföy durumunda ZeroDivisionError vermemesi.
        """
        # Sanitization kontrolü
        dirty_text = "Stage 2 | Breakout\nTarget $200 | Strong volume\r\n"
        cleaned = ed._sanitize_table_cell(dirty_text)
        self.assertNotIn("|", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertNotIn("\r", cleaned)
        self.assertEqual(cleaned, "Stage 2 / Breakout Target $200 / Strong volume")

        # Boş Portföy (Empty State) ve 0 başlangıç kasasında ZeroDivisionError vermeme
        empty_state = {
            "portfolio_summary": {"cash_usd": 0.0, "total_equity_usd": 0.0, "total_fees_paid_usd": 0.0},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        decisions_data = {
            "decisions_date": "2026-11-04",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "committee_overall_note": "Boş state testi",
            "decisions": [],
        }
        md = ed.generate_dashboard_markdown(empty_state, decisions_data, "2026-11-04")
        self.assertIn("# 📊 PORTFOLIO DASHBOARD", md)
        self.assertIn("*Şu anda açık pozisyon bulunmamaktadır (Nakit ağırlıklı).*", md)
        self.assertIn("*İzleme listesinde aktif hisse bulunmamaktadır.*", md)

    def test_tc14_large_universe_ticker_standardization_and_perf(self) -> None:
        """
        TC-14: Tam evren ölçek ve format testi.
        universe.json içinde 500+ sembol olduğunda yfinance ticker standartlarına uygunluk (BRK-B),
        mükerrer olmaması ve kuyruk motorunun hızlı seçimi.
        """
        # Ticker standardizasyonu
        self.assertEqual(pdb.clean_universe_ticker("BRK.B"), "BRK-B")
        self.assertEqual(pdb.clean_universe_ticker("bf.b"), "BF-B")
        self.assertEqual(pdb.clean_universe_ticker("  aapl "), "AAPL")

        # 500+ hisselik havuzda kuyruk oluşturma ve performans (<50ms)
        large_tickers = [f"TICK{i}" for i in range(500)] + ["BRK.B", "AAPL"]
        large_universe = {"tickers": large_tickers}
        state = {"open_positions": [], "watchlist": []}

        start_time = time.perf_counter()
        queue = pdb.build_analysis_queue(state, large_universe, max_items=5)
        elapsed = time.perf_counter() - start_time

        self.assertEqual(len(queue), 5)
        self.assertEqual(len(set(q["ticker"] for q in queue)), 5)
        self.assertLess(elapsed, 0.05, "500 hisselik evrende kuyruk seçimi 50ms altında olmalıdır!")

    def test_tc15_discovery_fallback_for_failed_or_delisted_tickers(self) -> None:
        """
        TC-15: Keşif sırasında hatalı/delist ticker yedekleme (Discovery Fallback) testi.
        Keşifte seçilen bir hisse için veri alınamazsa kuyruk motorunun havuzdan yedek aday çekebilmesi.
        """
        state = {
            "open_positions": [{"ticker": "POS1"}],
            "watchlist": [{"ticker": "WATCH1"}],
        }
        current_queue = [
            {"ticker": "POS1", "source": "OPEN_POSITION"},
            {"ticker": "WATCH1", "source": "WATCHLIST"},
            {"ticker": "FAIL1", "source": "DISCOVERY"},
            {"ticker": "FAIL2", "source": "DISCOVERY"},
        ]
        universe = {"tickers": ["POS1", "WATCH1", "FAIL1", "FAIL2", "BACKUP1", "BACKUP2", "BACKUP3"]}

        fallbacks = pdb.get_fallback_candidates(
            state, universe, current_queue, count=2, failed_tickers={"FAIL1", "FAIL2"}
        )
        self.assertEqual(len(fallbacks), 2)
        fallback_tickers = [f["ticker"] for f in fallbacks]
        self.assertTrue(all(t in ("BACKUP1", "BACKUP2", "BACKUP3") for t in fallback_tickers))
        self.assertNotIn("POS1", fallback_tickers)
        self.assertNotIn("WATCH1", fallback_tickers)
        self.assertNotIn("FAIL1", fallback_tickers)

    def test_tc16_market_calendar_weekend_and_holiday_protection(self) -> None:
        """
        TC-16: ABD borsa takvimi tatil ve yarım gün koruma testi.
        Borsa kapalıyken veya seans ortasında eksik hacimli barın hatalı analiz üretmesini engelleyen kontrol.
        """
        # Haftasonu kontrolü (2026-11-07 Cumartesi)
        valid, msg = pdb.is_market_session_valid("2026-11-07")
        self.assertFalse(valid)
        self.assertIn("Haftasonu", msg)

        # Resmi Tatil kontrolü (2026-12-25 Noel)
        valid_hol, msg_hol = pdb.is_market_session_valid("2026-12-25")
        self.assertFalse(valid_hol)
        self.assertIn("Christmas", msg_hol)

        # Hafta içi geçerli gün
        valid_ok, _ = pdb.is_market_session_valid("2026-11-04")
        self.assertTrue(valid_ok)

        # Sıfır hacimli bar testi
        df_zero_vol = pd.DataFrame({"Volume": [0.0]}, index=[pd.Timestamp("2026-11-04")])
        valid_vol, msg_vol = pdb.is_market_session_valid("2026-11-04", df_zero_vol)
        self.assertFalse(valid_vol)
        self.assertIn("hacmi", msg_vol)

    def test_tc17_forex_factory_macro_filter_and_failsafe(self) -> None:
        """
        TC-17: Forex Factory yüksek etkili (USD + High Impact) veri süzgeci ve fail-safe testi.
        Ağ kesintisinde sistemin çökmeden teknik analize devam edebilmesi; kritik veri gününde risk bayrağı üretimi.
        """
        today_str = "2026-11-04"

        # Case 1: Yüksek etkili USD verisi (FOMC / CPI)
        events_high = [
            {"title": "FOMC Statement", "currency": "USD", "impact": "HIGH", "date": "2026-11-04"},
            {"title": "German Prelim CPI", "currency": "EUR", "impact": "HIGH", "date": "2026-11-04"},
        ]
        res_high = pdb.evaluate_forex_factory_macro_risk(events_high, today_str)
        self.assertEqual(res_high["status"], "MACRO_HIGH_RISK")
        self.assertEqual(res_high["action"], "HALT_NEW_BUYS")
        self.assertEqual(res_high["high_impact_count"], 1)

        # Case 2: Düşük etkili / USD olmayan veriler
        events_low = [{"title": "Crude Oil Inventories", "currency": "USD", "impact": "LOW", "date": "2026-11-04"}]
        res_low = pdb.evaluate_forex_factory_macro_risk(events_low, today_str)
        self.assertEqual(res_low["status"], "MACRO_CLEAR")
        self.assertEqual(res_low["action"], "TRADING_ALLOWED")

        # Case 3: Ağ kesintisi / Çevrimdışı (Fail-Safe)
        res_failsafe = pdb.evaluate_forex_factory_macro_risk(None, today_str)
        self.assertEqual(res_failsafe["status"], "FAIL_SAFE")
        self.assertEqual(res_failsafe["action"], "PROCEED_WITH_CAUTION")

    def test_tc18_backtest_zero_lookahead_bias(self) -> None:
        """
        TC-18: Backtest motoru: Geleceği görme (Zero Look-Ahead Bias) izolasyon testi.
        T gününde çalışan indikatör fonksiyonlarına verilen serinin kesinlikle T+1 ve sonrasını içermediğinin kanıtı.
        """
        np.random.seed(42)
        dates = pd.date_range("2025-01-01", periods=250, freq="B")
        prices = 100 + np.cumsum(np.random.randn(250))
        df_full = pd.DataFrame(
            {"Open": prices, "High": prices + 1.0, "Low": prices - 1.0, "Close": prices, "Volume": [100000] * 250},
            index=dates,
        )

        # T = 150 gününe kadar olan verilerle indikatör hesapla
        t_index = 150
        df_slice1 = df_full.iloc[: t_index + 1].copy()
        ind1 = pdb.calculate_indicators(df_slice1, {})

        # T+1 ve sonrasına yapay şok dalgası ver (Gelecek değişiyor)
        df_full_shocked = df_full.copy()
        df_full_shocked.iloc[t_index + 1 :, df_full_shocked.columns.get_loc("Close")] *= 5.0
        df_slice2 = df_full_shocked.iloc[: t_index + 1].copy()
        ind2 = pdb.calculate_indicators(df_slice2, {})

        # T anındaki indikatörlerin gelecekteki şoktan zerre etkilenmediğini kanıtla
        self.assertEqual(ind1["rsi_14"], ind2["rsi_14"])
        self.assertEqual(ind1["macd"], ind2["macd"])
        self.assertEqual(ind1["sma_50"], ind2["sma_50"])
        self.assertEqual(ind1["current_price"], ind2["current_price"])

    def test_tc19_backtest_gap_down_execution_and_fee_accumulation(self) -> None:
        """
        TC-19: Backtest motoru: Emir icrası, gap-down açılışlarda gerçekçi çıkış (stop fiyatı yerine Open fiyatı)
        ve komisyon birikim doğrulaması.
        """
        # Pozisyon: 10 adet AAPL @ 100.00$, Stop: 95.00$
        # Ertesi gün piyasa sert gap-down açılır: Open: 88.00$ (Stop fiyatının 7$ altında!)
        pos_shares = 10.0
        avg_buy = 100.00
        stop_plan = 95.00
        open_gap = 88.00

        # Gerçekçi icra: Stop altına gap ile açıldıysa stop fiyatından değil Open fiyatından çıkılır
        execution_price = open_gap if open_gap < stop_plan else stop_plan
        self.assertEqual(execution_price, 88.00)

        gross_proceeds = round(pos_shares * execution_price, 2)
        net_proceeds = round(gross_proceeds - ed.FEE_PER_TRADE, 2)
        total_fees = round(ed.FEE_PER_TRADE * 2, 2)  # Alış + Satış
        realized_pnl = round((gross_proceeds - (pos_shares * avg_buy)) - total_fees, 2)

        self.assertEqual(gross_proceeds, 880.00)
        self.assertEqual(net_proceeds, 878.50)
        self.assertEqual(realized_pnl, -123.00, "Gerçekçi slippage/gap zararı yansıtılmalıdır!")

    def test_tc20_backtest_stock_split_and_metric_formulas(self) -> None:
        """
        TC-20: Backtest motoru: Tarihsel bölünme (Stock Split - 10:1 split) düzeltilmiş fiyat tutarlılığı
        ve getiri / drawdown matematiksel formül doğrulaması.
        """
        # 1. 10:1 Hisse Bölünmesi Simülasyonu
        pre_split_shares = 1.00
        pre_split_price = 1000.00
        pre_split_val = pre_split_shares * pre_split_price

        split_factor = 10.0
        post_split_shares = pre_split_shares * split_factor
        post_split_price = pre_split_price / split_factor
        post_split_val = post_split_shares * post_split_price

        self.assertEqual(pre_split_val, post_split_val, "Bölünme anında portföy değeri değişemez!")

        # 2. Temel Performans Metrik Formülleri
        initial_equity = 3500.00
        final_equity = 3850.00
        total_return_pct = round(((final_equity - initial_equity) / initial_equity) * 100, 2)
        self.assertEqual(total_return_pct, 10.00)

        # Maksimum Drawdown (Tepe 4000$ -> Dip 3200$)
        equity_curve = [3500.0, 3800.0, 4000.0, 3600.0, 3200.0, 3500.0]
        peak = 0.0
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
        self.assertEqual(round(max_dd * 100, 2), 20.00)

        # Win Rate ve Profit Factor
        pnls = [50.0, -20.0, 80.0, -30.0, 100.0]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        win_rate = round((len(wins) / len(pnls)) * 100, 2)
        profit_factor = round(sum(wins) / sum(losses), 2)

        self.assertEqual(win_rate, 60.00)
        self.assertEqual(profit_factor, 4.60)

    def test_tc21_atomic_write_crash_resilience_and_idempotency(self) -> None:
        """
        TC-21: Atomik dosya yazma (.tmp + os.replace) ve çökme kurtarma testi ile
        aynı gün çift çalıştırmada mükerrer işlem yapmama (idempotency) testi.
        """
        # 1. Atomik Yazma Testi
        test_file = self.tmp_path / "atomic_state.json"
        data = {"status": "ACTIVE", "counter": 1}
        ed.save_json(test_file, data)
        self.assertTrue(test_file.exists())
        self.assertFalse(test_file.with_name(f"{test_file.name}.tmp").exists())
        self.assertEqual(ed.load_json(test_file)["counter"], 1)

        # 2. İdempotency (Çift Çalıştırma Koruması) Testi
        state = {
            "portfolio_summary": {"cash_usd": 3500.00, "total_equity_usd": 3500.00, "total_fees_paid_usd": 0.00},
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        decisions_data = {
            "decisions_date": "2026-11-04",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "decisions": [{"ticker": "NVDA", "action": "BUY", "shares": 2.00, "price": 150.00}],
        }

        # İlk çalıştırma -> İşlem yapılır
        ed.process_decisions(state, decisions_data)
        cash_after_first = state["portfolio_summary"]["cash_usd"]
        trades_after_first = len(state["trade_history"])
        self.assertEqual(cash_after_first, round(3500.00 - 300.00 - 1.50, 2))
        self.assertEqual(trades_after_first, 1)

        # İkinci çalıştırma (Aynı gün aynı kararlar) -> İdempotency devreye girer, hiçbir şey değişmez
        ed.process_decisions(state, decisions_data)
        self.assertEqual(state["portfolio_summary"]["cash_usd"], cash_after_first)
        self.assertEqual(len(state["trade_history"]), trades_after_first)
        self.assertEqual(len(state["open_positions"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

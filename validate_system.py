#!/usr/bin/env python3
"""
validate_system.py
Paper Trading Orkestrası - Otomatik Doğrulama ve QA Test Paketi (unittest / pytest uyumlu)

ÖNEMLİ KURAL:
Mevcut gerçek `state.json` ve `PORTFOLIO_DASHBOARD.md` dosyalarına KESİNLİKLE dokunmaz.
Tüm testler geçici dizin içindeki izole `test_state.json`, `test_decisions.json`,
`test_dashboard.md` dosyaları üzerinde koşturulur ve test başında/sonunda gerçek dosyaların
SHA-256 özetleri (hash) karşılaştırılarak bozulmadığı matematiksel olarak kanıtlanır.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import execute_decisions as ed
import prepare_daily_batch as pdb

BASE_DIR = Path("/home/memin/Projects/Trader").resolve()
REAL_STATE_FILE = BASE_DIR / "state.json"
REAL_DASHBOARD_FILE = BASE_DIR / "PORTFOLIO_DASHBOARD.md"


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPaperTradingOrchestra(unittest.TestCase):
    """Paper Trading Orkestrası kapsamlı QA doğrulama testleri."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.initial_state_hash = _file_sha256(REAL_STATE_FILE)
        cls.initial_dashboard_hash = _file_sha256(REAL_DASHBOARD_FILE)

    @classmethod
    def tearDownClass(cls) -> None:
        final_state_hash = _file_sha256(REAL_STATE_FILE)
        final_dashboard_hash = _file_sha256(REAL_DASHBOARD_FILE)
        assert cls.initial_state_hash == final_state_hash, (
            "KRİTİK HATA: Gerçek state.json dosyası test sırasında değişti!"
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
    # SENARYO A: Kuyruk oluşturma, mükerrer hisse engelleme ve >5 taşma testi
    # =========================================================================
    def test_scenario_a_queue_priority_deduplication_and_overflow(self) -> None:
        """
        Senaryo A:
        1. Öncelik sırası: open_positions -> watchlist -> random_discovery (toplam maks 5).
        2. Mükerrer hisse engelleme: open_positions veya watchlist içindeki hisseler
           universe.json'da bulunsa dahi random_discovery tarafından tekrar seçilemez.
        3. >5 hisse taşma (overflow): open_positions + watchlist > 5 olduğunda kod çökmez,
           öncelik sırasını koruyarak tam 5 hissede kırpar (truncate).
        """
        universe = {
            "market": "TEST_POOL",
            "tickers": ["AAPL", "MSFT", "LLY", "NVDA", "GOOGL", "AMZN", "META", "AAPL", "MSFT"],
        }

        # 1 & 2: Öncelik ve Mükerrer Engelleme Testi
        state = {
            "open_positions": [
                {"ticker": "AAPL", "shares": 2.0, "avg_buy_price": 200.0, "current_price": 205.0}
            ],
            "watchlist": [
                {"ticker": "MSFT", "status": "WAIT_BUY", "expires_date": "2026-11-20"},
                {"ticker": "LLY", "status": "WAIT_BUY", "expires_date": "2026-11-20"},
            ],
        }

        for _ in range(30):
            queue = pdb.build_analysis_queue(state, universe, max_items=5)
            self.assertEqual(len(queue), 5, "Kuyruk uzunluğu tam 5 olmalı")
            tickers = [q["ticker"] for q in queue]
            sources = [q["source"] for q in queue]

            # İlk sıradaki kesinlikle OPEN_POSITION (AAPL)
            self.assertEqual(tickers[0], "AAPL")
            self.assertEqual(sources[0], "OPEN_POSITION")

            # 2. ve 3. sıradakiler kesinlikle WATCHLIST (MSFT, LLY)
            self.assertEqual(tickers[1:3], ["MSFT", "LLY"])
            self.assertEqual(sources[1:3], ["WATCHLIST", "WATCHLIST"])

            # Son 2 hisse DISCOVERY olmalı ve AAPL/MSFT/LLY içermemeli
            self.assertEqual(sources[3:5], ["DISCOVERY", "DISCOVERY"])
            self.assertEqual(len(set(tickers)), 5, f"Kuyrukta mükerrer hisse bulundu: {tickers}")

        # 3: >5 Hisse Taşma (Overflow) Testi (4 açık pozisyon + 4 izleme listesi = 8 hisse)
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
        self.assertEqual(len(overflow_queue), 5, "Taşma durumunda kuyruk 5 hissede kırpılmalı")
        self.assertEqual(
            [q["ticker"] for q in overflow_queue],
            ["AAPL", "MSFT", "NVDA", "GOOGL", "LLY"],
        )
        self.assertEqual(
            [q["source"] for q in overflow_queue],
            ["OPEN_POSITION", "OPEN_POSITION", "OPEN_POSITION", "OPEN_POSITION", "WATCHLIST"],
        )

        # 6 açık pozisyon olduğunda sadece ilk 5 açık pozisyon alınmalı
        heavy_open_state = {
            "open_positions": [{"ticker": f"T{i}"} for i in range(1, 7)],
            "watchlist": [{"ticker": "W1", "status": "WAIT_BUY"}],
        }
        heavy_queue = pdb.build_analysis_queue(heavy_open_state, universe, max_items=5)
        self.assertEqual(len(heavy_queue), 5)
        self.assertEqual([q["ticker"] for q in heavy_queue], ["T1", "T2", "T3", "T4", "T5"])

    # =========================================================================
    # SENARYO B: 14 günü geçmiş watchlist elemanının EXPIRED olarak silinmesi
    # =========================================================================
    def test_scenario_b_watchlist_ttl_expiration_and_deletion(self) -> None:
        """
        Senaryo B:
        14 günü doldurmuş veya geçmiş watchlist elemanları clean_watchlist()
        tarafından EXPIRED olarak işaretlenmeli ve aktif watchlist'ten silinmelidir.
        """
        old_item_1 = {
            "ticker": "INTC",
            "added_date": "2026-10-15",
            "expires_date": "2026-10-29",  # 14 günü geçmiş
            "target_entry_price": 22.0,
            "stop_loss_plan": 20.5,
            "status": "WAIT_BUY",
            "reason": "Test geçmiş tarih",
        }
        old_item_2 = {
            "ticker": "AMD",
            "added_date": "2026-10-21",
            "expires_date": "2026-11-04",  # Tam 14. gün (bugün doluyor)
            "target_entry_price": 140.0,
            "stop_loss_plan": 132.0,
            "status": "WAIT_BUY",
            "reason": "Test sınır tarih",
        }
        fresh_item = {
            "ticker": "AVGO",
            "added_date": "2026-11-01",
            "expires_date": "2026-11-15",  # Henüz süresi dolmadı
            "target_entry_price": 170.0,
            "stop_loss_plan": 160.0,
            "status": "WAIT_BUY",
            "reason": "Test aktif hisse",
        }

        test_state = {
            "portfolio_summary": {"cash_usd": 3500.0, "total_equity_usd": 3500.0},
            "open_positions": [],
            "watchlist": [old_item_1, old_item_2, fresh_item],
            "trade_history": [],
        }

        expired_list = pdb.clean_watchlist(test_state, today_str="2026-11-04")

        # 1. Süresi dolanlar EXPIRED listesinde dönmeli ve referans statüleri EXPIRED olmalı
        self.assertEqual(set(expired_list), {"INTC", "AMD"})
        self.assertEqual(old_item_1["status"], "EXPIRED")
        self.assertEqual(old_item_2["status"], "EXPIRED")

        # 2. Süresi dolanlar state["watchlist"] içinden tamamen silinmiş olmalı
        remaining_tickers = [w["ticker"] for w in test_state["watchlist"]]
        self.assertEqual(remaining_tickers, ["AVGO"])

        # 3. Kuyruk oluşturulduğunda süresi dolanlar kuyruğa WATCHLIST olarak girmemeli
        queue = pdb.build_analysis_queue(test_state, {"tickers": ["AAPL", "NVDA", "GOOGL", "MSFT"]}, max_items=5)
        watchlist_in_queue = [q["ticker"] for q in queue if q["source"] == "WATCHLIST"]
        self.assertEqual(watchlist_in_queue, ["AVGO"])

    # =========================================================================
    # SENARYO C: BUY -> Fiyat değişimiyle HOLD -> SELL tam döngü muhasebe testi
    # =========================================================================
    def test_scenario_c_full_lifecycle_buy_hold_sell_accounting(self) -> None:
        """
        Senaryo C:
        İzole dosyalar üzerinde:
        1. Başlangıç: 3500.00$ nakit, 0.00$ komisyon.
        2. BUY: 4.00 adet NVDA @ 150.00$ (Maliyet 600.00$ + 1.50$ komisyon = 601.50$).
           -> cash_usd = 2898.50$, total_fees_paid_usd = 1.50$, total_equity_usd = 3498.50$.
        3. HOLD: NVDA fiyatı 175.50$'a yükselir (Pozisyon değeri = 702.00$).
           -> current_price = 175.50$, cash_usd = 2898.50$, total_equity_usd = 3600.50$.
        4. SELL: 4.00 adet NVDA @ 175.50$ satılır (Brüt 702.00$ - 1.50$ komisyon = 700.50$).
           -> total_fees_paid_usd = 3.00$
           -> pnl_usd = (702.00 - 600.00) - 3.00 = +99.00$
           -> cash_usd = 2898.50 + 700.50 = 3599.00$
           -> total_equity_usd = 3599.00$ (Başlangıç 3500.00$ + Net PnL 99.00$ ile kuruşu kuruşuna eşit!).
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
                    "reason": "Breakout bekleniyor",
                }
            ],
            "trade_history": [],
        }
        ed.save_json(self.test_state_file, initial_state)

        # --- ADIM 1: BUY ---
        buy_decisions = {
            "decisions_date": "2026-11-04",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "committee_overall_note": "Test BUY",
            "decisions": [
                {
                    "ticker": "NVDA",
                    "action": "BUY",
                    "shares": 4.00,
                    "price": 150.00,
                    "stop_loss": 140.00,
                    "take_profit": 180.00,
                    "thesis": "Stage 2 breakout",
                    "reason": "Alım onayı",
                }
            ],
        }
        ed.save_json(self.test_decisions_file, buy_decisions)
        rc = ed.main(
            state_file=self.test_state_file,
            decisions_file=self.test_decisions_file,
            dashboard_file=self.test_dashboard_file,
        )
        self.assertEqual(rc, 0)

        state_after_buy = ed.load_json(self.test_state_file)
        self.assertEqual(state_after_buy["portfolio_summary"]["cash_usd"], 2898.50)
        self.assertEqual(state_after_buy["portfolio_summary"]["total_fees_paid_usd"], 1.50)
        self.assertEqual(state_after_buy["portfolio_summary"]["total_equity_usd"], 3498.50)
        self.assertEqual(len(state_after_buy["open_positions"]), 1)
        self.assertEqual(len(state_after_buy["watchlist"]), 0, "Alınan hisse watchlist'ten silinmeli")

        # --- ADIM 2: HOLD (Fiyat 150.00$ -> 175.50$'a değişir) ---
        hold_decisions = {
            "decisions_date": "2026-11-05",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "committee_overall_note": "Test HOLD",
            "decisions": [
                {
                    "ticker": "NVDA",
                    "action": "HOLD",
                    "shares": 4.00,
                    "price": 175.50,
                    "stop_loss": 160.00,
                    "reason": "Trend devam ediyor, izleyen stop yükseltildi",
                }
            ],
        }
        ed.save_json(self.test_decisions_file, hold_decisions)
        rc = ed.main(
            state_file=self.test_state_file,
            decisions_file=self.test_decisions_file,
            dashboard_file=self.test_dashboard_file,
        )
        self.assertEqual(rc, 0)

        state_after_hold = ed.load_json(self.test_state_file)
        self.assertEqual(state_after_hold["open_positions"][0]["current_price"], 175.50)
        self.assertEqual(state_after_hold["open_positions"][0]["stop_loss"], 160.00)
        self.assertEqual(state_after_hold["portfolio_summary"]["cash_usd"], 2898.50)
        self.assertEqual(state_after_hold["portfolio_summary"]["total_fees_paid_usd"], 1.50)
        self.assertEqual(state_after_hold["portfolio_summary"]["total_equity_usd"], 3600.50)

        # --- ADIM 3: SELL (4.00 adet @ 175.50$) ---
        sell_decisions = {
            "decisions_date": "2026-11-06",
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "committee_overall_note": "Test SELL",
            "decisions": [
                {
                    "ticker": "NVDA",
                    "action": "SELL",
                    "shares": 4.00,
                    "price": 175.50,
                    "reason": "Hedef fiyata ulaşıldı",
                }
            ],
        }
        ed.save_json(self.test_decisions_file, sell_decisions)
        rc = ed.main(
            state_file=self.test_state_file,
            decisions_file=self.test_decisions_file,
            dashboard_file=self.test_dashboard_file,
        )
        self.assertEqual(rc, 0)

        state_after_sell = ed.load_json(self.test_state_file)
        summary = state_after_sell["portfolio_summary"]
        sell_record = state_after_sell["trade_history"][-1]

        self.assertEqual(len(state_after_sell["open_positions"]), 0)
        self.assertEqual(summary["total_fees_paid_usd"], 3.00)
        self.assertEqual(sell_record["action"], "SELL")
        self.assertEqual(sell_record["fee_usd"], 1.50)
        self.assertEqual(sell_record["pnl_usd"], 99.00)
        self.assertEqual(summary["cash_usd"], 3599.00)
        self.assertEqual(summary["total_equity_usd"], 3599.00)
        self.assertEqual(
            round(3500.00 + sell_record["pnl_usd"], 2),
            summary["total_equity_usd"],
            "Başlangıç kasası + Net PnL kuruşu kuruşuna toplam varlığa eşit olmalı!",
        )

        # Küsüratlı pay ve fiyatlarda (1.33 adet @ 100.01$ alış -> 100.02$ satış) 1 cent sapma olmaması testi
        frac_state = {
            "portfolio_summary": {
                "cash_usd": 3500.00,
                "total_equity_usd": 3500.00,
                "total_fees_paid_usd": 0.00,
            },
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            frac_state,
            {
                "decisions_date": "2026-11-04",
                "circuit_breaker_acknowledged": "TRADING_ALLOWED",
                "decisions": [{"ticker": "AAPL", "action": "BUY", "shares": 1.33, "price": 100.01}],
            },
        )
        ed.process_decisions(
            frac_state,
            {
                "decisions_date": "2026-11-05",
                "circuit_breaker_acknowledged": "TRADING_ALLOWED",
                "decisions": [{"ticker": "AAPL", "action": "SELL", "shares": 1.33, "price": 100.02}],
            },
        )
        frac_pnl = frac_state["trade_history"][-1]["pnl_usd"]
        self.assertEqual(frac_state["portfolio_summary"]["total_fees_paid_usd"], 3.00)
        self.assertEqual(frac_state["portfolio_summary"]["cash_usd"], round(3500.00 + frac_pnl, 2))
        self.assertEqual(frac_state["portfolio_summary"]["total_equity_usd"], round(3500.00 + frac_pnl, 2))

    # =========================================================================
    # SENARYO D: Kasa yetersizliği ve %20 pozisyon aşımı davranışı testi
    # =========================================================================
    def test_scenario_d_insufficient_cash_and_20pct_position_cap(self) -> None:
        """
        Senaryo D:
        1. %20 Pozisyon Aşımı: 3500$ kasada (%20 limit = 700.00$), 150.00$ fiyattan 10 adet (1500$)
           veya 4.75 adet (712.50$) BUY emri geldiğinde:
           - Aşağı yuvarlama (floor) ile en fazla 4.66 adet (699.00$ <= 700.00$) alınmalı.
           - 4.67 adede (700.50$) yukarı yuvarlanıp %20 sınırı ASLA delinmemeli.
        2. Kısmi Kasa Yetersizliği: Kasada sadece 101.50$ nakit varken 150.00$ fiyattan 2 adet BUY geldiğinde:
           - 1.50$ komisyon düşüldükten sonra kalan 100.00$ ile floor(100/150) = 0.66 adet (99.00$) alınmalı.
           - Kasa 101.50 - (99.00 + 1.50) = 1.00$ (>= 0) kalmalı, ASLA eksiye (-0.50$) düşmemeli!
        3. Tam Kasa Yetersizliği: Kasada 1.20$ (< 1.50$ komisyon) varken BUY geldiğinde:
           - İşlem tamamen reddedilmeli, pozisyon açılmamalı, komisyon kesilmemeli.
        """
        # 1. %20 Pozisyon Aşımı Testi (712.50$ -> eski %2 tolerans hatasını da yakalar)
        state_cap = {
            "portfolio_summary": {
                "cash_usd": 3500.00,
                "total_equity_usd": 3500.00,
                "total_fees_paid_usd": 0.00,
            },
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            state_cap,
            {
                "decisions_date": "2026-11-04",
                "circuit_breaker_acknowledged": "TRADING_ALLOWED",
                "decisions": [
                    {
                        "ticker": "MSFT",
                        "action": "BUY",
                        "shares": 4.75,  # 4.75 * 150 = 712.50$ (> 700.00$ limit)
                        "price": 150.00,
                    }
                ],
            },
        )
        pos = state_cap["open_positions"][0]
        pos_cost = round(pos["shares"] * pos["avg_buy_price"], 2)
        self.assertEqual(pos["shares"], 4.66, "Pay adedi 4.66'ya floor edilmeli (4.67 olursa 700.50$ > 700$ olur)")
        self.assertLessEqual(pos_cost, 700.00, "Pozisyon maliyeti %20 limitini (700$) asla aşamaz")
        self.assertEqual(state_cap["portfolio_summary"]["cash_usd"], round(3500.00 - 699.00 - 1.50, 2))

        # 2. Kısmi Kasa Yetersizliği (101.50$ nakit ile 150$'lık hisse alımı)
        state_low_cash = {
            "portfolio_summary": {
                "cash_usd": 101.50,
                "total_equity_usd": 3500.00,
                "total_fees_paid_usd": 0.00,
            },
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            state_low_cash,
            {
                "decisions_date": "2026-11-04",
                "circuit_breaker_acknowledged": "TRADING_ALLOWED",
                "decisions": [
                    {
                        "ticker": "GOOGL",
                        "action": "BUY",
                        "shares": 2.00,
                        "price": 150.00,
                    }
                ],
            },
        )
        self.assertGreaterEqual(
            state_low_cash["portfolio_summary"]["cash_usd"],
            0.00,
            "Nakit bakiye ASLA eksiye düşemez!",
        )
        self.assertEqual(state_low_cash["open_positions"][0]["shares"], 0.66)
        self.assertEqual(state_low_cash["portfolio_summary"]["cash_usd"], 1.00)

        # 3. Tam Kasa Yetersizliği (1.20$ nakit < 1.50$ komisyon)
        state_no_cash = {
            "portfolio_summary": {
                "cash_usd": 1.20,
                "total_equity_usd": 1.20,
                "total_fees_paid_usd": 0.00,
            },
            "open_positions": [],
            "watchlist": [],
            "trade_history": [],
        }
        ed.process_decisions(
            state_no_cash,
            {
                "decisions_date": "2026-11-04",
                "circuit_breaker_acknowledged": "TRADING_ALLOWED",
                "decisions": [
                    {
                        "ticker": "AAPL",
                        "action": "BUY",
                        "shares": 1.00,
                        "price": 200.00,
                    }
                ],
            },
        )
        self.assertEqual(len(state_no_cash["open_positions"]), 0, "Bakiye yetersizken pozisyon açılamaz")
        self.assertEqual(state_no_cash["portfolio_summary"]["cash_usd"], 1.20, "İptal edilen işlemde nakit değişemez")
        self.assertEqual(state_no_cash["portfolio_summary"]["total_fees_paid_usd"], 0.00)

    # =========================================================================
    # EK DENETİM TESTİ: yfinance NaN / Eksik Veri ve Gerçek Skill Entegrasyonu
    # =========================================================================
    def test_yfinance_nan_resilience_and_real_skills_integration(self) -> None:
        """
        yfinance NaN veya eksik veri döndürdüğünde calculate_indicators ve
        run_technical_and_sizing çökmemeli; claude-trading-skills modülleri
        gerçekten çağrılmalıdır.
        """
        # 1. Boş veya <30 gün veri
        empty_df = pd.DataFrame()
        res_empty = pdb.calculate_indicators(empty_df, {})
        self.assertIn("error", res_empty)
        pa_empty, sz_empty = pdb.run_technical_and_sizing("TEST", empty_df, res_empty, 3500.0, "2026-11-04")
        self.assertEqual(pa_empty["verdict"], "INSUFFICIENT_DATA")
        self.assertEqual(sz_empty["recommended_shares"], 0.0)

        # 2. İçinde NaN satırlar ve NaN Volume/PE bulunan 260 günlük veri
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
        # Son satırların bazılarına NaN enjekte et
        df_nan.loc[dates[-1], "Volume"] = np.nan
        df_nan.loc[dates[-5], "Close"] = np.nan
        df_nan.loc[dates[-10], "Volume"] = np.nan

        dirty_info = {"trailingPE": float("nan"), "priceToBook": float("inf")}
        indicators = pdb.calculate_indicators(df_nan, dirty_info)
        self.assertNotIn("error", indicators)
        self.assertEqual(indicators["volume_latest"], 0)
        self.assertIsNone(indicators["pe_ratio"])
        self.assertIsNone(indicators["pb_ratio"])

        pa_res, sizing_res = pdb.run_technical_and_sizing(
            "TEST", df_nan, indicators, 3500.0, dates[-1].strftime("%Y-%m-%d")
        )
        self.assertIn(pa_res["verdict"], ("CONFIRMED", "NOT_CONFIRMED", "INSUFFICIENT_DATA"))
        self.assertGreater(sizing_res["recommended_shares"], 0)
        self.assertLessEqual(sizing_res["position_value"], 700.00)


if __name__ == "__main__":
    unittest.main(verbosity=2)

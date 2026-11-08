#!/usr/bin/env python3
"""
src/backtest_step.py
Otonom Borsa Orkestrası — Adım Adım Backtest Yürütücüsü ve İzole Checkpoint Kasası

SIFIR CANLI TEMAS: Yalnızca şu izole dosyalara yazar:
    data/backtest_state.json, data/backtest_briefing.json (+ okur: data/backtest_decisions.json),
    docs/BACKTEST_REPORT.md
Canlı `state.json`, `daily_briefing.json`, `decisions.json` ve `PORTFOLIO_DASHBOARD.md` dosyalarına
asla dokunulmaz.

Modlar:
    --init     : Yeni izole simülasyon kasasını (3.500 $) kurar.
    --prepare  : Simülasyon tarihini ilerletir, ara günlerde SL/TP'yi Cevap Anahtarından icra eder,
                 Zaman Kilidiyle `backtest_briefing.json` üretir (durum -> AWAITING_DECISIONS).
    --execute  : `backtest_decisions.json` kararlarını kasaya işler, portföyü o günün kapanışıyla
                 değerler, equity_curve'e (portföy + SPY Buy & Hold) ekler, karneyi günceller (durum -> READY).
    --status   : Güncel simülasyon özetini yazdırır.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.backtest_data import (
    check_sl_tp_in_window,
    get_cached_or_fetch_ticker,
    get_trading_days,
)
from src.execute_decisions import (
    FEE_PER_TRADE,
    INITIAL_CASH,
    load_json,
    process_decisions,
    save_json,
)
from src.paths import (
    BACKTEST_BRIEFING_FILE,
    BACKTEST_CACHE_DIR,
    BACKTEST_DECISIONS_FILE,
    BACKTEST_REPORT_FILE,
    BACKTEST_STATE_FILE,
    DATA_DIR,
    UNIVERSE_FILE,
)
from src.ui_dashboard import sanitize_table_cell, save_text_atomic

STATUS_READY = "READY"
STATUS_AWAITING = "AWAITING_DECISIONS"
STATUS_COMPLETED = "COMPLETED"

DEFAULT_START = "2024-11-04"
DEFAULT_END = "2026-11-04"
DEFAULT_STEP_DAYS = 7
CALENDAR_RANGE = ("2022-10-01", "2100-12-31")


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _usd(val: float) -> str:
    sign = "-" if val < 0 else ""
    return f"{sign}${abs(val):,.2f}"


def _signed_usd(val: float) -> str:
    return f"{'+' if val >= 0 else '-'}${abs(val):,.2f}"


def _signed_pct(val: float) -> str:
    return f"{val:+.2f}%"


def _validate_date(value: str, label: str) -> str:
    try:
        return date.fromisoformat(str(value).strip()[:10]).strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} geçersiz (YYYY-MM-DD bekleniyor): {value}") from exc


def _trading_days(cache_dir: Path, allow_network: bool) -> list[str]:
    """SPY takvimini baz alan tüm geçerli borsa iş günleri."""
    return get_trading_days(CALENDAR_RANGE[0], CALENDAR_RANGE[1], cache_dir=cache_dir, allow_network=allow_network)


def _close_on_or_before(
    ticker: str, as_of: str, cache_dir: Path, allow_network: bool
) -> float | None:
    """`as_of` tarihi ve öncesindeki son kapanış fiyatı (Zaman Kilitli)."""
    df, _ = get_cached_or_fetch_ticker(
        ticker, as_of_date=as_of, cache_dir=cache_dir, allow_network=allow_network, max_lookback_bars=5
    )
    if df.empty:
        return None
    val = float(df["Close"].iloc[-1])
    return round(val, 2) if math.isfinite(val) and val > 0 else None


def next_sim_date(state: dict[str, Any], trading_days: list[str]) -> str | None:
    """
    Bir sonraki simülasyon gününü hesaplar. İlk adımda `start_date`'e, sonrasında
    `current_sim_date + step_days` tarihini izleyen ilk borsa iş gününe gider.
    `end_date` aşılırsa son geçerli iş gününde durur; ilerlenecek gün kalmadıysa None döner.
    """
    cur = state["current_sim_date"]
    start = state["start_date"]
    step = max(1, int(state.get("step_days", DEFAULT_STEP_DAYS)))
    valid = [d for d in trading_days if d <= state["end_date"]]
    if not valid or cur >= valid[-1]:
        return None

    if cur < start:
        target = start
    else:
        target = (date.fromisoformat(cur) + timedelta(days=step)).strftime("%Y-%m-%d")

    candidate = next((d for d in valid if d >= target and d > cur), None)
    return candidate if candidate is not None else valid[-1]


def compute_equity(state: dict[str, Any]) -> float:
    """cash + açık pozisyon piyasa değeri (cent hassasiyetli)."""
    positions_val = round(
        sum(round(float(p["shares"]) * float(p["current_price"]), 2) for p in state.get("open_positions", [])),
        2,
    )
    return round(round(float(state["cash_usd"]), 2) + positions_val, 2)


def mark_to_market(state: dict[str, Any], as_of: str, cache_dir: Path, allow_network: bool) -> None:
    """Açık pozisyonları `as_of` kapanışıyla değerler ve total_equity_usd'yi günceller."""
    for pos in state.get("open_positions", []):
        px = _close_on_or_before(pos["ticker"], as_of, cache_dir, allow_network)
        if px is not None:
            pos["current_price"] = px
    state["total_equity_usd"] = compute_equity(state)


def _run_engine(state: dict[str, Any], decisions_data: dict[str, Any]) -> None:
    """
    Backtest kasasını `execute_decisions.process_decisions` motoruna (aynı %20 tavan, `_floor_shares`,
    1.50$ komisyon, idempotency) uyarlayıp kararları işler ve sonucu düz şemaya geri yazar.
    """
    engine_state = {
        "portfolio_summary": {
            "cash_usd": state["cash_usd"],
            "total_equity_usd": state["total_equity_usd"],
            "total_fees_paid_usd": state["total_fees_paid_usd"],
            "last_decisions_digest": state.get("last_decisions_digest"),
        },
        "open_positions": state["open_positions"],
        "watchlist": state["watchlist"],
        "trade_history": state["trade_history"],
    }
    process_decisions(engine_state, decisions_data, enforce_risk_cap=True)
    summary = engine_state["portfolio_summary"]
    state["cash_usd"] = round(float(summary["cash_usd"]), 2)
    state["total_equity_usd"] = round(float(summary["total_equity_usd"]), 2)
    state["total_fees_paid_usd"] = round(float(summary["total_fees_paid_usd"]), 2)
    state["last_decisions_digest"] = summary.get("last_decisions_digest")
    state["open_positions"] = engine_state["open_positions"]
    state["watchlist"] = engine_state["watchlist"]
    state["trade_history"] = engine_state["trade_history"]


def spy_benchmark_value(state: dict[str, Any], as_of: str, cache_dir: Path, allow_network: bool) -> float:
    """Aynı tarihte 3.500 $'lık SPY Buy & Hold karşılığı."""
    spy_px = _close_on_or_before("SPY", as_of, cache_dir, allow_network)
    base = float(state.get("spy_start_price") or 0.0)
    if spy_px is None or base <= 0:
        raise RuntimeError(f"SPY kıyaslama fiyatı hesaplanamadı (as_of={as_of}).")
    return round(INITIAL_CASH * spy_px / base, 2)


# ---------------------------------------------------------------------------
# Mod: --init
# ---------------------------------------------------------------------------
def init_state(
    start_date: str,
    end_date: str,
    step_days: int,
    state_file: Path = BACKTEST_STATE_FILE,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    start_date = _validate_date(start_date, "start-date")
    end_date = _validate_date(end_date, "end-date")
    if step_days < 1:
        raise ValueError("step-days en az 1 olmalı.")
    if end_date <= start_date:
        raise ValueError("end-date, start-date'ten sonra olmalı.")
    if state_file.exists() and not force:
        raise FileExistsError(f"{state_file} zaten var. Sıfırlamak için --force kullanın.")

    days = _trading_days(cache_dir, allow_network)
    first_day = next((d for d in days if d >= start_date), None)
    if first_day is None:
        raise RuntimeError("Önbellekte start-date sonrası SPY verisi yok (önce src/backtest_data.py çalıştırın).")

    spy_start = _close_on_or_before("SPY", first_day, cache_dir, allow_network)
    if spy_start is None:
        raise RuntimeError("SPY başlangıç fiyatı bulunamadı.")

    # İlk --prepare adımı start_date'in kendisine inebilsin diye başlangıç öncesi son iş gününden başlanır.
    prev_day = next((d for d in reversed(days) if d < start_date), None)
    if prev_day is None:
        prev_day = (date.fromisoformat(start_date) - timedelta(days=1)).strftime("%Y-%m-%d")

    state: dict[str, Any] = {
        "cash_usd": INITIAL_CASH,
        "total_equity_usd": INITIAL_CASH,
        "total_fees_paid_usd": 0.0,
        "start_date": start_date,
        "end_date": end_date,
        "current_sim_date": prev_day,
        "step_days": step_days,
        "status": STATUS_READY,
        "spy_start_date": first_day,
        "spy_start_price": spy_start,
        "open_positions": [],
        "watchlist": [],
        "trade_history": [],
        "equity_curve": [],
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(state_file, state)
    return state


# ---------------------------------------------------------------------------
# Mod: --prepare
# ---------------------------------------------------------------------------
def apply_interim_exits(
    state: dict[str, Any],
    prev_date: str,
    new_date: str,
    cache_dir: Path,
    allow_network: bool,
) -> list[dict[str, Any]]:
    """
    (prev_date, new_date] aralığındaki her iş günü için açık pozisyonların gerçek Open/High/Low barlarını
    kontrol eder. Open<=SL -> Open'dan, Low<=SL -> SL'den STOP_LOSS; Open>=TP -> Open'dan, High>=TP -> TP'den
    TAKE_PROFIT satışı yapar (1.50$ komisyonlu, standart muhasebe motoruyla).
    """
    triggers: list[dict[str, Any]] = []
    for pos in state["open_positions"]:
        res = check_sl_tp_in_window(
            pos["ticker"],
            stop_loss=pos.get("stop_loss"),
            take_profit=pos.get("take_profit"),
            start_date_exclusive=prev_date,
            end_date_inclusive=new_date,
            cache_dir=cache_dir,
            allow_network=allow_network,
        )
        if res["triggered"]:
            triggers.append({
                "ticker": pos["ticker"],
                "type": res["trigger_type"],
                "date": res["trigger_date"],
                "price": res["execution_price"],
            })

    triggers.sort(key=lambda t: (t["date"], t["ticker"]))
    executed: list[dict[str, Any]] = []
    for trg in triggers:
        label = "Stop-Loss" if trg["type"] == "STOP_LOSS" else "Take-Profit"
        decisions_data = {
            "decisions_date": trg["date"],
            "circuit_breaker_acknowledged": "TRADING_ALLOWED",
            "decisions": [{
                "ticker": trg["ticker"],
                "action": "SELL",
                "price": trg["price"],
                "shares": 0,
                "reason": f"OTOMATİK {trg['type']}: {label} seviyesi {trg['date']} seansında tetiklendi (Cevap Anahtarı).",
            }],
        }
        before = len(state["trade_history"])
        _run_engine(state, decisions_data)
        if len(state["trade_history"]) > before:
            state["trade_history"][-1]["exit_reason"] = trg["type"]
            executed.append(trg)
    return executed


def prepare_step(
    state_file: Path = BACKTEST_STATE_FILE,
    briefing_file: Path = BACKTEST_BRIEFING_FILE,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
) -> int:
    from src import prepare_daily_batch

    state = load_json(state_file)
    if state["status"] == STATUS_COMPLETED:
        print("[*] Simülasyon zaten TAMAMLANDI.")
        return 0
    if state["status"] == STATUS_AWAITING:
        print(
            f"[!] Durum AWAITING_DECISIONS: {state['current_sim_date']} için brifing hazır. "
            "Önce kararları yazıp --execute çalıştırın."
        )
        return 1

    days = _trading_days(cache_dir, allow_network)
    prev_date = state["current_sim_date"]
    new_date = next_sim_date(state, days)
    if new_date is None:
        state["status"] = STATUS_COMPLETED
        save_json(state_file, state)
        print("[✓] İlerlenecek iş günü kalmadı: simülasyon TAMAMLANDI.")
        return 0

    print(f"[*] Simülasyon ilerliyor: {prev_date} -> {new_date}")

    # b) Ara gün SL/TP denetimi
    interim = apply_interim_exits(state, prev_date, new_date, cache_dir, allow_network)
    for trg in interim:
        print(f"    [AUTO {trg['type']}] {trg['ticker']} @ ${trg['price']:.2f} ({trg['date']})")

    # Pozisyonları yeni günün kapanışıyla değerle (brifing doğru equity / %20 tavanı görsün)
    mark_to_market(state, new_date, cache_dir, allow_network)

    # c) Zaman Kilidiyle brifing (prepare_daily_batch ile aynı şema için geçici adaptör state)
    adapter_path = DATA_DIR / "backtest_state_adapter.tmp.json"
    adapter = {
        "portfolio_summary": {
            "cash_usd": state["cash_usd"],
            "total_equity_usd": state["total_equity_usd"],
            "total_fees_paid_usd": state["total_fees_paid_usd"],
        },
        "open_positions": state["open_positions"],
        "watchlist": state["watchlist"],
        "trade_history": state["trade_history"],
    }
    save_json(adapter_path, adapter)
    try:
        rc = prepare_daily_batch.main(
            state_file=adapter_path,
            universe_file=UNIVERSE_FILE,
            briefing_file=briefing_file,
            as_of_date=new_date,
            use_cache=True,
            cache_dir=cache_dir,
            allow_network=allow_network,
            random_seed=int(new_date.replace("-", "")),
        )
        if rc != 0:
            print("[!] Brifing üretimi başarısız; kasa değiştirilmedi.")
            return rc
        state["watchlist"] = load_json(adapter_path).get("watchlist", [])
    finally:
        if adapter_path.exists():
            adapter_path.unlink()

    briefing = load_json(briefing_file)
    if not briefing.get("candidates"):
        print(
            "[!] Brifingde hiç aday yok (önbellekte veri eksik olabilir). Kasa değiştirilmedi. "
            "Önce `python src/backtest_data.py --all-universe` ile önbelleği doldurun veya --offline'sız çalıştırın."
        )
        return 1
    briefing["backtest"] = {
        "mode": True,
        "current_sim_date": new_date,
        "previous_sim_date": prev_date,
        "step_days": state["step_days"],
        "interim_exits": interim,
        "decisions_date_required": new_date,
    }
    save_json(briefing_file, briefing)

    state["current_sim_date"] = new_date
    state["status"] = STATUS_AWAITING
    save_json(state_file, state)
    print(f"[✓] {new_date} brifingi hazır ({briefing_file.name}). Durum: {STATUS_AWAITING}")
    return 0


# ---------------------------------------------------------------------------
# Mod: --execute
# ---------------------------------------------------------------------------
def execute_step(
    state_file: Path = BACKTEST_STATE_FILE,
    decisions_file: Path = BACKTEST_DECISIONS_FILE,
    report_file: Path = BACKTEST_REPORT_FILE,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
) -> int:
    state = load_json(state_file)
    if state["status"] != STATUS_AWAITING:
        print(f"[!] Durum {state['status']}: --execute yalnızca AWAITING_DECISIONS durumunda çalışır (önce --prepare).")
        return 1
    if not decisions_file.exists():
        print(f"[!] {decisions_file} bulunamadı. Önce komite kararlarını yazın.")
        return 1

    sim_date = state["current_sim_date"]
    decisions_data = load_json(decisions_file)
    decisions_date = decisions_data.get("decisions_date")
    if decisions_date is None:
        decisions_data["decisions_date"] = sim_date
    elif str(decisions_date)[:10] != sim_date:
        print(f"[!] Karar tarihi ({decisions_date}) simülasyon tarihiyle ({sim_date}) uyuşmuyor; eski karar dosyası olabilir.")
        return 1

    _run_engine(state, decisions_data)
    mark_to_market(state, sim_date, cache_dir, allow_network)

    state["equity_curve"].append({
        "date": sim_date,
        "portfolio_value_usd": state["total_equity_usd"],
        "spy_value_usd": spy_benchmark_value(state, sim_date, cache_dir, allow_network),
        "cash_usd": state["cash_usd"],
    })

    days = _trading_days(cache_dir, allow_network)
    state["status"] = STATUS_COMPLETED if next_sim_date(state, days) is None else STATUS_READY

    save_json(state_file, state)
    save_text_atomic(report_file, generate_report(state))
    print(f"\n[✓] {sim_date} adımı işlendi. Durum: {state['status']} | Varlık: {_usd(state['total_equity_usd'])}")
    print(f"[✓] Karne güncellendi: {report_file}")
    return 0


# ---------------------------------------------------------------------------
# Metrikler ve Karne
# ---------------------------------------------------------------------------
def compute_metrics(state: dict[str, Any]) -> dict[str, Any]:
    equity = float(state["total_equity_usd"])
    net_pnl = round(equity - INITIAL_CASH, 2)
    net_pct = net_pnl / INITIAL_CASH * 100

    curve = state.get("equity_curve", [])
    spy_value = float(curve[-1]["spy_value_usd"]) if curve else INITIAL_CASH
    spy_pct = (spy_value / INITIAL_CASH - 1) * 100

    peak = INITIAL_CASH
    max_dd = 0.0
    for val in [INITIAL_CASH] + [float(c["portfolio_value_usd"]) for c in curve]:
        peak = max(peak, val)
        if peak > 0:
            max_dd = max(max_dd, (peak - val) / peak * 100)

    sells = [t for t in state.get("trade_history", []) if t.get("action") == "SELL"]
    wins = [t for t in sells if float(t.get("pnl_usd", 0.0)) > 0]
    gross_win = sum(float(t["pnl_usd"]) for t in wins)
    gross_loss = abs(sum(float(t["pnl_usd"]) for t in sells if float(t.get("pnl_usd", 0.0)) < 0))
    if gross_loss > 0:
        profit_factor = f"{gross_win / gross_loss:.2f}"
    else:
        profit_factor = "∞" if gross_win > 0 else "N/A"

    start = date.fromisoformat(state["start_date"])
    end = date.fromisoformat(state["end_date"])
    cur = date.fromisoformat(state["current_sim_date"])
    total_days = max(1, (end - start).days)
    completion = 100.0 if state["status"] == STATUS_COMPLETED else min(100.0, max(0.0, (cur - start).days / total_days * 100))

    return {
        "equity": equity,
        "net_pnl": net_pnl,
        "net_pct": net_pct,
        "spy_value": spy_value,
        "spy_pct": spy_pct,
        "alpha_pct": net_pct - spy_pct,
        "max_drawdown_pct": max_dd,
        "win_rate_pct": (len(wins) / len(sells) * 100) if sells else 0.0,
        "closed_trades": len(sells),
        "profit_factor": profit_factor,
        "completion_pct": completion,
    }


def generate_report(state: dict[str, Any]) -> str:
    m = compute_metrics(state)
    cell = sanitize_table_cell
    lines: list[str] = [
        "# 📊 BACKTEST SİMÜLASYON KARNESİ",
        "",
        f"> Üretim zamanı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Durum: **{state['status']}**",
        "",
        "## ⏱️ İlerleme",
        "",
        f"- **Başlangıç Tarihi:** {state['start_date']}",
        f"- **Bitiş Tarihi:** {state['end_date']}",
        f"- **Güncel Simülasyon Tarihi:** {state['current_sim_date']}",
        f"- **Adım Aralığı:** {state['step_days']} gün",
        f"- **Tamamlanma:** %{m['completion_pct']:.1f}",
        "",
        "## 💰 Kasa Özeti",
        "",
        "| Metrik | Değer |",
        "|:---|---:|",
        f"| Başlangıç Sermayesi | {_usd(INITIAL_CASH)} |",
        f"| Güncel Toplam Varlık | {_usd(m['equity'])} |",
        f"| Nakit | {_usd(float(state['cash_usd']))} |",
        f"| Net Kâr/Zarar | {_signed_usd(m['net_pnl'])} ({_signed_pct(m['net_pct'])}) |",
        f"| SPY Buy & Hold ({_usd(INITIAL_CASH)}) | {_usd(m['spy_value'])} ({_signed_pct(m['spy_pct'])}) |",
        f"| Alpha (Strateji - SPY) | {_signed_pct(m['alpha_pct'])} |",
        f"| Max Drawdown (adım bazlı) | -%{m['max_drawdown_pct']:.2f} |",
        f"| Win Rate ({m['closed_trades']} kapanan satış) | %{m['win_rate_pct']:.1f} |",
        f"| Profit Factor | {m['profit_factor']} |",
        f"| Ödenen Toplam Komisyon | {_usd(float(state['total_fees_paid_usd']))} |",
        "",
        "## 📂 Açık Pozisyonlar",
        "",
    ]

    positions = state.get("open_positions", [])
    if positions:
        lines += [
            "| Hisse | Adet | Ort. Alış | Güncel | Piyasa Değeri | Gerçekleşmemiş K/Z | Stop-Loss | Take-Profit | Alış Tarihi |",
            "|:---|---:|---:|---:|---:|---:|---:|---:|:---|",
        ]
        for p in positions:
            shares = float(p["shares"])
            cur_px = float(p["current_price"])
            avg = float(p["avg_buy_price"])
            unreal = round(shares * cur_px - shares * avg - float(p.get("fees_paid_usd", FEE_PER_TRADE)), 2)
            lines.append(
                f"| {cell(p['ticker'])} | {shares:.2f} | {_usd(avg)} | {_usd(cur_px)} | "
                f"{_usd(round(shares * cur_px, 2))} | {_signed_usd(unreal)} | "
                f"{_usd(float(p.get('stop_loss', 0.0)))} | {_usd(float(p.get('take_profit', 0.0)))} | "
                f"{cell(p.get('buy_date', '-'))} |"
            )
    else:
        lines.append("_Açık pozisyon yok._")

    lines += ["", "## 👀 Watchlist", ""]
    watchlist = state.get("watchlist", [])
    if watchlist:
        lines += [
            "| Hisse | Hedef Giriş | Stop Planı | Eklenme | Son Geçerlilik | Gerekçe |",
            "|:---|---:|---:|:---|:---|:---|",
        ]
        for w in watchlist:
            lines.append(
                f"| {cell(w['ticker'])} | {_usd(float(w.get('target_entry_price', 0.0)))} | "
                f"{_usd(float(w.get('stop_loss_plan', 0.0)))} | {cell(w.get('added_date', '-'))} | "
                f"{cell(w.get('expires_date', '-'))} | {cell(w.get('reason', ''))} |"
            )
    else:
        lines.append("_İzleme listesi boş._")

    lines += ["", "## 📜 İşlem Geçmişi", ""]
    trades = state.get("trade_history", [])
    if trades:
        lines += [
            "| Tarih | Hisse | İşlem | Adet | Fiyat | Komisyon | Net K/Z | Gerekçe |",
            "|:---|:---|:---|---:|---:|---:|---:|:---|",
        ]
        for t in trades:
            action = t["action"] + (f" ({t['exit_reason']})" if t.get("exit_reason") else "")
            pnl = _signed_usd(float(t.get("pnl_usd", 0.0))) if t["action"] == "SELL" else "-"
            lines.append(
                f"| {cell(t['date'])} | {cell(t['ticker'])} | {cell(action)} | {float(t['shares']):.2f} | "
                f"{_usd(float(t['price']))} | {_usd(float(t.get('fee_usd', FEE_PER_TRADE)))} | {pnl} | "
                f"{cell(t.get('committee_summary', ''))} |"
            )
    else:
        lines.append("_Henüz işlem yok._")

    lines += ["", "## 📈 Equity Eğrisi (Son 15 Adım)", ""]
    curve = state.get("equity_curve", [])
    if curve:
        lines += ["| Tarih | Portföy | SPY (Buy & Hold) | Fark |", "|:---|---:|---:|---:|"]
        for c in curve[-15:]:
            diff = round(float(c["portfolio_value_usd"]) - float(c["spy_value_usd"]), 2)
            lines.append(
                f"| {c['date']} | {_usd(float(c['portfolio_value_usd']))} | {_usd(float(c['spy_value_usd']))} | {_signed_usd(diff)} |"
            )
    else:
        lines.append("_Henüz tamamlanmış adım yok._")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mod: --status
# ---------------------------------------------------------------------------
def print_status(state_file: Path = BACKTEST_STATE_FILE) -> int:
    if not state_file.exists():
        print(f"[!] {state_file} yok. Önce --init çalıştırın.")
        return 1
    state = load_json(state_file)
    m = compute_metrics(state)
    print("=" * 60)
    print("BACKTEST DURUMU")
    print("=" * 60)
    print(f"Durum              : {state['status']}")
    print(f"Simülasyon Tarihi  : {state['current_sim_date']} (Aralık: {state['start_date']} -> {state['end_date']}, adım: {state['step_days']} gün)")
    print(f"Tamamlanma         : %{m['completion_pct']:.1f}")
    print(f"Nakit              : {_usd(float(state['cash_usd']))}")
    print(f"Toplam Varlık      : {_usd(m['equity'])}  ({_signed_usd(m['net_pnl'])} / {_signed_pct(m['net_pct'])})")
    print(f"SPY Buy & Hold     : {_usd(m['spy_value'])}  ({_signed_pct(m['spy_pct'])})  | Alpha: {_signed_pct(m['alpha_pct'])}")
    print(f"Komisyon           : {_usd(float(state['total_fees_paid_usd']))}")
    print(f"Açık Pozisyonlar   : {len(state['open_positions'])}")
    for p in state["open_positions"]:
        print(
            f"    - {p['ticker']}: {float(p['shares']):.2f} adet | Ort. ${float(p['avg_buy_price']):.2f} | "
            f"Güncel ${float(p['current_price']):.2f} | SL ${float(p['stop_loss']):.2f} | TP ${float(p['take_profit']):.2f}"
        )
    print(f"Watchlist          : {len(state['watchlist'])} | Kapanan işlem: {m['closed_trades']}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli() -> int:
    parser = argparse.ArgumentParser(description="Adım Adım Backtest Yürütücüsü (izole, sıfır canlı temas)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--init", action="store_true", help="İzole backtest kasasını kur")
    mode.add_argument("--prepare", action="store_true", help="Sonraki adıma ilerle ve brifing üret")
    mode.add_argument("--execute", action="store_true", help="backtest_decisions.json kararlarını işle")
    mode.add_argument("--status", action="store_true", help="Simülasyon özetini göster")
    parser.add_argument("--start-date", default=DEFAULT_START)
    parser.add_argument("--end-date", default=DEFAULT_END)
    parser.add_argument("--step-days", type=int, default=DEFAULT_STEP_DAYS)
    parser.add_argument("--force", action="store_true", help="--init: mevcut kasayı sıfırla")
    parser.add_argument("--offline", action="store_true", help="Ağ erişimini kapat, yalnızca önbellek")
    args = parser.parse_args()
    allow_network = not args.offline

    try:
        if args.init:
            state = init_state(
                args.start_date, args.end_date, args.step_days, allow_network=allow_network, force=args.force
            )
            print(f"[✓] {BACKTEST_STATE_FILE} kuruldu: {_usd(state['cash_usd'])} | {state['start_date']} -> {state['end_date']} | adım {state['step_days']} gün")
            print(f"    SPY başlangıç ({state['spy_start_date']}): ${state['spy_start_price']:.2f}")
            return 0
        if args.prepare:
            return prepare_step(allow_network=allow_network)
        if args.execute:
            return execute_step(allow_network=allow_network)
        return print_status()
    except (ValueError, FileExistsError, FileNotFoundError, RuntimeError) as exc:
        print(f"[!] Hata: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(_cli())

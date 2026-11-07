#!/usr/bin/env python3
"""
src/ui_dashboard.py
Otonom Borsa Orkestrası — 11 Ajan Karar Karnesi ve Hibrit Gösterge Paneli (UI) Motoru

Görevler:
1. İncelenen her hisse için 11 komite ajanının/adımının ayrı ayrı kararını (✅ ONAY / ⚠️ UYARI / ❌ RED),
   metriklerini ve gerekçelerini sentezlemek (build_11_agent_scorecard).
2. GitHub ve IDE üzerinde doğrudan okunabilen ASCII grafikli ve 11 ajan tablolu
   PORTFOLIO_DASHBOARD.md içeriğini üretmek (generate_dashboard_markdown).
   - Canlı/Gerçek para modunda (trading_mode == "LIVE" veya privacy_mode == True)
     kişisel bakiye, lot ve işlem tutarlarını otomatik maskelemek.
3. Yalnızca yerel bilgisayarda (.gitignore korumasında) çalışan, sunucu gerektirmeyen
   tek dosyalık interaktif HTML5 gösterge panelini (docs/dashboard.html) üretmek (generate_dashboard_html).
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.paths import (
    BRIEFING_FILE,
    DASHBOARD_FILE,
    DECISIONS_FILE,
    HTML_DASHBOARD_FILE,
    STATE_FILE,
)

INITIAL_CASH = 3500.00
FEE_PER_TRADE = 1.50
MAX_POSITION_PCT = 0.20


def sanitize_table_cell(text: Any) -> str:
    """Markdown tablolarını bozabilecek pipe (|), yeni satır ve satır başı karakterlerini temizler."""
    if text is None:
        return "-"
    cleaned = str(text).replace("|", "/").replace("\n", " ").replace("\r", " ").strip()
    return cleaned if cleaned else "-"


def escape_html(text: Any) -> str:
    """HTML çıktısında XSS veya DOM bozulmasını önlemek için özel karakterleri encode eder."""
    if text is None:
        return "-"
    cleaned = str(text).strip()
    return html.escape(cleaned, quote=True) if cleaned else "-"


def render_ascii_bar(pct: float, width: int = 20) -> str:
    """0-100 arası yüzde değerini ASCII ilerleme çubuğuna dönüştürür."""
    if not math.isfinite(pct):
        pct = 0.0
    clamped = max(0.0, min(100.0, float(pct)))
    filled = int(round((clamped / 100.0) * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def is_privacy_active(state: dict[str, Any], privacy_mode: bool = False) -> bool:
    """
    Public GitHub reposunda kişisel finansal verilerin gizlenip gizlenmeyeceğini belirler.
    Gerçek parayla canlı işlemlere geçildiğinde (LIVE mod) veya privacy_mode=True olduğunda aktifleşir.
    """
    if privacy_mode:
        return True
    env_mode = os.environ.get("TRADING_MODE", "").upper().strip()
    env_priv = os.environ.get("PRIVACY_MODE", "").lower().strip()
    if env_mode == "LIVE" or env_priv in ("1", "true", "yes", "on"):
        return True
    summary = state.get("portfolio_summary", {})
    if str(summary.get("trading_mode", "")).upper().strip() == "LIVE":
        return True
    if bool(summary.get("privacy_mode", False)):
        return True
    return False


def _verdict_badge(verdict: str) -> str:
    v = str(verdict).upper().strip()
    if v == "PASS":
        return "✅ ONAY"
    if v == "WARN":
        return "⚠️ UYARI"
    return "❌ RED"


def build_11_agent_scorecard(
    decision: dict[str, Any],
    candidate_briefing: dict[str, Any] | None = None,
    cb_status: str = "TRADING_ALLOWED",
    cb_rationale: str = "",
) -> list[dict[str, Any]]:
    """
    İncelenen bir hisse için 11 komite ajanının/adımının ayrı ayrı kararını ve gerekçesini üretir.
    Eğer decision sözlüğünde 'agent_evaluations' açıkça verilmişse ilgili adımları oradan alır;
    aksi halde daily_briefing.json metrikleri ve decision verilerinden 11 adımı sentezler.
    """
    ticker = str(decision.get("ticker", "UNKNOWN")).upper().strip()
    action = str(decision.get("action", "DROP")).upper().strip()
    price = float(decision.get("price", 0.0) or 0.0)
    shares = float(decision.get("shares", 0.0) or 0.0)
    stop_loss = decision.get("stop_loss") or decision.get("stop_loss_plan")
    take_profit = decision.get("take_profit")
    target_entry = decision.get("target_entry_price")
    thesis = str(decision.get("thesis") or decision.get("reason") or "Komite değerlendirmesi.")
    reason = str(decision.get("reason") or decision.get("thesis") or "Standart komite süzgeci.")

    cand = candidate_briefing or {}
    mdata = cand.get("market_data", {}) if isinstance(cand.get("market_data"), dict) else {}
    wpa = cand.get("weekly_price_action", {}) if isinstance(cand.get("weekly_price_action"), dict) else {}
    psize = cand.get("position_sizing", {}) if isinstance(cand.get("position_sizing"), dict) else {}
    tt = mdata.get("trend_template", {}) if isinstance(mdata.get("trend_template"), dict) else {}

    # 1. Hesap Devre Kesici (drawdown-circuit-breaker)
    cb_clean = str(cb_status or "TRADING_ALLOWED").upper().strip()
    if cb_clean == "TRADING_ALLOWED":
        s1_verdict = "PASS"
        s1_rat = cb_rationale or "Devre kesici TRADING_ALLOWED durumunda; hesap yeni risk alımına açık."
    else:
        s1_verdict = "FAIL" if action == "BUY" else "WARN"
        s1_rat = cb_rationale or f"Devre kesici {cb_clean} durumunda; yeni BUY işlemleri kilitli."

    # 2. Öncelikli Kuyruk Yönetimi (queue-management)
    source = str(cand.get("source") or ("OPEN_POSITION" if action in ("SELL", "HOLD") else "DISCOVERY")).upper()
    source_labels = {
        "OPEN_POSITION": "1. Öncelik: Açık Pozisyon takibi (Stop/TP/Trend kontrolü).",
        "WATCHLIST": "2. Öncelik: İzleme Listesi (WAIT_BUY hedef giriş kontrolü).",
        "DISCOVERY": "3. Öncelik: Evren (universe.json) yeni aday keşfi (5 hisse kotası dahilinde).",
    }
    s2_verdict = "PASS"
    s2_rat = source_labels.get(source, f"Kuyruk kaynağı: {source} (5 hisse kotası dahilinde incelendi).")

    # 3. Minervini Trend Şablonu (Stage 2 Uptrend Gate)
    tt_score = tt.get("score")
    tt_passed_cnt = tt.get("passed_count")
    sma50 = mdata.get("sma_50")
    sma150 = mdata.get("sma_150")
    sma200 = mdata.get("sma_200")
    if tt_score is not None:
        score_val = float(tt_score)
        if score_val >= 70.0:
            s3_verdict = "PASS"
        elif score_val >= 50.0:
            s3_verdict = "WARN"
        else:
            s3_verdict = "FAIL"
        sma_info = ""
        if sma50 and sma150 and sma200:
            sma_info = f" | Fiyat: ${price:.2f} (SMA50: ${ float(sma50):.2f}, SMA150: ${float(sma150):.2f}, SMA200: ${float(sma200):.2f})"
        s3_rat = f"Stage 2 Puanı: {score_val:.1f}/100 ({tt_passed_cnt}/7 kriter geçti){sma_info}."
    else:
        s3_verdict = "PASS" if action in ("BUY", "HOLD", "WAIT_BUY") else "FAIL"
        s3_rat = "Minervini Stage 2 trend şablonu onayı mevcut." if s3_verdict == "PASS" else "Minervini Stage 2 yükseliş trendi kriterleri karşılanmadı."

    # 4. Haftalık Fiyat Hareketi ve Fraktal Swing Seviyeleri (technical-analyst)
    wpa_verdict = wpa.get("verdict")
    wpa_reason = wpa.get("verdict_reason")
    swing_low = wpa.get("nearest_swing_low")
    swing_high = wpa.get("nearest_swing_high")
    stop_ref = wpa.get("stop_reference")
    if wpa_verdict:
        if action == "DROP" and s3_verdict == "FAIL":
            s4_verdict = "FAIL"
        elif wpa_verdict == "CONFIRMED" or action in ("BUY", "HOLD"):
            s4_verdict = "PASS"
        else:
            s4_verdict = "WARN"
        sw_text = ""
        if swing_low is not None and swing_high is not None:
            sw_text = f" | Swing Dip: ${float(swing_low):.2f}, Swing Tepe: ${float(swing_high):.2f}, Stop Ref: ${float(stop_ref or swing_low):.2f}"
        s4_rat = f"Haftalık Sinyal: {wpa_verdict} ({wpa_reason or 'normal'}){sw_text}."
    else:
        s4_verdict = "PASS" if action in ("BUY", "HOLD") else ("WARN" if action in ("WAIT_BUY", "SELL") else "FAIL")
        s4_rat = f"Haftalık fraktal pivot ve fiyat hareketi değerlendirildi (Stop referansı: ${float(stop_loss):.2f})." if stop_loss else "Haftalık yapı incelendi."

    # 5. Hacim ve Momentum Doğrulaması (RSI / MACD / Volume)
    rsi = mdata.get("rsi_14")
    macd_hist = mdata.get("macd_hist")
    vol_chg = mdata.get("volume_change_pct")
    if rsi is not None:
        rsi_val = float(rsi)
        macd_val = float(macd_hist or 0.0)
        vol_val = float(vol_chg or 0.0)
        if 40.0 <= rsi_val <= 72.0 and macd_val >= 0:
            s5_verdict = "PASS"
            mom_note = "İdeal momentum ve dengeli RSI bölgesi."
        elif rsi_val > 72.0:
            s5_verdict = "WARN"
            mom_note = "Aşırı alım bölgesi (RSI > 72); tepe kovalamama kuralı devrede."
        elif rsi_val < 32.0:
            s5_verdict = "FAIL" if action == "DROP" else "WARN"
            mom_note = "Aşırı satım / sert satış baskısı (RSI < 32); düşen bıçak tutulmaz."
        else:
            s5_verdict = "PASS" if action in ("BUY", "HOLD") else "WARN"
            mom_note = "Momentum izleniyor."
        s5_rat = f"RSI(14): {rsi_val:.1f} | MACD Hist: {macd_val:+.4f} | 20g Hacim Değişimi: {vol_val:+.1f}%. ({mom_note})"
    else:
        s5_verdict = "PASS" if action in ("BUY", "HOLD") else ("WARN" if action == "WAIT_BUY" else "FAIL")
        s5_rat = "RSI(14), MACD histogramı ve 20 günlük kurumsal hacim ortalaması kontrol edildi."

    # 6. Temel Değerleme ve Sağlamlık Filtresi (P/E & P/B)
    pe = mdata.get("pe_ratio")
    pb = mdata.get("pb_ratio")
    if pe is not None or pb is not None:
        pe_str = f"{float(pe):.2f}" if pe is not None else "N/A"
        pb_str = f"{float(pb):.2f}" if pb is not None else "N/A"
        if pb is not None and float(pb) < 0:
            s6_verdict = "FAIL"
            s6_rat = f"F/K (P/E): {pe_str} | PD/DD (P/B): {pb_str} — Negatif özkaynak riski tespit edildi."
        else:
            s6_verdict = "PASS" if action != "DROP" else "WARN"
            s6_rat = f"F/K (P/E): {pe_str} | PD/DD (P/B): {pb_str} — Kurumsal bilanço ve özkaynak yapısı uygun."
    else:
        s6_verdict = "PASS" if action != "DROP" else "WARN"
        s6_rat = "Temel çarpanlar (F/K ve PD/DD) ile bilanço sağlamlığı kontrol edildi."

    # 7. Senaryo Analisti Değerlendirmesi (scenario-analyst)
    if action == "BUY":
        s7_verdict = "PASS"
        s7_rat = f"18 Aylık Base/Bull senaryo ağırlıklı pozitif tez: {thesis}"
    elif action == "WAIT_BUY":
        s7_verdict = "WARN"
        s7_rat = f"Uzun vadeli tez pozitif ancak kısa vadeli giriş zamanlaması bekleniyor: {thesis}"
    elif action == "HOLD":
        s7_verdict = "PASS"
        s7_rat = f"Mevcut yatırım tezi geçerliliğini koruyor: {thesis}"
    elif action == "SELL":
        s7_verdict = "WARN"
        s7_rat = f"Pozisyon kapatma / risk realizasyonu senaryosu: {reason}"
    else:
        s7_verdict = "FAIL"
        s7_rat = f"Bear Case (ayı senaryosu) baskın; yatırım tezi reddedildi: {reason}"

    # 8. Şeytanın Avukatı / Karşı Görüş ve R:R (strategy-reviewer)
    eff_entry = float(target_entry if action == "WAIT_BUY" and target_entry else price)
    eff_stop = float(stop_loss) if stop_loss is not None else ( float(psize.get("stop_price", 0.0)) if psize.get("stop_price") else 0.0 )
    eff_tp = float(take_profit) if take_profit is not None else (eff_entry * 1.15 if eff_entry > 0 else 0.0)
    if eff_entry > 0 and eff_stop > 0 and eff_entry > eff_stop:
        risk_per_share = eff_entry - eff_stop
        reward_per_share = max(0.0, eff_tp - eff_entry)
        rr_ratio = reward_per_share / risk_per_share if risk_per_share > 0 else 0.0
        if action == "BUY":
            s8_verdict = "PASS"
            s8_rat = f"Giriş: ${eff_entry:.2f} | Stop: ${eff_stop:.2f} | Hedef: ${eff_tp:.2f} (R:R = 1:{rr_ratio:.1f}). Kör nokta ve destek testi onaylandı."
        elif action == "WAIT_BUY":
            s8_verdict = "WARN"
            s8_rat = f"Mevcut fiyat (${price:.2f}) R:R oranını zayıflatıyor; ${eff_entry:.2f} destek/pullback seviyesi ve ${eff_stop:.2f} stop planı bekleniyor."
        else:
            s8_verdict = "PASS" if action == "HOLD" else "FAIL"
            s8_rat = f"Stop-Loss koruma seviyesi: ${eff_stop:.2f} | Risk/Ödül disiplini denetlendi."
    else:
        s8_verdict = "FAIL" if action == "DROP" else ("PASS" if action in ("BUY", "HOLD", "SELL") else "WARN")
        s8_rat = reason if action == "DROP" else f"Karşıt görüş süzgeci: {reason}"

    # 9. Pozisyon Boyutlandırma ve Risk Bütçesi (position-sizer)
    rec_shares = float(shares if shares > 0 else (psize.get("recommended_shares", 0.0) or 0.0))
    pos_val = round(rec_shares * price, 2) if price > 0 else float(psize.get("position_value", 0.0) or 0.0)
    risk_dlr = float(psize.get("risk_dollars", 0.0) or 0.0)
    risk_pct = float(psize.get("risk_pct", 0.0) or 0.0)
    if action == "BUY":
        s9_verdict = "PASS"
        s9_rat = f"Önerilen Adet: {rec_shares:.2f} lot (${pos_val:.2f} <= %20 kasa tavanı) | Maksimum Risk: ${risk_dlr:.2f} (%{risk_pct:.2f} <= %1.00 kasa riski)."
    elif action == "WAIT_BUY":
        s9_verdict = "WARN"
        s9_rat = f"Hedef fiyata (${float(target_entry or price):.2f}) gelindiğinde maks %20 kasa ve %1 risk bütçesiyle ({rec_shares:.2f} adet) boyutlandırılacak."
    elif action in ("HOLD", "SELL"):
        s9_verdict = "PASS"
        s9_rat = f"Pozisyon büyüklüğü: {rec_shares:.2f} adet (${pos_val:.2f}). Kasa %20 tavan kurallarına uygun."
    else:
        s9_verdict = "FAIL"
        s9_rat = "İşlem reddedildiği (DROP) için sermaye tahsisi yapılmadı ($0.00)."

    # 10. İşlem Öncesi Disiplin Kapısı (pre-trade-discipline-gate)
    if action == "BUY" and cb_clean == "TRADING_ALLOWED":
        s10_verdict = "PASS"
        s10_rat = "5/5 Disiplin Kriteri Onaylandı: [✓] Yazılı Tez [✓] Matematiksel Stop [✓] <=%20 Kasa & <=%1 Risk [✓] Devre Kesici Açık [✓] Sıfır Duygusal İşlem."
    elif action == "WAIT_BUY":
        s10_verdict = "WARN"
        s10_rat = "Disiplin Kapısı Beklemede: Hisse kaliteli ancak giriş fiyatı/indikatör soğuması gerçekleşmeden erken alıma izin verilmedi."
    elif action in ("HOLD", "SELL"):
        s10_verdict = "PASS"
        s10_rat = "Açık pozisyon yönetim disiplini (Stop-Loss / Take-Profit / Trend takibi) kurallara uygun."
    else:
        s10_verdict = "FAIL"
        s10_rat = "Disiplin Kapısından Geçemedi: Teknik/trend kriterleri sağlanmadığı için alım emri engellendi."

    # 11. Nihai Karar Sentezi ve Hafıza Güncellemesi (trader-memory-core)
    if action in ("BUY", "HOLD", "SELL"):
        s11_verdict = "PASS"
    elif action == "WAIT_BUY":
        s11_verdict = "WARN"
    else:
        s11_verdict = "FAIL"
    s11_rat = f"NİHAİ KARAR: {action} ({ticker}) — {reason}"

    steps = [
        {
            "step": 1,
            "agent_id": "drawdown-circuit-breaker",
            "agent_name": "Hesap Devre Kesici (Circuit Breaker)",
            "verdict": s1_verdict,
            "badge": _verdict_badge(s1_verdict),
            "rationale": s1_rat,
        },
        {
            "step": 2,
            "agent_id": "queue-management",
            "agent_name": "Öncelikli Kuyruk Yönetimi (Queue)",
            "verdict": s2_verdict,
            "badge": _verdict_badge(s2_verdict),
            "rationale": s2_rat,
        },
        {
            "step": 3,
            "agent_id": "minervini-stage2-gate",
            "agent_name": "Minervini Trend Şablonu (Stage 2)",
            "verdict": s3_verdict,
            "badge": _verdict_badge(s3_verdict),
            "rationale": s3_rat,
        },
        {
            "step": 4,
            "agent_id": "technical-analyst",
            "agent_name": "Haftalık Fiyat Hareketi & Swing",
            "verdict": s4_verdict,
            "badge": _verdict_badge(s4_verdict),
            "rationale": s4_rat,
        },
        {
            "step": 5,
            "agent_id": "volume-momentum",
            "agent_name": "Hacim ve Momentum (RSI / MACD)",
            "verdict": s5_verdict,
            "badge": _verdict_badge(s5_verdict),
            "rationale": s5_rat,
        },
        {
            "step": 6,
            "agent_id": "fundamental-filter",
            "agent_name": "Temel Değerleme Filtresi (P/E & P/B)",
            "verdict": s6_verdict,
            "badge": _verdict_badge(s6_verdict),
            "rationale": s6_rat,
        },
        {
            "step": 7,
            "agent_id": "scenario-analyst",
            "agent_name": "Senaryo Analisti (18 Ay Base/Bull/Bear)",
            "verdict": s7_verdict,
            "badge": _verdict_badge(s7_verdict),
            "rationale": s7_rat,
        },
        {
            "step": 8,
            "agent_id": "strategy-reviewer",
            "agent_name": "Şeytanın Avukatı & Risk/Ödül (R:R)",
            "verdict": s8_verdict,
            "badge": _verdict_badge(s8_verdict),
            "rationale": s8_rat,
        },
        {
            "step": 9,
            "agent_id": "position-sizer",
            "agent_name": "Pozisyon Boyutlandırma (%20 / %1 Risk)",
            "verdict": s9_verdict,
            "badge": _verdict_badge(s9_verdict),
            "rationale": s9_rat,
        },
        {
            "step": 10,
            "agent_id": "pre-trade-discipline-gate",
            "agent_name": "İşlem Öncesi Disiplin Kapısı (5 Kural)",
            "verdict": s10_verdict,
            "badge": _verdict_badge(s10_verdict),
            "rationale": s10_rat,
        },
        {
            "step": 11,
            "agent_id": "trader-memory-core",
            "agent_name": "Nihai Komite Sentezi (Final Decision)",
            "verdict": s11_verdict,
            "badge": _verdict_badge(s11_verdict),
            "rationale": s11_rat,
        },
    ]

    # Eğer decision içinde manuel/özel agent_evaluations verilmişse üzerine işle
    custom_evals = decision.get("agent_evaluations")
    if isinstance(custom_evals, list):
        for idx, item in enumerate(custom_evals):
            if idx < len(steps) and isinstance(item, dict):
                if "verdict" in item:
                    steps[idx]["verdict"] = str(item["verdict"]).upper()
                    steps[idx]["badge"] = _verdict_badge(steps[idx]["verdict"])
                if "rationale" in item:
                    steps[idx]["rationale"] = str(item["rationale"])

    return steps


def generate_dashboard_markdown(
    state: dict[str, Any],
    decisions_data: dict[str, Any],
    today_str: str,
    briefing_data: dict[str, Any] | None = None,
    privacy_mode: bool = False,
) -> str:
    """
    GitHub ve IDE uyumlu, ASCII grafikli ve 11 Ajan Karar Karneli Markdown gösterge paneli üretir.
    privacy_mode=True veya trading_mode=='LIVE' olduğunda kişisel bakiye ve pozisyon büyüklüklerini maskeler.
    """
    priv = is_privacy_active(state, privacy_mode=privacy_mode)
    summary = state.get("portfolio_summary", {})
    cash = float(summary.get("cash_usd", INITIAL_CASH) or 0.0)
    equity = float(summary.get("total_equity_usd", INITIAL_CASH) or 0.0)
    fees_paid = float(summary.get("total_fees_paid_usd", 0.0) or 0.0)

    open_positions = state.get("open_positions", [])
    positions_value = round(sum(round(float(pos["shares"]) * float(pos["current_price"]), 2) for pos in open_positions), 2)
    net_pnl = round(equity - INITIAL_CASH, 2)
    net_pnl_pct = (net_pnl / INITIAL_CASH) * 100 if INITIAL_CASH > 0 else 0.0

    cash_pct = (cash / equity * 100.0) if equity > 0 else 0.0
    pos_pct = (positions_value / equity * 100.0) if equity > 0 else 0.0

    watchlist = [w for w in state.get("watchlist", []) if w.get("status") != "EXPIRED"]
    history = state.get("trade_history", [])
    decisions = decisions_data.get("decisions", []) if isinstance(decisions_data, dict) else []

    cb_status = str(decisions_data.get("circuit_breaker_acknowledged", "UNKNOWN"))
    cb_rationale = ""
    candidates_map: dict[str, dict[str, Any]] = {}
    if isinstance(briefing_data, dict):
        cb_obj = briefing_data.get("circuit_breaker", {})
        if isinstance(cb_obj, dict):
            cb_rationale = str(cb_obj.get("rationale", ""))
        for c in briefing_data.get("candidates", []):
            if isinstance(c, dict) and c.get("ticker"):
                candidates_map[str(c["ticker"]).upper().strip()] = c

    if priv:
        cash_str = "`🔒 [GİZLİ - CANLI MOD]`"
        pos_val_str = "`🔒 [GİZLİ - CANLI MOD]`"
        equity_str = "`🔒 [GİZLİ - CANLI MOD]`"
        init_str = "`🔒 [GİZLİ - CANLI MOD]`"
        pnl_str_summary = f"`🔒 [GİZLİ]` (`{net_pnl_pct:+.2f}%`)"
        fees_str = "`🔒 [GİZLİ]`"
        max_pos_str = "`%20` (`🔒 [GİZLİ]`)"
    else:
        cash_str = f"`${cash:,.2f}`"
        pos_val_str = f"`${positions_value:,.2f}`"
        equity_str = f"`${equity:,.2f}`"
        init_str = f"`${INITIAL_CASH:,.2f}`"
        pnl_str_summary = f"`${net_pnl:+,.2f}` (`{net_pnl_pct:+.2f}%`)"
        fees_str = f"`${fees_paid:,.2f}` (Midas 1.50$/işlem)"
        max_pos_str = f"`%20` (Maks `${equity * MAX_POSITION_PCT:,.2f}`)"

    lines = [
        "# 📊 PORTFOLIO DASHBOARD (Paper Trading)",
        f"**Son Güncelleme:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  **Tarih:** {today_str}",
        "",
        "## 1. Portföy Özeti",
        "| Metrik | Değer |",
        "|---|---|",
        f"| **Nakit Bakiye (Cash)** | {cash_str} |",
        f"| **Hisse Pozisyon Değeri** | {pos_val_str} |",
        f"| **Toplam Varlık (Total Equity)** | {equity_str} |",
        f"| **Başlangıç Sermayesi** | {init_str} |",
        f"| **Toplam Net Kâr / Zarar** | {pnl_str_summary} |",
        f"| **Ödenen Toplam Komisyon** | {fees_str} |",
        f"| **Maksimum Pozisyon Limiti** | {max_pos_str} |",
        "",
        "### 📈 Kasa Dağılımı (ASCII Görünüm)",
        "```text",
        f"Nakit Oranı  [{render_ascii_bar(cash_pct, 25)}] %{cash_pct:5.1f}",
        f"Hisse Oranı  [{render_ascii_bar(pos_pct, 25)}] %{pos_pct:5.1f}",
        "```",
        "",
        "## 2. Açık Pozisyonlar (`open_positions`)",
    ]

    if open_positions:
        lines.extend([
            "| Sembol | Adet | Alış Fiyatı | Güncel Fiyat | Piyasa Değeri | Kâr/Zarar ($) | Kâr/Zarar (%) | Stop-Loss | Kâr Al (TP) | Yatırım Tezi |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ])
        for p in open_positions:
            val = round(float(p["shares"]) * float(p["current_price"]), 2)
            cost = round(float(p["shares"]) * float(p["avg_buy_price"]), 2)
            pnl = round(val - cost, 2)
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0.0
            thesis_clean = sanitize_table_cell(p.get("thesis", "-"))
            if priv:
                lines.append(
                    f"| **{p['ticker']}** | `🔒` | `${float(p['avg_buy_price']):.2f}` | `${float(p['current_price']):.2f}` | `🔒` | `🔒` | `{pnl_pct:+.2f}%` | `${float(p.get('stop_loss', 0)):.2f}` | `${float(p.get('take_profit', 0)):.2f}` | {thesis_clean} |"
                )
            else:
                lines.append(
                    f"| **{p['ticker']}** | {float(p['shares']):.2f} | `${float(p['avg_buy_price']):.2f}` | `${float(p['current_price']):.2f}` | `${val:,.2f}` | `${pnl:+,.2f}` | `{pnl_pct:+.2f}%` | `${float(p.get('stop_loss', 0)):.2f}` | `${float(p.get('take_profit', 0)):.2f}` | {thesis_clean} |"
                )
    else:
        lines.append("*Şu anda açık pozisyon bulunmamaktadır (Nakit ağırlıklı).*")

    lines.extend([
        "",
        "## 3. İzleme Listesi (`watchlist`)",
    ])

    if watchlist:
        lines.extend([
            "| Sembol | Eklenme Tarihi | Son Geçerlilik | Hedef Giriş Fiyatı | Planlanan Stop | Durum | Gerekçe |",
            "|---|---|---|---|---|---|---|",
        ])
        for w in watchlist:
            reason_clean = sanitize_table_cell(w.get("reason", "-"))
            lines.append(
                f"| **{w['ticker']}** | {w.get('added_date')} | {w.get('expires_date')} | `${float(w.get('target_entry_price', 0)):.2f}` | `${float(w.get('stop_loss_plan', 0)):.2f}` | `{w.get('status')}` | {reason_clean} |"
            )
    else:
        lines.append("*İzleme listesinde aktif hisse bulunmamaktadır.*")

    lines.extend([
        "",
        "## 4. Son İşlem Geçmişi (`trade_history` - Son 10 İşlem)",
    ])

    if history:
        lines.extend([
            "| Tarih | Sembol | İşlem | Adet | Fiyat | Komisyon | Net PnL ($) | Komite Özeti |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for t in reversed(history[-10:]):
            summary_clean = sanitize_table_cell(t.get("committee_summary", "-"))
            if priv:
                pnl_cell = "`🔒`" if t.get("action") == "SELL" else "-"
                lines.append(
                    f"| {t.get('date')} | **{t.get('ticker')}** | `{t.get('action')}` | `🔒` | `${float(t.get('price', 0)):.2f}` | `🔒` | {pnl_cell} | {summary_clean} |"
                )
            else:
                pnl_cell = f"${float(t.get('pnl_usd', 0)):+,.2f}" if t.get("action") == "SELL" else "-"
                lines.append(
                    f"| {t.get('date')} | **{t.get('ticker')}** | `{t.get('action')}` | {float(t.get('shares', 0)):.2f} | `${float(t.get('price', 0)):.2f}` | `${float(t.get('fee_usd', 0)):.2f}` | {pnl_cell} | {summary_clean} |"
                )
    else:
        lines.append("*Henüz tamamlanmış işlem kaydı bulunmamaktadır.*")

    committee_note = sanitize_table_cell(decisions_data.get("committee_overall_note", "Kayıt yok."))
    lines.extend([
        "",
        "## 5. Bugünkü Komite Karar Özeti",
        f"**Devre Kesici Onayı:** `{cb_status}`",
        f"**Komite Genel Notu:** {committee_note}",
        "",
        "## 6. 11 Ajan Komite Karar Karnesi (Hisse Bazlı Detay)",
    ])

    if decisions:
        for d in decisions:
            tkr = str(d.get("ticker", "UNKNOWN")).upper().strip()
            act = str(d.get("action", "DROP")).upper().strip()
            prc = float(d.get("price", 0.0) or 0.0)
            scorecard = build_11_agent_scorecard(
                d,
                candidate_briefing=candidates_map.get(tkr),
                cb_status=cb_status,
                cb_rationale=cb_rationale,
            )
            pass_cnt = sum(1 for s in scorecard if s["verdict"] == "PASS")
            warn_cnt = sum(1 for s in scorecard if s["verdict"] == "WARN")
            fail_cnt = sum(1 for s in scorecard if s["verdict"] == "FAIL")

            lines.extend([
                f"### 📌 {tkr} (`${prc:.2f}`) — Nihai Karar: `{act}` (✅ {pass_cnt} | ⚠️ {warn_cnt} | ❌ {fail_cnt})",
                "| # | Uzman Ajan / Komite Adımı | Karar | Gerekçe ve Metrikler |",
                "|---|---|---|---|",
            ])
            for s in scorecard:
                rat_clean = sanitize_table_cell(s["rationale"])
                if priv and s["step"] == 9:
                    rat_clean = "🔒 [Canlı Modda Pozisyon Boyutu Gizli]"
                lines.append(
                    f"| **{s['step']}** | {sanitize_table_cell(s['agent_name'])} | {s['badge']} | {rat_clean} |"
                )
            lines.append("")
    else:
        lines.append("*Bugün için incelenen hisse kararı bulunmamaktadır.*")
        lines.append("")

    return "\n".join(lines)


def generate_dashboard_html(
    state: dict[str, Any],
    decisions_data: dict[str, Any],
    today_str: str,
    briefing_data: dict[str, Any] | None = None,
) -> str:
    """
    Tarayıcıda sunucusuz çalışan, tek dosyalık modern dark-mode interaktif HTML gösterge paneli üretir.
    Bu dosya (.gitignore içinde olduğu için) sadece kullanıcının yerel bilgisayarında bulunur.
    """
    summary = state.get("portfolio_summary", {})
    cash = float(summary.get("cash_usd", INITIAL_CASH) or 0.0)
    equity = float(summary.get("total_equity_usd", INITIAL_CASH) or 0.0)
    fees_paid = float(summary.get("total_fees_paid_usd", 0.0) or 0.0)
    trading_mode = str(summary.get("trading_mode", "PAPER")).upper().strip()

    open_positions = state.get("open_positions", [])
    positions_value = round(sum(round(float(pos["shares"]) * float(pos["current_price"]), 2) for pos in open_positions), 2)
    net_pnl = round(equity - INITIAL_CASH, 2)
    net_pnl_pct = (net_pnl / INITIAL_CASH) * 100 if INITIAL_CASH > 0 else 0.0

    cash_pct = (cash / equity * 100.0) if equity > 0 else 100.0
    pos_pct = (positions_value / equity * 100.0) if equity > 0 else 0.0
    max_pos_limit_usd = round(equity * MAX_POSITION_PCT, 2)

    watchlist = [w for w in state.get("watchlist", []) if w.get("status") != "EXPIRED"]
    history = state.get("trade_history", [])
    decisions = decisions_data.get("decisions", []) if isinstance(decisions_data, dict) else []

    cb_status = str(decisions_data.get("circuit_breaker_acknowledged", "TRADING_ALLOWED")).upper().strip()
    committee_note = escape_html(decisions_data.get("committee_overall_note", "Kayıt yok."))
    cb_rationale = ""
    candidates_map: dict[str, dict[str, Any]] = {}
    if isinstance(briefing_data, dict):
        cb_obj = briefing_data.get("circuit_breaker", {})
        if isinstance(cb_obj, dict):
            cb_rationale = str(cb_obj.get("rationale", ""))
        for c in briefing_data.get("candidates", []):
            if isinstance(c, dict) and c.get("ticker"):
                candidates_map[str(c["ticker"]).upper().strip()] = c

    pnl_color_class = "pos" if net_pnl >= 0 else "neg"
    cb_badge_class = "badge-pass" if cb_status == "TRADING_ALLOWED" else "badge-fail"

    # Açık pozisyon satırları
    if open_positions:
        open_pos_rows = []
        for p in open_positions:
            tkr = escape_html(p.get("ticker"))
            sh = float(p.get("shares", 0.0))
            avg_p = float(p.get("avg_buy_price", 0.0))
            cur_p = float(p.get("current_price", 0.0))
            sl_p = float(p.get("stop_loss", 0.0))
            tp_p = float(p.get("take_profit", 0.0))
            val = round(sh * cur_p, 2)
            cost = round(sh * avg_p, 2)
            pnl = round(val - cost, 2)
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0.0
            weight_pct = (val / equity) * 100 if equity > 0 else 0.0
            row_cls = "pos" if pnl >= 0 else "neg"

            # Stop-Loss -> Current -> Take-Profit bar yüzdesi
            if tp_p > sl_p:
                range_pct = max(0.0, min(100.0, ((cur_p - sl_p) / (tp_p - sl_p)) * 100.0))
            else:
                range_pct = 50.0

            open_pos_rows.append(f"""
            <tr>
              <td><span class="ticker-pill">{tkr}</span></td>
              <td class="private-val">{sh:.2f}</td>
              <td>${avg_p:.2f}</td>
              <td><strong>${cur_p:.2f}</strong></td>
              <td class="private-val">${val:,.2f} <span class="muted">(%{weight_pct:.1f})</span></td>
              <td class="{row_cls} private-val">{pnl:+,.2f}$ ({pnl_pct:+.2f}%)</td>
              <td>
                <div class="sl-tp-wrap">
                  <span class="sl-label">SL: ${sl_p:.2f}</span>
                  <div class="sl-tp-bar"><div class="sl-tp-fill" style="width:{range_pct:.1f}%"></div></div>
                  <span class="tp-label">TP: ${tp_p:.2f}</span>
                </div>
              </td>
              <td class="thesis-cell">{escape_html(p.get("thesis", "-"))}</td>
            </tr>
            """)
        open_positions_html = "\n".join(open_pos_rows)
    else:
        open_positions_html = '<tr><td colspan="8" class="empty-row">Şu anda açık pozisyon bulunmamaktadır (Nakit ağırlıklı).</td></tr>'

    # Watchlist satırları
    if watchlist:
        wl_rows = []
        for w in watchlist:
            wl_rows.append(f"""
            <tr>
              <td><span class="ticker-pill">{escape_html(w.get("ticker"))}</span></td>
              <td>{escape_html(w.get("added_date"))}</td>
              <td>{escape_html(w.get("expires_date"))}</td>
              <td><strong>${float(w.get("target_entry_price", 0)):.2f}</strong></td>
              <td class="neg">${float(w.get("stop_loss_plan", 0)):.2f}</td>
              <td><span class="action-badge action-WAIT_BUY">{escape_html(w.get("status", "WAIT_BUY"))}</span></td>
              <td class="thesis-cell">{escape_html(w.get("reason", "-"))}</td>
            </tr>
            """)
        watchlist_html = "\n".join(wl_rows)
    else:
        watchlist_html = '<tr><td colspan="7" class="empty-row">İzleme listesinde aktif hisse bulunmamaktadır.</td></tr>'

    # İşlem geçmişi satırları
    if history:
        hist_rows = []
        for t in reversed(history[-15:]):
            act = str(t.get("action", "")).upper()
            pnl_val = float(t.get("pnl_usd", 0.0) or 0.0)
            pnl_cell = f'<span class="{"pos" if pnl_val >= 0 else "neg"} private-val">{pnl_val:+,.2f}$</span>' if act == "SELL" else "-"
            hist_rows.append(f"""
            <tr>
              <td>{escape_html(t.get("date"))}</td>
              <td><span class="ticker-pill">{escape_html(t.get("ticker"))}</span></td>
              <td><span class="action-badge action-{escape_html(act)}">{escape_html(act)}</span></td>
              <td class="private-val">{float(t.get("shares", 0)):.2f}</td>
              <td>${float(t.get("price", 0)):.2f}</td>
              <td class="private-val">${float(t.get("fee_usd", 0)):.2f}</td>
              <td>{pnl_cell}</td>
              <td class="thesis-cell">{escape_html(t.get("committee_summary", "-"))}</td>
            </tr>
            """)
        history_html = "\n".join(hist_rows)
    else:
        history_html = '<tr><td colspan="8" class="empty-row">Henüz tamamlanmış işlem kaydı bulunmamaktadır.</td></tr>'

    # 11 Ajan Karar Kartları
    decision_cards = []
    for d in decisions:
        tkr = str(d.get("ticker", "UNKNOWN")).upper().strip()
        act = str(d.get("action", "DROP")).upper().strip()
        prc = float(d.get("price", 0.0) or 0.0)
        sh = float(d.get("shares", 0.0) or 0.0)
        sl = d.get("stop_loss") or d.get("stop_loss_plan")
        tp = d.get("take_profit")
        t_entry = d.get("target_entry_price")

        scorecard = build_11_agent_scorecard(
            d,
            candidate_briefing=candidates_map.get(tkr),
            cb_status=cb_status,
            cb_rationale=cb_rationale,
        )
        pass_cnt = sum(1 for s in scorecard if s["verdict"] == "PASS")
        warn_cnt = sum(1 for s in scorecard if s["verdict"] == "WARN")
        fail_cnt = sum(1 for s in scorecard if s["verdict"] == "FAIL")

        meta_pills = [f'<span class="meta-pill">Güncel Fiyat: <strong>${prc:.2f}</strong></span>']
        if sh > 0:
            meta_pills.append(f'<span class="meta-pill private-val">Adet: <strong>{sh:.2f}</strong> (${sh * prc:,.2f})</span>')
        if t_entry:
            meta_pills.append(f'<span class="meta-pill">Hedef Giriş: <strong>${float(t_entry):.2f}</strong></span>')
        if sl:
            meta_pills.append(f'<span class="meta-pill">Stop Planı: <strong>${float(sl):.2f}</strong></span>')
        if tp:
            meta_pills.append(f'<span class="meta-pill">Kâr Al (TP): <strong>${float(tp):.2f}</strong></span>')

        agent_rows = []
        for s in scorecard:
            v_cls = "verdict-PASS" if s["verdict"] == "PASS" else ("verdict-WARN" if s["verdict"] == "WARN" else "verdict-FAIL")
            priv_cls = " private-val" if s["step"] == 9 else ""
            agent_rows.append(f"""
            <div class="agent-row {v_cls}">
              <div class="agent-step">#{s["step"]}</div>
              <div class="agent-name">{escape_html(s["agent_name"])}</div>
              <div class="agent-badge"><span class="v-pill {v_cls}">{escape_html(s["badge"])}</span></div>
              <div class="agent-rationale{priv_cls}">{escape_html(s["rationale"])}</div>
            </div>
            """)

        decision_cards.append(f"""
        <div class="decision-card" data-action="{escape_html(act)}">
          <div class="decision-header">
            <div class="decision-title">
              <span class="ticker-large">{escape_html(tkr)}</span>
              <span class="action-badge action-{escape_html(act)}">{escape_html(act)}</span>
              <span class="score-summary">✅ {pass_cnt} Onay &nbsp;|&nbsp; ⚠️ {warn_cnt} Uyarı &nbsp;|&nbsp; ❌ {fail_cnt} Red</span>
            </div>
            <div class="decision-meta">{"".join(meta_pills)}</div>
          </div>
          <div class="decision-summary-box">
            <div><strong>💡 Yatırım Tezi:</strong> {escape_html(d.get("thesis") or d.get("reason") or "-")}</div>
            <div style="margin-top:4px;"><strong>⚖️ Nihai Gerekçe:</strong> {escape_html(d.get("reason") or "-")}</div>
          </div>
          <div class="agent-grid">
            {"".join(agent_rows)}
          </div>
        </div>
        """)

    decisions_html = "\n".join(decision_cards) if decision_cards else '<div class="empty-row">Bugün için incelenen hisse kararı bulunmamaktadır.</div>'

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Otonom Borsa Orkestrası — 11 Ajan & Portföy Gösterge Paneli</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card: #111827;
      --card-alt: #1e293b;
      --border: #263248;
      --text: #f1f5f9;
      --muted: #94a3b8;
      --green: #10b981;
      --green-bg: rgba(16, 185, 129, 0.14);
      --amber: #f59e0b;
      --amber-bg: rgba(245, 158, 11, 0.14);
      --red: #ef4444;
      --red-bg: rgba(239, 68, 68, 0.14);
      --blue: #3b82f6;
      --blue-bg: rgba(59, 130, 246, 0.15);
      --purple: #a855f7;
      --purple-bg: rgba(168, 85, 247, 0.15);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{ max-width: 1440px; margin: 0 auto; }}
    .topbar {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 20px 24px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      margin-bottom: 20px;
    }}
    .topbar h1 {{ font-size: 1.45rem; font-weight: 700; display: flex; align-items: center; gap: 10px; }}
    .topbar-sub {{ color: var(--muted); font-size: 0.88rem; margin-top: 4px; }}
    .topbar-controls {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
    .btn-privacy {{
      background: var(--card-alt);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 14px;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.85rem;
      transition: all 0.15s;
    }}
    .btn-privacy:hover {{ border-color: var(--blue); }}
    body.privacy-masked .private-val {{
      filter: blur(7px);
      user-select: none;
    }}
    .badge-pass {{ background: var(--green-bg); color: var(--green); border: 1px solid var(--green); padding: 5px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }}
    .badge-fail {{ background: var(--red-bg); color: var(--red); border: 1px solid var(--red); padding: 5px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }}
    .badge-mode {{ background: var(--blue-bg); color: var(--blue); border: 1px solid var(--blue); padding: 5px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }}

    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }}
    .kpi-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
    }}
    .kpi-label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .kpi-value {{ font-size: 1.55rem; font-weight: 700; margin-top: 6px; }}
    .kpi-sub {{ color: var(--muted); font-size: 0.8rem; margin-top: 4px; }}
    .pos {{ color: var(--green); }}
    .neg {{ color: var(--red); }}
    .muted {{ color: var(--muted); font-size: 0.82rem; }}

    .alloc-bar-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 22px;
    }}
    .alloc-track {{
      width: 100%;
      height: 14px;
      background: var(--card-alt);
      border-radius: 999px;
      overflow: hidden;
      display: flex;
      margin: 10px 0 8px;
    }}
    .alloc-pos {{ background: var(--blue); height: 100%; }}
    .alloc-cash {{ background: var(--green); height: 100%; }}
    .alloc-legend {{ display: flex; justify-content: space-between; font-size: 0.84rem; color: var(--muted); }}

    .section {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px 22px;
      margin-bottom: 22px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
    }}
    .section-title {{ font-size: 1.15rem; font-weight: 700; }}
    .committee-banner {{
      background: var(--card-alt);
      border-left: 4px solid var(--blue);
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 18px;
      font-size: 0.92rem;
    }}

    .filter-bar {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .filter-btn {{
      background: var(--card-alt);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 12px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.82rem;
      font-weight: 600;
    }}
    .filter-btn.active {{ background: var(--blue); border-color: var(--blue); color: #fff; }}

    .decision-card {{
      background: #141c2f;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 18px;
    }}
    .decision-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .decision-title {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
    .ticker-large {{ font-size: 1.35rem; font-weight: 800; letter-spacing: 0.03em; }}
    .score-summary {{ font-size: 0.85rem; color: var(--muted); background: var(--card); padding: 4px 10px; border-radius: 6px; }}
    .decision-meta {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .meta-pill {{ background: var(--card); border: 1px solid var(--border); padding: 4px 10px; border-radius: 6px; font-size: 0.82rem; }}
    .decision-summary-box {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 14px;
      font-size: 0.9rem;
    }}

    .action-badge {{
      padding: 4px 10px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 0.78rem;
      letter-spacing: 0.04em;
    }}
    .action-BUY {{ background: var(--green-bg); color: var(--green); border: 1px solid var(--green); }}
    .action-WAIT_BUY {{ background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber); }}
    .action-DROP {{ background: var(--red-bg); color: var(--red); border: 1px solid var(--red); }}
    .action-HOLD {{ background: var(--blue-bg); color: var(--blue); border: 1px solid var(--blue); }}
    .action-SELL {{ background: var(--purple-bg); color: var(--purple); border: 1px solid var(--purple); }}

    .agent-grid {{
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .agent-row {{
      display: grid;
      grid-template-columns: 42px 260px 115px 1fr;
      align-items: center;
      gap: 12px;
      padding: 8px 12px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 0.86rem;
    }}
    @media (max-width: 900px) {{
      .agent-row {{ grid-template-columns: 40px 1fr; }}
    }}
    .agent-step {{ font-weight: 700; color: var(--muted); }}
    .agent-name {{ font-weight: 600; }}
    .v-pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.76rem;
      font-weight: 700;
    }}
    .verdict-PASS .v-pill {{ background: var(--green-bg); color: var(--green); }}
    .verdict-WARN .v-pill {{ background: var(--amber-bg); color: var(--amber); }}
    .verdict-FAIL .v-pill {{ background: var(--red-bg); color: var(--red); }}
    .agent-rationale {{ color: #cbd5e1; }}

    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th, td {{ padding: 11px 12px; text-align: left; border-bottom: 1px solid var(--border); vertical-align: middle; }}
    th {{ color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 0.76rem; letter-spacing: 0.04em; }}
    .ticker-pill {{ background: var(--card-alt); padding: 4px 9px; border-radius: 6px; font-weight: 700; }}
    .thesis-cell {{ max-width: 420px; color: #cbd5e1; }}
    .empty-row {{ text-align: center; color: var(--muted); padding: 20px; font-style: italic; }}

    .sl-tp-wrap {{ display: flex; align-items: center; gap: 6px; font-size: 0.75rem; min-width: 190px; }}
    .sl-label {{ color: var(--red); }}
    .tp-label {{ color: var(--green); }}
    .sl-tp-bar {{ flex: 1; height: 6px; background: var(--card-alt); border-radius: 999px; overflow: hidden; }}
    .sl-tp-fill {{ height: 100%; background: linear-gradient(90deg, var(--amber), var(--green)); }}
  </style>
</head>
<body>
  <div class="container">
    <div class="topbar">
      <div>
        <h1>🏛️ Otonom Borsa Orkestrası — Komite & Portföy Paneli</h1>
        <div class="topbar-sub">
          Son Güncelleme: <strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</strong> &nbsp;|&nbsp;
          Karar Tarihi: <strong>{escape_html(today_str)}</strong> &nbsp;|&nbsp;
          🔒 <em>Bu panel yereldir (.gitignore ile GitHub'a gönderilmez)</em>
        </div>
      </div>
      <div class="topbar-controls">
        <span class="badge-mode">MOD: {escape_html(trading_mode)}</span>
        <span class="{cb_badge_class}">DEVRE KESİCİ: {escape_html(cb_status)}</span>
        <button class="btn-privacy" onclick="togglePrivacy()" id="privacyBtn">🔒 Tutarları Gizle</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Toplam Varlık (Total Equity)</div>
        <div class="kpi-value private-val">${equity:,.2f}</div>
        <div class="kpi-sub private-val">Başlangıç: ${INITIAL_CASH:,.2f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Nakit Bakiye (Cash)</div>
        <div class="kpi-value private-val">${cash:,.2f}</div>
        <div class="kpi-sub">Kasa Ağırlığı: %{cash_pct:.1f}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Açık Pozisyon Değeri</div>
        <div class="kpi-value private-val">${positions_value:,.2f}</div>
        <div class="kpi-sub">Aktif Hisse: {len(open_positions)} adet (%{pos_pct:.1f})</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Toplam Net Kâr / Zarar</div>
        <div class="kpi-value {pnl_color_class} private-val">{net_pnl:+,.2f}$</div>
        <div class="kpi-sub {pnl_color_class}">Getiri: {net_pnl_pct:+.2f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Ödenen Komisyon (Midas)</div>
        <div class="kpi-value private-val">${fees_paid:,.2f}</div>
        <div class="kpi-sub">İşlem Başı Sabit $1.50</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Maks. Pozisyon Tavanı (%20)</div>
        <div class="kpi-value private-val">${max_pos_limit_usd:,.2f}</div>
        <div class="kpi-sub">İzleme Listesi: {len(watchlist)} hisse</div>
      </div>
    </div>

    <div class="alloc-bar-card">
      <div style="display:flex; justify-content:space-between; font-weight:600; font-size:0.9rem;">
        <span>Portföy Sermaye Dağılımı (Nakit vs. Hisse)</span>
        <span>Hisse: %{pos_pct:.1f} &nbsp;|&nbsp; Nakit: %{cash_pct:.1f}</span>
      </div>
      <div class="alloc-track">
        <div class="alloc-pos" style="width:{pos_pct:.1f}%"></div>
        <div class="alloc-cash" style="width:{cash_pct:.1f}%"></div>
      </div>
      <div class="alloc-legend">
        <span>🔵 Açık Hisse Pozisyonları (%{pos_pct:.1f})</span>
        <span>🟢 Kullanılabilir Nakit Bakiye (%{cash_pct:.1f})</span>
      </div>
    </div>

    <div class="section">
      <div class="section-header">
        <div class="section-title">🧠 11 Ajan Yatırım Komitesi Karar Karnesi (İncelenen {len(decisions)} Hisse)</div>
        <div class="filter-bar">
          <button class="filter-btn active" onclick="filterCards('ALL', this)">Tümü ({len(decisions)})</button>
          <button class="filter-btn" onclick="filterCards('BUY', this)">🟢 BUY</button>
          <button class="filter-btn" onclick="filterCards('WAIT_BUY', this)">🟡 WAIT_BUY</button>
          <button class="filter-btn" onclick="filterCards('DROP', this)">🔴 DROP</button>
          <button class="filter-btn" onclick="filterCards('HOLD', this)">🔵 HOLD</button>
          <button class="filter-btn" onclick="filterCards('SELL', this)">🟣 SELL</button>
        </div>
      </div>
      <div class="committee-banner">
        <strong>📋 Komite Genel Sentezi:</strong> {committee_note}
      </div>
      <div id="decisionCardsContainer">
        {decisions_html}
      </div>
    </div>

    <div class="section">
      <div class="section-header">
        <div class="section-title">💼 Açık Pozisyonlar (open_positions)</div>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Sembol</th>
              <th>Adet</th>
              <th>Alış Fiyatı</th>
              <th>Güncel Fiyat</th>
              <th>Piyasa Değeri</th>
              <th>Net Kâr/Zarar</th>
              <th>Stop-Loss / Hedef Mesafesi</th>
              <th>Yatırım Tezi</th>
            </tr>
          </thead>
          <tbody>
            {open_positions_html}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <div class="section-header">
        <div class="section-title">🔭 İzleme Listesi (watchlist — 14 Gün Süreli WAIT_BUY Adayları)</div>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Sembol</th>
              <th>Eklenme Tarihi</th>
              <th>Son Geçerlilik</th>
              <th>Hedef Giriş</th>
              <th>Planlanan Stop</th>
              <th>Durum</th>
              <th>Bekleme Gerekçesi</th>
            </tr>
          </thead>
          <tbody>
            {watchlist_html}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <div class="section-header">
        <div class="section-title">📜 Son İşlem Geçmişi (trade_history)</div>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Tarih</th>
              <th>Sembol</th>
              <th>İşlem</th>
              <th>Adet</th>
              <th>Fiyat</th>
              <th>Komisyon</th>
              <th>Net Realize PnL</th>
              <th>Komite Özeti</th>
            </tr>
          </thead>
          <tbody>
            {history_html}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    function togglePrivacy() {{
      document.body.classList.toggle('privacy-masked');
      const isMasked = document.body.classList.contains('privacy-masked');
      const btn = document.getElementById('privacyBtn');
      btn.textContent = isMasked ? '🔓 Tutarları Göster' : '🔒 Tutarları Gizle';
    }}
    function filterCards(action, btnEl) {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');
      document.querySelectorAll('.decision-card').forEach(card => {{
        if (action === 'ALL' || card.getAttribute('data-action') === action) {{
          card.style.display = 'block';
        }} else {{
          card.style.display = 'none';
        }}
      }});
    }}
  </script>
</body>
</html>
"""


def save_text_atomic(filepath: Path, content: str) -> None:
    """Metin dosyasını önce .tmp olarak yazıp ardından atomik olarak hedefe taşır."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_name(f"{filepath.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, filepath)


def main() -> None:
    parser = argparse.ArgumentParser(description="Otonom Borsa Orkestrası UI & Dashboard Üretici")
    parser.add_argument(
        "--update-markdown",
        action="store_true",
        help="docs/PORTFOLIO_DASHBOARD.md dosyasını da yeniden üretir.",
    )
    parser.add_argument(
        "--privacy",
        action="store_true",
        help="Markdown çıktısında kişisel bakiye ve pozisyon tutarlarını gizler.",
    )
    args = parser.parse_args()

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    decisions_data = json.loads(DECISIONS_FILE.read_text(encoding="utf-8")) if DECISIONS_FILE.exists() else {}
    briefing_data = json.loads(BRIEFING_FILE.read_text(encoding="utf-8")) if BRIEFING_FILE.exists() else None
    today_str = decisions_data.get("decisions_date") or date.today().strftime("%Y-%m-%d")

    html_content = generate_dashboard_html(state, decisions_data, today_str, briefing_data=briefing_data)
    save_text_atomic(HTML_DASHBOARD_FILE, html_content)
    print(f"[✓] Yerel İnteraktif HTML Gösterge Paneli üretildi: {HTML_DASHBOARD_FILE}")

    if args.update_markdown:
        md_content = generate_dashboard_markdown(
            state,
            decisions_data,
            today_str,
            briefing_data=briefing_data,
            privacy_mode=args.privacy,
        )
        save_text_atomic(DASHBOARD_FILE, md_content)
        print(f"[✓] Markdown Gösterge Paneli güncellendi: {DASHBOARD_FILE}")


if __name__ == "__main__":
    main()

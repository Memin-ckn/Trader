#!/usr/bin/env python3
"""
execute_decisions.py
Yerel Paper Trading Orkestrası - İşlem ve Hafıza Yürütücüsü

Görevler:
1. decisions.json dosyasını okumak.
2. state.json dosyasındaki portföy ve pozisyon durumunu güncellemek:
   - BUY: Kasanın maks %20'si kuralına uyarak alım yap, kasadan hisse bedeli + 1.50$ komisyon düş,
          open_positions ve trade_history'ye ekle, watchlist'ten çıkar.
   - SELL: Açık pozisyonu kapat, hisse satış bedelinden 1.50$ komisyon düşüp kasaya ekle,
           net PnL (alış komisyonu + satış komisyonu dahil) hesaplayıp trade_history'ye işle.
   - WAIT_BUY: Hedef giriş fiyatı, stop-loss planı ve 14 günlük son geçerlilik tarihiyle watchlist'e ekle/güncelle.
   - DROP: İzleme listesinden çıkar.
   - HOLD: Mevcut açık pozisyonu koru ve güncel fiyatını güncelle.
3. Açık pozisyonların güncel piyasa değeriyle total_equity_usd değerini yeniden hesaplamak.
4. state.json dosyasını kaydetmek.
5. Son durumu okunabilir formatta PORTFOLIO_DASHBOARD.md dosyasına yazdırmak.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.paths import (
    BASE_DIR,
    BRIEFING_FILE,
    DASHBOARD_FILE,
    DECISIONS_FILE,
    HTML_DASHBOARD_FILE,
    STATE_FILE,
)
from src.ui_dashboard import (
    build_11_agent_scorecard,
    generate_dashboard_html,
    generate_dashboard_markdown,
    sanitize_table_cell as _sanitize_table_cell,
    save_text_atomic,
)

INITIAL_CASH = 3500.00
FEE_PER_TRADE = 1.50
MAX_POSITION_PCT = 0.20


def _floor_shares(val: float) -> float:
    """Pay adedini bütçe aşımını önlemek için her zaman 2 ondalık basamağa aşağı yuvarlar (floor)."""
    if not math.isfinite(val) or val <= 0:
        return 0.0
    dec_val = Decimal(str(val))
    return float(dec_val.quantize(Decimal("0.01"), rounding=ROUND_FLOOR))


def load_json(filepath: Path) -> dict[str, Any]:
    if not filepath.exists():
        raise FileNotFoundError(f"{filepath} bulunamadı!")
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath: Path, data: dict[str, Any]) -> None:
    """Veriyi önce geçici (.tmp) dosyaya yazıp ardından atomik olarak asıl dosyanın üzerine taşır."""
    tmp_path = filepath.with_name(f"{filepath.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, filepath)


def process_decisions(
    state: dict[str, Any],
    decisions_data: dict[str, Any],
    enforce_risk_cap: bool = False,
) -> dict[str, Any]:
    """
    Kararları state sözlüğü üzerinde yürütür, portföy özetini ve açık pozisyonları günceller.
    """
    today_str = decisions_data.get("decisions_date") or date.today().strftime("%Y-%m-%d")
    cb_status = str(decisions_data.get("circuit_breaker_acknowledged", "TRADING_ALLOWED")).upper().strip()

    summary = state.setdefault("portfolio_summary", {})
    cash = round(float(summary.get("cash_usd", INITIAL_CASH)), 2)
    open_positions: list[dict[str, Any]] = state.setdefault("open_positions", [])
    watchlist: list[dict[str, Any]] = state.setdefault("watchlist", [])
    trade_history: list[dict[str, Any]] = state.setdefault("trade_history", [])

    # Başlangıç toplam varlığını mevcut nakit ve açık pozisyonlardan doğrula
    initial_positions_val = round(
        sum(round(float(p.get("shares", 0.0)) * float(p.get("current_price", 0.0)), 2) for p in open_positions),
        2,
    )
    total_equity = round(float(summary.get("total_equity_usd", cash + initial_positions_val)), 2)
    total_fees = round(float(summary.get("total_fees_paid_usd", 0.0)), 2)

    print(f"[*] İşlem Başlangıcı: Nakit = ${cash:,.2f} | Varlık = ${total_equity:,.2f}")

    decisions = decisions_data.get("decisions", [])
    print(f"[*] İşlenecek Karar Sayısı: {len(decisions)}\n")

    # İdempotency Koruması: Aynı gün aynı karar paketinin mükerrer çalışmasını engelle
    batch_sig = hashlib.sha256(
        f"{today_str}:{cb_status}:{json.dumps(decisions, sort_keys=True)}".encode()
    ).hexdigest()
    if summary.get("last_decisions_digest") == batch_sig:
        print(f"    [*] İdempotency Koruması: {today_str} tarihli karar paketi daha önce zaten işlenmiş. Tekrar icra engellendi.")
        return state

    for d in decisions:
        ticker = str(d.get("ticker", "")).upper().strip()
        action = str(d.get("action", "")).upper().strip()
        raw_price = d.get("price") if d.get("price") is not None else d.get("limit_price", 0.0)
        raw_shares = d.get("shares", 0.0)
        price = float(raw_price) if raw_price is not None else 0.0
        shares = float(raw_shares) if raw_shares is not None else 0.0
        reason = d.get("reason") or d.get("rationale") or ""
        thesis = d.get("thesis") or reason

        if not ticker:
            continue

        print(f"--- [İŞLEM: {ticker} -> {action}] ---")

        if action == "BUY":
            if cb_status in ("HALTED", "COOLDOWN"):
                print(f"    [X] Devre kesici ({cb_status}) aktif olduğu için {ticker} alımı engellendi!")
                continue

            if not math.isfinite(price) or price <= 0 or not math.isfinite(shares) or shares <= 0:
                print(f"    [X] Geçersiz fiyat ({price}) veya adet ({shares}) nedeniyle {ticker} alımı iptal edildi.")
                continue

            price = round(price, 2)
            shares = _floor_shares(shares)

            # Maksimum Pozisyon Kontrolü: Kasanın (Total Equity) kesin olarak en fazla %20'si
            max_allowed_val = round(total_equity * MAX_POSITION_PCT, 2)
            existing_pos = next((p for p in open_positions if p.get("ticker") == ticker), None)
            existing_val = (
                round(float(existing_pos["shares"]) * float(existing_pos["current_price"]), 2)
                if existing_pos
                else 0.0
            )
            rem_allowed_val = max(0.0, round(max_allowed_val - existing_val, 2))
            position_cost = round(shares * price, 2)

            if position_cost > rem_allowed_val:
                # Pozisyon büyüklüğünü kasanın %20'sine (aşağı yuvarlayarak / floor) sınırla
                shares = _floor_shares(rem_allowed_val / price)
                position_cost = round(shares * price, 2)
                # Eğer kayan nokta çarpımı hala sınırı 1 cent aşıyorsa 0.01 adet düşür
                while shares > 0 and position_cost > rem_allowed_val:
                    shares = round(shares - 0.01, 2)
                    position_cost = round(shares * price, 2)
                print(
                    f"    [!] Pozisyon boyutu kasanın %20'si ile sınırlandı (Maks: ${rem_allowed_val:.2f}) -> {shares:.2f} adet (${position_cost:.2f})."
                )

            # Mekanik %1 Kasa Riski Tavanı (Maksimum %1 Risk, ~$35-38):
            is_risk_cap_active = (
                enforce_risk_cap
                or bool(decisions_data.get("enforce_risk_cap", False))
                or bool(d.get("enforce_risk_cap", False))
            )
            raw_sl = d.get("stop_loss")
            if is_risk_cap_active and raw_sl is not None:
                sl_val = float(raw_sl)
                if sl_val > 0 and price > sl_val:
                    max_risk_usd = round(total_equity * 0.01, 2)
                    per_share_risk = price - sl_val
                    max_risk_shares = _floor_shares(max_risk_usd / per_share_risk)
                    if shares > max_risk_shares:
                        shares = max_risk_shares
                        position_cost = round(shares * price, 2)
                        print(
                            f"    [!] %1 risk tavanı uygulandı (Maks Risk: ${max_risk_usd:.2f}, Lot Başı Risk: ${per_share_risk:.2f}) -> {shares:.2f} adet (${position_cost:.2f})."
                        )

            total_buy_required = round(position_cost + FEE_PER_TRADE, 2)
            if total_buy_required > cash:
                # Nakit yetersizse bakiye kadar alım hesapla (floor ile asla kasayı eksiye düşürme)
                avail_cash_for_stock = max(0.0, round(cash - FEE_PER_TRADE, 2))
                shares = _floor_shares(avail_cash_for_stock / price)
                position_cost = round(shares * price, 2)
                while shares > 0 and round(position_cost + FEE_PER_TRADE, 2) > cash:
                    shares = round(shares - 0.01, 2)
                    position_cost = round(shares * price, 2)
                total_buy_required = round(position_cost + FEE_PER_TRADE, 2)
                print(
                    f"    [!] Yetersiz nakit! Alım nakit miktarına göre uyarlandı: {shares:.2f} adet (${position_cost:.2f})."
                )

            if shares <= 0 or position_cost <= 0 or total_buy_required > cash:
                print(f"    [X] Yetersiz bakiye veya limit aşımı nedeniyle {ticker} alımı iptal edildi.")
                continue

            # Kasadan düş
            cash = round(cash - total_buy_required, 2)
            total_fees = round(total_fees + FEE_PER_TRADE, 2)

            stop_loss = round(float(d.get("stop_loss", price * 0.94)), 2)
            take_profit = round(float(d.get("take_profit", price * 1.15)), 2)

            if existing_pos:
                old_shares = float(existing_pos["shares"])
                old_cost = round(old_shares * float(existing_pos["avg_buy_price"]), 2)
                new_total_shares = round(old_shares + shares, 2)
                existing_pos["shares"] = new_total_shares
                existing_pos["avg_buy_price"] = round((old_cost + position_cost) / new_total_shares, 2)
                existing_pos["current_price"] = price
                existing_pos["stop_loss"] = stop_loss
                existing_pos["take_profit"] = take_profit
                existing_pos["thesis"] = thesis
                existing_fees = float(existing_pos.get("fees_paid_usd", FEE_PER_TRADE))
                existing_pos["fees_paid_usd"] = round(existing_fees + FEE_PER_TRADE, 2)
            else:
                open_positions.append({
                    "ticker": ticker,
                    "shares": round(shares, 2),
                    "avg_buy_price": price,
                    "current_price": price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "buy_date": today_str,
                    "thesis": thesis,
                    "fees_paid_usd": FEE_PER_TRADE,
                })

            # İşlem geçmişine yaz
            trade_history.append({
                "date": today_str,
                "ticker": ticker,
                "action": "BUY",
                "shares": round(shares, 2),
                "price": price,
                "fee_usd": FEE_PER_TRADE,
                "pnl_usd": 0.0,
                "committee_summary": thesis,
            })

            # Eğer izleme listesindeyse çıkar
            watchlist[:] = [w for w in watchlist if w.get("ticker") != ticker]

            print(
                f"    [✓] {shares:.2f} adet {ticker} @ ${price:.2f} alındı. Maliyet: ${position_cost:.2f} + ${FEE_PER_TRADE:.2f} komisyon."
            )
            print(f"        Stop-Loss: ${stop_loss:.2f} | Kâr Al: ${take_profit:.2f}")

        elif action == "SELL":
            # Pozisyonu bul
            match_idx = next((i for i, p in enumerate(open_positions) if p.get("ticker") == ticker), None)
            if match_idx is None:
                print(f"    [!] Uyarı: {ticker} açık pozisyonlarda bulunamadı!")
                continue

            current_pos = open_positions[match_idx]
            if not math.isfinite(price) or price <= 0:
                price = float(current_pos.get("current_price", 0.0))

            price = round(price, 2)
            total_pos_shares = round(float(current_pos.get("shares", 0.0)), 2)

            # Kısmi satış desteği: eğer karar adet belirtmişse ve bu adet toplamdan küçükse kısmi sat
            req_shares = _floor_shares(shares) if shares > 0 else total_pos_shares
            sell_shares = min(req_shares, total_pos_shares)
            if sell_shares <= 0:
                sell_shares = total_pos_shares

            avg_buy = round(float(current_pos.get("avg_buy_price", price)), 2)
            buy_date = current_pos.get("buy_date", today_str)

            gross_proceeds = round(sell_shares * price, 2)
            net_proceeds = round(gross_proceeds - FEE_PER_TRADE, 2)
            cash = round(cash + net_proceeds, 2)
            total_fees = round(total_fees + FEE_PER_TRADE, 2)

            # Net kâr/zarar hesabı: Satış tutarı - Alış maliyeti - (İlgili Alış komisyonu + Satış komisyonu)
            buy_cost = round(sell_shares * avg_buy, 2)
            accum_buy_fees = float(current_pos.get("fees_paid_usd", FEE_PER_TRADE))

            if sell_shares >= total_pos_shares:
                open_positions.pop(match_idx)
                trade_net_pnl = round((gross_proceeds - buy_cost) - (accum_buy_fees + FEE_PER_TRADE), 2)
            else:
                current_pos["shares"] = round(total_pos_shares - sell_shares, 2)
                current_pos["current_price"] = price
                sold_ratio = sell_shares / total_pos_shares if total_pos_shares > 0 else 1.0
                fee_portion = round(accum_buy_fees * sold_ratio, 2)
                current_pos["fees_paid_usd"] = round(accum_buy_fees - fee_portion, 2)
                trade_net_pnl = round((gross_proceeds - buy_cost) - (fee_portion + FEE_PER_TRADE), 2)

            trade_history.append({
                "date": today_str,
                "ticker": ticker,
                "action": "SELL",
                "shares": sell_shares,
                "price": price,
                "fee_usd": FEE_PER_TRADE,
                "pnl_usd": trade_net_pnl,
                "buy_date": buy_date,
                "committee_summary": reason,
            })

            pnl_sign = "+" if trade_net_pnl >= 0 else ""
            print(
                f"    [✓] {sell_shares:.2f} adet {ticker} @ ${price:.2f} satıldı. Gelir: ${gross_proceeds:.2f} - ${FEE_PER_TRADE:.2f} komisyon."
            )
            print(f"        Net Kâr/Zarar: {pnl_sign}${trade_net_pnl:.2f}")

        elif action == "WAIT_BUY":
            raw_tgt = d.get("target_entry_price") or d.get("target_price") or price
            target_entry = float(raw_tgt) if raw_tgt is not None else 0.0
            stop_plan = float(d.get("stop_loss_plan", target_entry * 0.94))
            expires = (date.fromisoformat(today_str) + timedelta(days=14)).strftime("%Y-%m-%d")

            # Var olanı güncelle veya yeni ekle
            existing = next((w for w in watchlist if w.get("ticker") == ticker), None)
            if existing:
                existing["expires_date"] = expires
                existing["target_entry_price"] = round(target_entry, 2)
                existing["stop_loss_plan"] = round(stop_plan, 2)
                existing["status"] = "WAIT_BUY"
                existing["reason"] = reason
                print(
                    f"    [✓] {ticker} izleme listesinde güncellendi (Hedef: ${target_entry:.2f}, Son Gün: {expires})."
                )
            else:
                watchlist.append({
                    "ticker": ticker,
                    "added_date": today_str,
                    "expires_date": expires,
                    "target_entry_price": round(target_entry, 2),
                    "stop_loss_plan": round(stop_plan, 2),
                    "status": "WAIT_BUY",
                    "reason": reason,
                })
                print(
                    f"    [✓] {ticker} izleme listesine eklendi (Hedef: ${target_entry:.2f}, Stop Planı: ${stop_plan:.2f}, Son Gün: {expires})."
                )

        elif action == "DROP":
            before_len = len(watchlist)
            watchlist[:] = [w for w in watchlist if w.get("ticker") != ticker]
            if len(watchlist) < before_len:
                print(f"    [✓] {ticker} izleme listesinden çıkarıldı (DROP).")
            else:
                print(f"    [*] {ticker} listede zaten yoktu.")

        elif action == "HOLD":
            # Açık pozisyonun güncel fiyatını güncelle
            for p in open_positions:
                if p.get("ticker") == ticker:
                    if math.isfinite(price) and price > 0:
                        p["current_price"] = round(price, 2)
                    if d.get("stop_loss") is not None:
                        p["stop_loss"] = round(float(d["stop_loss"]), 2)
                    if d.get("take_profit") is not None:
                        p["take_profit"] = round(float(d["take_profit"]), 2)
                    print(f"    [✓] {ticker} pozisyonu korundu (HOLD). Güncel Fiyat: ${p['current_price']:.2f}")
                    break
        else:
            print(f"    [!] Tanımlanamayan aksiyon: {action} (Atlandı)")

    # 4. Süresi dolmuş (EXPIRED) watchlist elemanları varsa temizle ve Toplam Portföy Değerini (Total Equity) Yeniden Hesapla
    watchlist[:] = [w for w in watchlist if w.get("status") != "EXPIRED"]
    positions_market_val = round(
        sum(round(float(pos["shares"]) * float(pos["current_price"]), 2) for pos in open_positions),
        2,
    )
    new_total_equity = round(cash + positions_market_val, 2)

    summary["cash_usd"] = round(cash, 2)
    summary["total_equity_usd"] = round(new_total_equity, 2)
    summary["total_fees_paid_usd"] = round(total_fees, 2)
    summary["last_run_timestamp"] = datetime.now().isoformat()
    summary["last_decisions_digest"] = batch_sig

    return state


def main(
    state_file: Path | None = None,
    decisions_file: Path | None = None,
    dashboard_file: Path | None = None,
    html_dashboard_file: Path | None = None,
    briefing_file: Path | None = None,
) -> int:
    state_path = state_file or STATE_FILE
    decisions_path = decisions_file or DECISIONS_FILE
    dashboard_path = dashboard_file or DASHBOARD_FILE
    html_path = html_dashboard_file or (
        HTML_DASHBOARD_FILE if dashboard_file is None else dashboard_path.with_suffix(".html")
    )
    briefing_path = briefing_file or (
        BRIEFING_FILE if state_file is None else state_path.parent / "daily_briefing.json"
    )

    print("=" * 60)
    print("Yerel Paper Trading Orkestrası - Karar Yürütücüsü (execute_decisions)")
    print("=" * 60)

    is_init = "--init" in sys.argv

    if not decisions_path.exists() and not is_init:
        print(f"[!] Hata: {decisions_path} bulunamadı!")
        print("    Lütfen önce Komite analizini yapıp decisions.json dosyasını oluşturun.")
        print("    (Başlangıç gösterge panelini oluşturmak için: python execute_decisions.py --init)")
        return 1

    state = load_json(state_path)
    decisions_data = load_json(decisions_path) if decisions_path.exists() else {
        "decisions_date": date.today().strftime("%Y-%m-%d"),
        "circuit_breaker_acknowledged": "INITIALIZED",
        "committee_overall_note": "Başlangıç durumu (Henüz işlem yapılmadı).",
        "decisions": []
    }
    briefing_data = load_json(briefing_path) if briefing_path.exists() else None

    today_str = decisions_data.get("decisions_date") or date.today().strftime("%Y-%m-%d")
    process_decisions(state, decisions_data)

    summary = state["portfolio_summary"]
    open_positions = state.get("open_positions", [])
    positions_market_val = round(
        sum(round(float(pos["shares"]) * float(pos["current_price"]), 2) for pos in open_positions),
        2,
    )

    # 5. state.json Kaydet
    save_json(state_path, state)
    print(f"\n[✓] {state_path.name} başarıyla güncellendi.")
    print(f"    Yeni Nakit: ${summary['cash_usd']:,.2f}")
    print(f"    Hisse Varlığı: ${positions_market_val:,.2f}")
    print(f"    Toplam Varlık: ${summary['total_equity_usd']:,.2f}")
    print(f"    Ödenen Toplam Komisyon: ${summary['total_fees_paid_usd']:,.2f}")

    # 6. PORTFOLIO_DASHBOARD.md ve yerel dashboard.html Oluştur
    dashboard_md = generate_dashboard_markdown(state, decisions_data, today_str, briefing_data=briefing_data)
    save_text_atomic(dashboard_path, dashboard_md)
    print(f"[✓] Portföy gösterge paneli (Markdown) güncellendi: {dashboard_path}")

    dashboard_html = generate_dashboard_html(state, decisions_data, today_str, briefing_data=briefing_data)
    save_text_atomic(html_path, dashboard_html)
    print(f"[✓] Yerel interaktif gösterge paneli (HTML) güncellendi: {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

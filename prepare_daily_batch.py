#!/usr/bin/env python3
"""
prepare_daily_batch.py
Yerel Paper Trading Orkestrası - Günlük Veri ve Kuyruk Motoru

Görevler:
1. state.json dosyasını okumak.
2. watchlist içindeki süresi dolan (14 gün) hisseleri otomatik olarak EXPIRED olarak işaretlemek.
3. 5 hisselik öncelikli analiz kuyruğunu oluşturmak:
   a) open_positions (açık pozisyonlar)
   b) watchlist (aktif izleme listesi)
   c) universe.json içinden kalan kontenjan kadar rastgele yeni keşif
4. yfinance ile güncel fiyat, 1A/3A/1Y değişim, RSI(14), MACD, SMA(50), SMA(200),
   52 haftalık zirve/dip, hacim değişimi, F/K (PE), PD/DD (PB) verilerini çekmek.
5. claude-trading-skills reposundaki check_circuit_breaker, weekly_price_action,
   ve position_sizer modüllerini çalıştırıp sonuçları entegre etmek.
6. Tüm çıktıları daily_briefing.json dosyasına yazmak.
"""

from __future__ import annotations

import json
import os
import random
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

# Tüm kütüphane ve pandas uyarılarını sessize al
warnings.filterwarnings("ignore")
warnings.simplefilter("ignore")
if hasattr(pd, "errors"):
    for warning_name in dir(pd.errors):
        if "Warning" in warning_name:
            try:
                warnings.filterwarnings("ignore", category=getattr(pd.errors, warning_name))
            except Exception:
                pass


# Proje yolları
BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
UNIVERSE_FILE = BASE_DIR / "universe.json"
BRIEFING_FILE = BASE_DIR / "daily_briefing.json"
SKILLS_DIR = BASE_DIR / "claude-trading-skills" / "skills"

# Repo script dizinlerini sys.path'e ekle
CIRCUIT_BREAKER_DIR = SKILLS_DIR / "drawdown-circuit-breaker" / "scripts"
TECHNICAL_ANALYST_DIR = SKILLS_DIR / "technical-analyst" / "scripts"
POSITION_SIZER_DIR = SKILLS_DIR / "position-sizer" / "scripts"

for p in (CIRCUIT_BREAKER_DIR, TECHNICAL_ANALYST_DIR, POSITION_SIZER_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from check_circuit_breaker import CircuitConfig, evaluate_circuit_breaker, parse_as_of
except ImportError as e:
    raise ImportError(f"check_circuit_breaker modülü yüklenemedi: {e}")

try:
    from weekly_price_action import run_weekly_price_action
except ImportError as e:
    raise ImportError(f"weekly_price_action modülü yüklenemedi: {e}")

try:
    from position_sizer import SizingParameters, calculate_position
except ImportError as e:
    raise ImportError(f"position_sizer modülü yüklenemedi: {e}")


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


def clean_universe_ticker(ticker: str) -> str:
    """Ticker sembolünü yfinance standartlarına (örn: BRK.B -> BRK-B) ve büyük harfe dönüştürür."""
    if not ticker:
        return ""
    t = str(ticker).strip().upper()
    return t.replace(".", "-")


def _is_finite_number(val: Any) -> bool:
    try:
        return val is not None and not isinstance(val, bool) and np.isfinite(float(val))
    except (TypeError, ValueError):
        return False


def clean_watchlist(state: dict[str, Any], today_str: str) -> list[str]:
    """Süresi (14 gün) dolan watchlist elemanlarını EXPIRED olarak işaretler ve listeden siler."""
    expired_tickers: list[str] = []
    watchlist = state.get("watchlist", [])
    remaining_watchlist: list[dict[str, Any]] = []
    today_dt = date.fromisoformat(today_str)

    for item in watchlist:
        exp = item.get("expires_date")
        added = item.get("added_date")
        status = item.get("status", "WAIT_BUY")

        is_expired = (status == "EXPIRED")
        if exp and exp <= today_str:
            is_expired = True
        elif not exp and added:
            try:
                if (today_dt - date.fromisoformat(added)).days >= 14:
                    is_expired = True
            except ValueError:
                pass

        if is_expired:
            item["status"] = "EXPIRED"
            ticker = item.get("ticker")
            if ticker:
                expired_tickers.append(ticker)
        else:
            remaining_watchlist.append(item)

    state["watchlist"] = remaining_watchlist
    return expired_tickers


def build_analysis_queue(
    state: dict[str, Any], universe: dict[str, Any], max_items: int = 5
) -> list[dict[str, Any]]:
    """
    Öncelik Sırası:
    1. open_positions
    2. watchlist (status == WAIT_BUY veya aktif olanlar)
    3. universe.json içinden rastgele yeni seçim
    """
    if max_items <= 0:
        return []

    queue: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    # 1. Açık pozisyonlar
    for pos in state.get("open_positions", []):
        raw_ticker = pos.get("ticker")
        ticker = str(raw_ticker).upper().strip() if raw_ticker else ""
        if ticker and ticker not in seen_tickers:
            seen_tickers.add(ticker)
            queue.append({
                "ticker": ticker,
                "source": "OPEN_POSITION",
                "details": pos,
            })
        if len(queue) >= max_items:
            return queue

    # 2. İzleme listesi
    for item in state.get("watchlist", []):
        raw_ticker = item.get("ticker")
        ticker = str(raw_ticker).upper().strip() if raw_ticker else ""
        status = item.get("status", "WAIT_BUY")
        if status not in ("EXPIRED", "INVALIDATED") and ticker and ticker not in seen_tickers:
            seen_tickers.add(ticker)
            queue.append({
                "ticker": ticker,
                "source": "WATCHLIST",
                "details": item,
            })
        if len(queue) >= max_items:
            return queue

    # 3. Kalan kontenjan kadar universe'den rastgele keşif
    remaining = max_items - len(queue)
    raw_universe = universe.get("tickers", []) if isinstance(universe, dict) else []
    candidate_tickers: list[str] = []
    for t in raw_universe:
        norm_t = clean_universe_ticker(str(t)) if t else ""
        if norm_t and norm_t not in seen_tickers and norm_t not in candidate_tickers:
            candidate_tickers.append(norm_t)

    if candidate_tickers and remaining > 0:
        chosen = random.sample(candidate_tickers, min(remaining, len(candidate_tickers)))
        for ticker in chosen:
            seen_tickers.add(ticker)
            queue.append({
                "ticker": ticker,
                "source": "DISCOVERY",
                "details": {},
            })

    return queue


def get_fallback_candidates(
    state: dict[str, Any],
    universe: dict[str, Any],
    current_queue: list[dict[str, Any]],
    count: int = 1,
    failed_tickers: set[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Keşif sırasında veri alınamayan veya delist olan hisseler yerine
    universe.json havuzundan yeni yedek adaylar çeker.
    """
    if count <= 0:
        return []

    failed = {t.upper().strip() for t in (failed_tickers or set())}
    in_queue = {str(q.get("ticker", "")).upper().strip() for q in current_queue}
    in_positions = {str(p.get("ticker", "")).upper().strip() for p in state.get("open_positions", [])}
    in_watchlist = {str(w.get("ticker", "")).upper().strip() for w in state.get("watchlist", [])}
    excluded = in_queue | in_positions | in_watchlist | failed

    raw_universe = universe.get("tickers", []) if isinstance(universe, dict) else []
    candidates = []
    for t in raw_universe:
        norm = clean_universe_ticker(str(t))
        if norm and norm not in excluded and norm not in candidates:
            candidates.append(norm)

    if not candidates:
        return []

    chosen = random.sample(candidates, min(count, len(candidates)))
    return [{"ticker": c, "source": "DISCOVERY_FALLBACK", "details": {}} for c in chosen]


def is_market_session_valid(date_str: str, hist: pd.DataFrame | None = None) -> tuple[bool, str]:
    """
    ABD borsa seansı takvim kontrolü (Haftasonu, resmi tatil ve yarım gün/sıfır hacim kontrolü).
    """
    try:
        dt = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return False, "Geçersiz tarih formatı"

    if dt.weekday() >= 5:
        return False, f"Haftasonu ({dt.strftime('%A')}): Borsa kapalı"

    fixed_holidays = {
        (1, 1): "New Year's Day",
        (6, 19): "Juneteenth",
        (7, 4): "Independence Day",
        (12, 25): "Christmas Day",
    }
    if (dt.month, dt.day) in fixed_holidays:
        return False, f"Resmi Borsa Tatili: {fixed_holidays[(dt.month, dt.day)]}"

    if hist is not None and isinstance(hist, pd.DataFrame) and not hist.empty:
        if "Volume" in hist.columns:
            last_vol = hist["Volume"].iloc[-1]
            if last_vol is None or np.isnan(last_vol) or float(last_vol) <= 0:
                return False, "Eksik/Sıfır seans hacmi (Borsa açılmamış veya yarım gün olabilir)"

    return True, "Geçerli işlem seansı"


def evaluate_forex_factory_macro_risk(
    events: list[dict[str, Any]] | None = None,
    today_str: str | None = None,
) -> dict[str, Any]:
    """
    Forex Factory / Makroekonomik Takvim değerlendirmesi.
    Eğer USD para biriminde Yüksek Etkili (High / Red) veri (FOMC, CPI, NFP vb.) varsa
    yüksek risk bayrağı üretir.
    Veri sağlanmamışsa veya hata durumunda çökmez; FAIL_SAFE modunda çalışır.
    """
    if events is None:
        return {
            "status": "FAIL_SAFE",
            "action": "PROCEED_WITH_CAUTION",
            "high_impact_count": 0,
            "events": [],
            "note": "Makro veri kaynağına ulaşılamadı, standart teknik analize devam ediliyor.",
        }

    high_risk_events = []
    for ev in events:
        currency = str(ev.get("currency", "")).upper().strip()
        impact = str(ev.get("impact", "")).upper().strip()
        ev_date = ev.get("date")

        # Bugünün USD ve Yüksek etkili (High / Red) olayları
        if currency == "USD" and impact in ("HIGH", "RED"):
            if today_str is None or ev_date is None or str(ev_date).startswith(today_str):
                high_risk_events.append(ev)

    if high_risk_events:
        return {
            "status": "MACRO_HIGH_RISK",
            "action": "HALT_NEW_BUYS",
            "high_impact_count": len(high_risk_events),
            "events": high_risk_events,
            "note": f"Bugün {len(high_risk_events)} adet yüksek etkili USD makro olayı var (Alımlar kısıtlanmalı).",
        }

    return {
        "status": "MACRO_CLEAR",
        "action": "TRADING_ALLOWED",
        "high_impact_count": 0,
        "events": [],
        "note": "Yüksek etkili USD makro engeli bulunmuyor.",
    }


def _sanitize_history_df(hist: pd.DataFrame | None) -> pd.DataFrame:
    """OHLCV DataFrame içindeki eksik/NaN satırları güvenli şekilde temizler."""
    if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
        return pd.DataFrame()
    required_cols = ["Open", "High", "Low", "Close"]
    for col in required_cols:
        if col not in hist.columns:
            return pd.DataFrame()
    cleaned = hist.dropna(subset=required_cols).copy()
    if cleaned.empty:
        return pd.DataFrame()
    if "Volume" in cleaned.columns:
        cleaned["Volume"] = cleaned["Volume"].fillna(0).clip(lower=0)
    else:
        cleaned["Volume"] = 0
    return cleaned


def calculate_indicators(hist: pd.DataFrame, info: dict[str, Any] | None) -> dict[str, Any]:
    """
    yfinance verilerinden teknik ve temel indikatörleri hesaplar.
    """
    info = info or {}
    cleaned = _sanitize_history_df(hist)
    if cleaned.empty or len(cleaned) < 30:
        return {"error": "Yetersiz fiyat verisi (en az 30 geçerli gün gerekli)"}

    close = cleaned["Close"].astype(float)
    high = cleaned["High"].astype(float)
    low = cleaned["Low"].astype(float)
    vol = cleaned["Volume"].astype(float)

    current_price = float(close.iloc[-1])
    if not _is_finite_number(current_price) or current_price <= 0:
        return {"error": "Geçersiz güncel fiyat verisi (NaN veya <= 0)"}

    n = len(close)

    # 1A, 3A, 1Y Değişim
    chg_1m = float((close.iloc[-1] / close.iloc[-22] - 1) * 100) if n >= 22 and close.iloc[-22] > 0 else 0.0
    chg_3m = float((close.iloc[-1] / close.iloc[-65] - 1) * 100) if n >= 65 and close.iloc[-65] > 0 else 0.0
    chg_1y = float((close.iloc[-1] / close.iloc[-252] - 1) * 100) if n >= 252 and close.iloc[-252] > 0 else 0.0

    # 52 Haftalık Zirve / Dip
    high_52w = float(high.iloc[-252:].max()) if n >= 252 else float(high.max())
    low_52w = float(low.iloc[-252:].min()) if n >= 252 else float(low.min())

    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_14 = float(rsi_series.iloc[-1]) if _is_finite_number(rsi_series.iloc[-1]) else 50.0

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    macd_val = float(macd_line.iloc[-1]) if _is_finite_number(macd_line.iloc[-1]) else 0.0
    signal_val = float(signal_line.iloc[-1]) if _is_finite_number(signal_line.iloc[-1]) else 0.0
    hist_val = float(macd_hist.iloc[-1]) if _is_finite_number(macd_hist.iloc[-1]) else 0.0

    # Hareketli Ortalamalar
    raw_sma_50 = close.rolling(50).mean().iloc[-1] if n >= 50 else None
    raw_sma_150 = close.rolling(150).mean().iloc[-1] if n >= 150 else None
    raw_sma_200 = close.rolling(200).mean().iloc[-1] if n >= 200 else None

    sma_50 = float(raw_sma_50) if _is_finite_number(raw_sma_50) else None
    sma_150 = float(raw_sma_150) if _is_finite_number(raw_sma_150) else None
    sma_200 = float(raw_sma_200) if _is_finite_number(raw_sma_200) else None

    # Hacim Değişimi (Son gün vs 20 günlük ortalama)
    raw_vol_20ma = vol.iloc[-21:-1].mean() if n >= 21 else vol.mean()
    vol_20ma = float(raw_vol_20ma) if _is_finite_number(raw_vol_20ma) else 0.0
    raw_vol_latest = vol.iloc[-1]
    vol_latest = float(raw_vol_latest) if _is_finite_number(raw_vol_latest) else 0.0
    vol_change_pct = float((vol_latest / vol_20ma - 1) * 100) if vol_20ma > 0 else 0.0

    # ATR (14)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    raw_atr = tr.rolling(14).mean().iloc[-1] if n >= 14 else tr.mean()
    atr_14 = float(raw_atr) if _is_finite_number(raw_atr) and float(raw_atr) > 0 else round(current_price * 0.03, 2)

    # F/K (P/E) ve PD/DD (P/B)
    raw_pe = info.get("trailingPE") if _is_finite_number(info.get("trailingPE")) else info.get("forwardPE")
    pe_ratio = round(float(raw_pe), 2) if _is_finite_number(raw_pe) else None

    raw_pb = info.get("priceToBook")
    pb_ratio = round(float(raw_pb), 2) if _is_finite_number(raw_pb) else None

    # Minervini 7-Point Trend Template Kontrolü
    trend_criteria = {}
    passed_count = 0

    # 1. Price > SMA150 ve Price > SMA200
    c1 = (sma_150 is not None and sma_200 is not None and current_price > sma_150 and current_price > sma_200)
    trend_criteria["c1_price_above_sma150_200"] = c1
    if c1: passed_count += 1

    # 2. SMA150 > SMA200
    c2 = (sma_150 is not None and sma_200 is not None and sma_150 > sma_200)
    trend_criteria["c2_sma150_above_sma200"] = c2
    if c2: passed_count += 1

    # 3. SMA200 yükseliş trendinde mi (22 gün öncesine göre)
    c3 = False
    if n >= 222 and sma_200 is not None:
        raw_sma_200_22d = close.iloc[:-22].rolling(200).mean().iloc[-1]
        if _is_finite_number(raw_sma_200_22d):
            c3 = sma_200 > float(raw_sma_200_22d)
    trend_criteria["c3_sma200_trending_up"] = c3
    if c3: passed_count += 1

    # 4. Price > SMA50
    c4 = (sma_50 is not None and current_price > sma_50)
    trend_criteria["c4_price_above_sma50"] = c4
    if c4: passed_count += 1

    # 5. Price en az %25 52-haftalık dip üzerinde
    c5 = (low_52w > 0 and (current_price - low_52w) / low_52w >= 0.25)
    trend_criteria["c5_25pct_above_52w_low"] = c5
    if c5: passed_count += 1

    # 6. Price 52-haftalık zirvenin %25 içinde
    c6 = (high_52w > 0 and (high_52w - current_price) / high_52w <= 0.25)
    trend_criteria["c6_within_25pct_52w_high"] = c6
    if c6: passed_count += 1

    # 7. 1Y Değişim Pozitif (RS vekili)
    c7 = chg_1y > 0
    trend_criteria["c7_positive_1y_relative_strength"] = c7
    if c7: passed_count += 1

    trend_template_passed = passed_count >= 5  # Minervini Stage 2 eşiği

    return {
        "current_price": round(current_price, 2),
        "change_1m_pct": round(chg_1m, 2),
        "change_3m_pct": round(chg_3m, 2),
        "change_1y_pct": round(chg_1y, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "rsi_14": round(rsi_14, 2),
        "macd": round(macd_val, 4),
        "macd_signal": round(signal_val, 4),
        "macd_hist": round(hist_val, 4),
        "sma_50": round(sma_50, 2) if sma_50 is not None else None,
        "sma_150": round(sma_150, 2) if sma_150 is not None else None,
        "sma_200": round(sma_200, 2) if sma_200 is not None else None,
        "volume_latest": int(vol_latest),
        "volume_20d_avg": int(vol_20ma),
        "volume_change_pct": round(vol_change_pct, 2),
        "atr_14": round(atr_14, 2),
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
        "trend_template": {
            "passed": trend_template_passed,
            "score": round((passed_count / 7) * 100, 1),
            "passed_count": passed_count,
            "criteria": trend_criteria,
        },
    }


def evaluate_account_circuit_breaker(state: dict[str, Any], today_str: str) -> dict[str, Any]:
    """
    state.json içindeki trade_history'yi kullanarak check_circuit_breaker çalıştırır.
    """
    theses = []
    trade_history = state.get("trade_history", [])
    account_size = float(state.get("portfolio_summary", {}).get("total_equity_usd", 3500.0))

    for idx, trade in enumerate(trade_history):
        if trade.get("action") == "SELL":
            pnl = float(trade.get("pnl_usd", 0.0))
            trade_date = trade.get("date", today_str)
            theses.append({
                "thesis_id": f"th_{trade.get('ticker')}_{idx}",
                "ticker": trade.get("ticker", "UNKNOWN"),
                "status": "CLOSED",
                "status_history": [
                    {"status": "ACTIVE", "at": f"{trade_date}T09:30:00Z"},
                    {"status": "CLOSED", "at": f"{trade_date}T16:00:00Z", "realized_pnl": pnl},
                ],
                "outcome": {"pnl_dollars": pnl},
                "exit": {"actual_date": f"{trade_date}T16:00:00Z"},
            })

    config = CircuitConfig(
        max_daily_loss_pct=2.0,
        losing_streak_n=2,
        cooldown_hours=24.0,
        weekly_drawdown_pct=5.0,
        monthly_drawdown_pct=8.0,
    )
    as_of = parse_as_of(today_str)
    res = evaluate_circuit_breaker(
        theses,
        account_size=account_size,
        as_of=as_of,
        config=config,
        initial_quality="OK" if theses else "EMPTY_STATE",
        initial_warnings=[],
    )
    return {
        "recommendation": res.get("recommendation"),
        "rationale": res.get("rationale"),
        "triggered_rules": res.get("triggered_rules", []),
        "metrics": res.get("metrics", {}),
    }


def run_technical_and_sizing(
    ticker: str,
    hist: pd.DataFrame,
    indicators: dict[str, Any],
    account_size: float,
    today_str: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    weekly_price_action ve position_sizer modüllerini çalıştırır.
    """
    if not isinstance(indicators, dict) or "error" in indicators or "current_price" not in indicators:
        err_msg = indicators.get("error", "Eksik indikatör verisi") if isinstance(indicators, dict) else "Geçersiz indikatör"
        return (
            {
                "verdict": "INSUFFICIENT_DATA",
                "confidence": "MEDIUM",
                "verdict_reason": err_msg,
                "nearest_swing_high": None,
                "nearest_swing_low": None,
                "stop_reference": None,
            },
            {
                "entry_price": None,
                "stop_price": None,
                "recommended_shares": 0.0,
                "position_value": 0.0,
                "risk_dollars": 0.0,
                "risk_pct": 0.0,
                "binding_constraint": None,
            },
        )

    cleaned = _sanitize_history_df(hist)

    # 1. Daily bars oluştur
    daily_bars = []
    for idx, row in cleaned.iterrows():
        d_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        vol_val = float(row["Volume"]) if _is_finite_number(row["Volume"]) else 0.0
        daily_bars.append({
            "date": d_str,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(max(0.0, vol_val)),
        })

    # 2. weekly_price_action (Alım için CROWDED_LONG ve CROWDED_SHORT analizleri)
    pa_long = run_weekly_price_action(daily_bars, direction="CROWDED_LONG", as_of=today_str)
    pa_short = run_weekly_price_action(daily_bars, direction="CROWDED_SHORT", as_of=today_str)

    swing_levels = pa_long.get("swing_levels") or pa_short.get("swing_levels") or {}
    nearest_low = swing_levels.get("nearest_swing_low", {}).get("price") if swing_levels.get("nearest_swing_low") else None
    nearest_high = swing_levels.get("nearest_swing_high", {}).get("price") if swing_levels.get("nearest_swing_high") else None

    # 3. Stop Price ve Sizing
    current_price = float(indicators["current_price"])
    raw_atr = indicators.get("atr_14")
    atr = float(raw_atr) if _is_finite_number(raw_atr) and float(raw_atr) > 0 else round(current_price * 0.03, 2)

    # Stop fiyatı: Eğer fraktal swing low varsa ve current_price'ın %1-%15 altındaysa onu kullan, yoksa ATR (2x) kullan
    if _is_finite_number(nearest_low) and 0.85 * current_price <= float(nearest_low) < current_price:
        stop_price = round(float(nearest_low), 2)
    else:
        stop_price = round(current_price - (2.0 * atr), 2)

    if not _is_finite_number(stop_price) or stop_price >= current_price or stop_price <= 0:
        stop_price = round(current_price * 0.94, 2)  # %6 default stop-loss

    sizing_params = SizingParameters(
        account_size=account_size if _is_finite_number(account_size) and account_size > 0 else 3500.0,
        entry_price=current_price,
        stop_price=stop_price,
        risk_pct=1.0,           # Kasanın %1'i kadar risk
        max_position_pct=20.0,  # Kasanın en fazla %20'si
        fractional_shares=True,
        share_precision=2,
    )
    sizing_result = calculate_position(sizing_params)

    pa_summary = {
        "verdict": pa_long.get("verdict"),
        "confidence": pa_long.get("confidence"),
        "verdict_reason": pa_long.get("verdict_reason"),
        "nearest_swing_high": nearest_high,
        "nearest_swing_low": nearest_low,
        "stop_reference": stop_price,
    }

    sizing_summary = {
        "entry_price": current_price,
        "stop_price": stop_price,
        "recommended_shares": sizing_result.get("final_recommended_shares"),
        "position_value": sizing_result.get("final_position_value"),
        "risk_dollars": sizing_result.get("final_risk_dollars"),
        "risk_pct": sizing_result.get("final_risk_pct"),
        "binding_constraint": sizing_result.get("binding_constraint"),
    }

    return pa_summary, sizing_summary


def main(
    state_file: Path | None = None,
    universe_file: Path | None = None,
    briefing_file: Path | None = None,
) -> int:
    state_path = state_file or STATE_FILE
    universe_path = universe_file or UNIVERSE_FILE
    briefing_path = briefing_file or BRIEFING_FILE

    print("=" * 60)
    print("Yerel Paper Trading Orkestrası - Günlük Veri Motoru (prepare_daily_batch)")
    print("=" * 60)

    # 1. State ve Universe Yükle
    state = load_json(state_path)
    universe = load_json(universe_path)
    today_str = date.today().strftime("%Y-%m-%d")

    print(f"[*] İşlem Tarihi: {today_str}")
    account_size = float(state.get("portfolio_summary", {}).get("total_equity_usd", 3500.0))
    print(f"[*] Mevcut Toplam Varlık (Equity): ${account_size:,.2f}")

    # 2. Watchlist Temizliği
    expired = clean_watchlist(state, today_str)
    if expired:
        print(f"[*] Süresi Dolan İzleme Listesi Hisseleri (EXPIRED olarak silindi): {', '.join(expired)}")
        save_json(state_path, state)
    else:
        print("[*] İzleme listesinde süresi dolan hisse yok.")

    # 3. Analiz Kuyruğunu Oluştur (Maks 5)
    queue = build_analysis_queue(state, universe, max_items=5)
    print(f"[*] Analiz Kuyruğu ({len(queue)} hisse):")
    for q in queue:
        print(f"    - {q['ticker']} ({q['source']})")

    # 4. Circuit Breaker Kontrolü
    circuit_breaker_result = evaluate_account_circuit_breaker(state, today_str)
    print(f"[*] Devre Kesici Durumu: {circuit_breaker_result['recommendation']}")
    print(f"    {circuit_breaker_result['rationale']}")

    # 5. Hisse Verilerini Çek ve Modülleri Çalıştır
    candidates_data = []
    for item in queue:
        ticker = item["ticker"]
        source = item["source"]
        print(f"\n[+] {ticker} analiz ediliyor ({source})...")

        try:
            yf_ticker = yf.Ticker(ticker)
            hist = yf_ticker.history(period="2y")
            info = yf_ticker.info or {}

            if hist is None or hist.empty:
                print(f"    [!] {ticker} için fiyat verisi alınamadı!")
                continue

            indicators = calculate_indicators(hist, info)
            if "error" in indicators:
                print(f"    [!] {ticker} veri hatası: {indicators['error']}")
                continue

            pa_res, sizing_res = run_technical_and_sizing(
                ticker, hist, indicators, account_size, today_str
            )

            candidate_payload = {
                "ticker": ticker,
                "source": source,
                "source_details": item["details"],
                "market_data": indicators,
                "weekly_price_action": pa_res,
                "position_sizing": sizing_res,
            }
            candidates_data.append(candidate_payload)

            print(f"    Fiyat: ${indicators['current_price']} | RSI(14): {indicators['rsi_14']} | SMA50: {indicators['sma_50']}")
            print(f"    Stage 2 Skoru: {indicators['trend_template']['score']}/100 (Geçti mi: {indicators['trend_template']['passed']})")
            print(f"    Önerilen Pozisyon: {sizing_res['recommended_shares']} adet (${sizing_res['position_value']:.2f}) | Risk: ${sizing_res.get('risk_dollars', 0)}")

        except Exception as exc:
            print(f"    [!] {ticker} işlenirken hata oluştu: {exc}")

    # 6. daily_briefing.json Oluştur ve Kaydet
    briefing = {
        "schema_version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "as_of_date": today_str,
        "portfolio_summary": state.get("portfolio_summary", {}),
        "circuit_breaker": circuit_breaker_result,
        "queue_summary": {
            "total_candidates": len(candidates_data),
            "open_positions_count": sum(1 for c in candidates_data if c["source"] == "OPEN_POSITION"),
            "watchlist_count": sum(1 for c in candidates_data if c["source"] == "WATCHLIST"),
            "discovery_count": sum(1 for c in candidates_data if c["source"] == "DISCOVERY"),
        },
        "candidates": candidates_data,
    }

    save_json(briefing_path, briefing)
    print(f"\n[✓] Günlük brifing hazırlandı ve kaydedildi: {briefing_path}")
    print(f"[✓] Toplam {len(candidates_data)} hisse incelendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

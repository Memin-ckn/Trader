#!/usr/bin/env python3
"""
src/backtest_data.py
Otonom Borsa Orkestrası — Cevap Anahtarı Deposu (Tarihsel Veri Önbelleği) ve Zaman Kilidi Motoru

Görevler:
1. 2022-10-01 – 2026-11-08 arası OHLCV fiyat/hacim verilerini (ve kıyaslama için SPY endeksini)
   indirip `data/backtest_cache/` altında yerel önbellekte ("Cevap Anahtarı Deposu") saklamak.
   - Kasım 2024 başlangıcında SMA(200), 22 günlük SMA(200) eğimi ve 52 haftalık zirve/dip (252 iş günü)
     indikatörlerinin eksiksiz hesaplanabilmesi için veri penceresi Ekim 2022'den başlatılır.
2. ZAMAN KİLİDİ (`slice_history_as_of`):
   - Ajanlara/komiteye veri sunulurken DataFrame'i tam `as_of_date` (`YYYY-MM-DD`) tarihinde kesmek
     (`bar_date <= as_of_date`) ve gelecekteki barların sızmasını (`Look-Ahead Bias`) %100 engellemek.
3. CEVAP ANAHTARI SORGUSU (`get_answer_key_window`, `check_sl_tp_in_window`):
   - Simülasyon adımları arasındaki ara günlerde açık pozisyonların `stop_loss` (`Low <= stop_loss`)
     veya `take_profit` (`High >= take_profit`) seviyelerinin tetiklenip tetiklenmediğini kontrol etmek.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
warnings.simplefilter("ignore")
if hasattr(pd, "errors"):
    for warning_name in dir(pd.errors):
        if "Warning" in warning_name:
            try:
                warnings.filterwarnings("ignore", category=getattr(pd.errors, warning_name))
            except Exception:
                pass

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.paths import BACKTEST_CACHE_DIR, STATE_FILE, UNIVERSE_FILE

DEFAULT_CACHE_START = "2022-10-01"
DEFAULT_CACHE_END = "2026-11-08"
DEFAULT_SIM_START = "2024-11-01"
DEFAULT_SIM_END = "2026-11-06"
DEFAULT_LOOKBACK_BARS = 504  # ~2 işlem yılı (yfinance period="2y" karşılığı)


def normalize_ticker(ticker: str) -> str:
    """Sembolü yfinance formatına (örn. BRK.B -> BRK-B) ve büyük harfe dönüştürür."""
    if not ticker:
        return ""
    return str(ticker).strip().upper().replace(".", "-")


def _bar_date_str(idx_val: Any) -> str:
    """DataFrame indeks elemanını YYYY-MM-DD metnine dönüştürür."""
    if hasattr(idx_val, "strftime"):
        return idx_val.strftime("%Y-%m-%d")
    return str(idx_val)[:10]


def normalize_history_df(hist: pd.DataFrame | None) -> pd.DataFrame:
    """
    OHLCV DataFrame indeksini saat diliminden arındırılmış (tz-naive) ve tarihe göre
    sıralanmış standart formata dönüştürür.
    """
    if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
        return pd.DataFrame()

    df = hist.copy()
    # Eğer MultiIndex sütun varsa (yf.download kaynaklı) düzleştir
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else str(c) for c in df.columns]

    required_cols = ["Open", "High", "Low", "Close"]
    for col in required_cols:
        if col not in df.columns:
            return pd.DataFrame()

    df = df.dropna(subset=required_cols).copy()
    if df.empty:
        return pd.DataFrame()

    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].fillna(0).clip(lower=0)
    else:
        df["Volume"] = 0

    # İndeksi YYYY-MM-DD bazlı Timestamp'e normalize et
    date_strings = [_bar_date_str(i) for i in df.index]
    df.index = pd.to_datetime(date_strings, format="%Y-%m-%d", errors="coerce")
    df = df[~df.index.isna()].copy()
    df = df[~df.index.duplicated(keep="last")]
    df = df.sort_index()
    df.index.name = "Date"
    return df


def slice_history_as_of(
    hist: pd.DataFrame | None,
    as_of_date: str | date,
    max_lookback_bars: int | None = DEFAULT_LOOKBACK_BARS,
) -> pd.DataFrame:
    """
    ZAMAN KİLİDİ (Point-in-Time Slicing):
    Verilen OHLCV DataFrame'i tam `as_of_date` (`YYYY-MM-DD`) tarihinde keser.
    `as_of_date` tarihinden sonraki hiçbir bar (gelecek verisi) kesinlikle döndürülmez.
    """
    df = normalize_history_df(hist)
    if df.empty:
        return pd.DataFrame()

    as_of_str = as_of_date.strftime("%Y-%m-%d") if isinstance(as_of_date, (date, datetime)) else str(as_of_date)[:10]
    cutoff_ts = pd.Timestamp(as_of_str)

    sliced = df.loc[df.index <= cutoff_ts].copy()
    if sliced.empty:
        return pd.DataFrame()

    if max_lookback_bars is not None and max_lookback_bars > 0 and len(sliced) > max_lookback_bars:
        sliced = sliced.iloc[-max_lookback_bars:].copy()

    return sliced


def verify_no_lookahead(hist: pd.DataFrame | None, as_of_date: str | date) -> tuple[bool, str]:
    """
    Verilen DataFrame içinde `as_of_date` sonrası herhangi bir satır olup olmadığını denetler.
    Gelecek verisi sızıntısı varsa (False, sızan_tarih) döner.
    """
    if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
        return True, "EMPTY"

    as_of_str = as_of_date.strftime("%Y-%m-%d") if isinstance(as_of_date, (date, datetime)) else str(as_of_date)[:10]
    bar_dates = [_bar_date_str(i) for i in hist.index]
    leaked = [d for d in bar_dates if d > as_of_str]
    if leaked:
        return False, f"LOOKAHEAD_LEAK_DETECTED: max_bar={max(leaked)} > as_of={as_of_str}"
    return True, bar_dates[-1]


def _ticker_pkl_path(ticker: str, cache_dir: Path) -> Path:
    return cache_dir / f"{normalize_ticker(ticker)}.pkl"


def _ticker_meta_path(ticker: str, cache_dir: Path) -> Path:
    return cache_dir / f"{normalize_ticker(ticker)}.meta.json"


def save_ticker_to_cache(
    ticker: str,
    hist: pd.DataFrame,
    info: dict[str, Any] | None = None,
    cache_dir: Path = BACKTEST_CACHE_DIR,
) -> bool:
    """Bir hissenin OHLCV DataFrame'ini ve temel meta verisini atomik olarak önbelleğe kaydeder."""
    norm_t = normalize_ticker(ticker)
    df = normalize_history_df(hist)
    if not norm_t or df.empty:
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)
    pkl_path = _ticker_pkl_path(norm_t, cache_dir)
    tmp_pkl = pkl_path.with_name(f"{pkl_path.name}.tmp")
    with tmp_pkl.open("wb") as f:
        pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp_pkl, pkl_path)

    meta_payload = {
        "ticker": norm_t,
        "first_date": _bar_date_str(df.index[0]),
        "last_date": _bar_date_str(df.index[-1]),
        "bars_count": len(df),
        "updated_at": datetime.now().isoformat(),
        "info": {
            "sector": (info or {}).get("sector"),
            "trailingPE": (info or {}).get("trailingPE"),
            "forwardPE": (info or {}).get("forwardPE"),
            "priceToBook": (info or {}).get("priceToBook"),
        },
    }
    meta_path = _ticker_meta_path(norm_t, cache_dir)
    tmp_meta = meta_path.with_name(f"{meta_path.name}.tmp")
    with tmp_meta.open("w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_meta, meta_path)
    return True


def load_ticker_from_cache(
    ticker: str,
    cache_dir: Path = BACKTEST_CACHE_DIR,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Önbellekten tam (kesilmemiş) Cevap Anahtarı DataFrame'ini ve info sözlüğünü okur."""
    norm_t = normalize_ticker(ticker)
    pkl_path = _ticker_pkl_path(norm_t, cache_dir)
    meta_path = _ticker_meta_path(norm_t, cache_dir)

    if not pkl_path.exists():
        return pd.DataFrame(), {}

    try:
        with pkl_path.open("rb") as f:
            df = pickle.load(f)
        df = normalize_history_df(df)
    except Exception:
        return pd.DataFrame(), {}

    info: dict[str, Any] = {}
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                meta = json.load(f)
                info = meta.get("info", {}) or {}
        except Exception:
            info = {}

    return df, info


def fetch_and_cache_ticker(
    ticker: str,
    start_date: str = DEFAULT_CACHE_START,
    end_date: str = DEFAULT_CACHE_END,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    fetch_info: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Tek bir hisseyi yfinance üzerinden `start_date`..`end_date` aralığında indirir ve
    yerel Cevap Anahtarı Deposuna (`cache_dir`) kaydeder.
    """
    norm_t = normalize_ticker(ticker)
    yf_t = yf.Ticker(norm_t)
    hist = yf_t.history(start=start_date, end=end_date, auto_adjust=True)
    df = normalize_history_df(hist)

    info: dict[str, Any] = {}
    if fetch_info and not df.empty:
        try:
            raw_info = yf_t.info or {}
            info = {
                "sector": raw_info.get("sector"),
                "trailingPE": raw_info.get("trailingPE"),
                "forwardPE": raw_info.get("forwardPE"),
                "priceToBook": raw_info.get("priceToBook"),
            }
        except Exception:
            info = {}

    if not df.empty:
        save_ticker_to_cache(norm_t, df, info=info, cache_dir=cache_dir)

    return df, info


def get_cached_or_fetch_ticker(
    ticker: str,
    as_of_date: str | date | None = None,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
    max_lookback_bars: int | None = DEFAULT_LOOKBACK_BARS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Önce yerel önbelleğe (`cache_dir`) bakar; yoksa ve `allow_network=True` ise `yfinance`'ten
    indirip önbelleğe yazar. Ardından `as_of_date` verilmişse ZAMAN KİLİDİ (`slice_history_as_of`)
    uygulayarak sadece o güne ve öncesine ait veriyi döndürür.
    """
    norm_t = normalize_ticker(ticker)
    df, info = load_ticker_from_cache(norm_t, cache_dir=cache_dir)

    if df.empty and allow_network:
        df, info = fetch_and_cache_ticker(norm_t, cache_dir=cache_dir)

    if df.empty:
        return pd.DataFrame(), info

    if as_of_date is not None:
        df = slice_history_as_of(df, as_of_date=as_of_date, max_lookback_bars=max_lookback_bars)

    return df, info


def download_batch_to_cache(
    tickers: list[str],
    start_date: str = DEFAULT_CACHE_START,
    end_date: str = DEFAULT_CACHE_END,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    force: bool = False,
    batch_size: int = 50,
    sectors_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Birden fazla hisseyi toplu olarak (`yf.download`) indirip yerel Cevap Anahtarı Deposuna kaydeder.
    Zaten önbellekte olan hisseleri `force=False` ise tekrar indirmez.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    sectors_map = sectors_map or {}

    unique_tickers: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        norm = normalize_ticker(t)
        if norm and norm not in seen:
            seen.add(norm)
            unique_tickers.append(norm)

    to_download: list[str] = []
    cached_already = 0
    for t in unique_tickers:
        if not force and _ticker_pkl_path(t, cache_dir).exists():
            cached_already += 1
        else:
            to_download.append(t)

    saved_count = 0
    failed_tickers: list[str] = []

    for i in range(0, len(to_download), batch_size):
        chunk = to_download[i : i + batch_size]
        print(f"[*] Toplu veri indiriliyor ({i + 1}..{i + len(chunk)} / {len(to_download)}): {', '.join(chunk[:8])}{'...' if len(chunk) > 8 else ''}")
        try:
            if len(chunk) == 1:
                t = chunk[0]
                df, info = fetch_and_cache_ticker(
                    t, start_date=start_date, end_date=end_date, cache_dir=cache_dir, fetch_info=False
                )
                if not df.empty:
                    if t in sectors_map:
                        info["sector"] = sectors_map[t]
                        save_ticker_to_cache(t, df, info=info, cache_dir=cache_dir)
                    saved_count += 1
                else:
                    failed_tickers.append(t)
            else:
                raw_bulk = yf.download(
                    tickers=chunk,
                    start=start_date,
                    end=end_date,
                    group_by="ticker",
                    auto_adjust=True,
                    threads=True,
                    progress=False,
                )
                for t in chunk:
                    try:
                        if isinstance(raw_bulk.columns, pd.MultiIndex):
                            if t in raw_bulk.columns.get_level_values(0):
                                sub_df = raw_bulk[t]
                            else:
                                sub_df = pd.DataFrame()
                        else:
                            sub_df = raw_bulk
                        info = {"sector": sectors_map.get(t)} if t in sectors_map else {}
                        if save_ticker_to_cache(t, sub_df, info=info, cache_dir=cache_dir):
                            saved_count += 1
                        else:
                            failed_tickers.append(t)
                    except Exception:
                        failed_tickers.append(t)
        except Exception as exc:
            print(f"    [!] Grup indirme uyarısı: {exc}")
            for t in chunk:
                failed_tickers.append(t)

    # Toplu indirmede zaman aşımına uğrayan sembolleri tekil olarak yeniden dene
    if failed_tickers:
        still_failed: list[str] = []
        for t in failed_tickers:
            try:
                df, info = fetch_and_cache_ticker(
                    t, start_date=start_date, end_date=end_date, cache_dir=cache_dir, fetch_info=False
                )
                if not df.empty:
                    if t in sectors_map:
                        info["sector"] = sectors_map[t]
                        save_ticker_to_cache(t, df, info=info, cache_dir=cache_dir)
                    saved_count += 1
                else:
                    still_failed.append(t)
            except Exception:
                still_failed.append(t)
        failed_tickers = still_failed

    manifest = {
        "updated_at": datetime.now().isoformat(),
        "start_date": start_date,
        "end_date": end_date,
        "total_requested": len(unique_tickers),
        "cached_already": cached_already,
        "newly_saved": saved_count,
        "failed_tickers": failed_tickers,
    }
    manifest_path = cache_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest


def get_answer_key_window(
    ticker: str,
    start_date_exclusive: str | date,
    end_date_inclusive: str | date,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
) -> pd.DataFrame:
    """
    CEVAP ANAHTARI SORGUSU:
    Yalnızca simülasyon yürütücüsü (`backtest_step.py`) tarafından iki simülasyon adımı arasındaki
    `(start_date_exclusive, end_date_inclusive]` günlerinde Stop-Loss veya Take-Profit patlayıp
    patlamadığını kontrol etmek için kullanılır.
    """
    df, _ = get_cached_or_fetch_ticker(
        ticker,
        as_of_date=None,
        cache_dir=cache_dir,
        allow_network=allow_network,
        max_lookback_bars=None,
    )
    if df.empty:
        return pd.DataFrame()

    start_str = (
        start_date_exclusive.strftime("%Y-%m-%d")
        if isinstance(start_date_exclusive, (date, datetime))
        else str(start_date_exclusive)[:10]
    )
    end_str = (
        end_date_inclusive.strftime("%Y-%m-%d")
        if isinstance(end_date_inclusive, (date, datetime))
        else str(end_date_inclusive)[:10]
    )
    start_ts = pd.Timestamp(start_str)
    end_ts = pd.Timestamp(end_str)

    return df.loc[(df.index > start_ts) & (df.index <= end_ts)].copy()


def check_sl_tp_in_window(
    ticker: str,
    stop_loss: float | None,
    take_profit: float | None,
    start_date_exclusive: str | date,
    end_date_inclusive: str | date,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
) -> dict[str, Any]:
    """
    Açık bir pozisyonun `(start_date_exclusive, end_date_inclusive]` tarih aralığındaki
    her bir işlem gününü Cevap Anahtarından kronolojik olarak tarar:
    - Eğer o günkü `Low <= stop_loss` ise pozisyon Stop-Loss ile tetiklenir (muhafazakar kural:
      aynı gün hem SL hem TP değmişse önce Stop-Loss kabul edilir; açılış boşluklu (gap-down)
      ise `min(Open, stop_loss)` fiyatından çıkar).
    - Eğer `High >= take_profit` ise pozisyon Take-Profit ile tetiklenir (gap-up açılış varsa
      `max(Open, take_profit)` fiyatından çıkar).
    """
    window = get_answer_key_window(
        ticker,
        start_date_exclusive=start_date_exclusive,
        end_date_inclusive=end_date_inclusive,
        cache_dir=cache_dir,
        allow_network=allow_network,
    )
    if window.empty:
        return {"triggered": False, "trigger_type": None, "trigger_date": None, "execution_price": None, "last_close": None}

    sl = float(stop_loss) if stop_loss is not None and stop_loss > 0 else None
    tp = float(take_profit) if take_profit is not None and take_profit > 0 else None

    for idx, row in window.iterrows():
        d_str = _bar_date_str(idx)
        bar_open = float(row["Open"])
        bar_high = float(row["High"])
        bar_low = float(row["Low"])

        # 1. Önce Stop-Loss kontrolü (muhafazakar risk yönetimi)
        if sl is not None and bar_low <= sl:
            exec_price = round(min(bar_open, sl), 2) if bar_open < sl else round(sl, 2)
            return {
                "triggered": True,
                "trigger_type": "STOP_LOSS",
                "trigger_date": d_str,
                "execution_price": exec_price,
                "last_close": round(float(row["Close"]), 2),
            }

        # 2. Take-Profit kontrolü
        if tp is not None and bar_high >= tp:
            exec_price = round(max(bar_open, tp), 2) if bar_open > tp else round(tp, 2)
            return {
                "triggered": True,
                "trigger_type": "TAKE_PROFIT",
                "trigger_date": d_str,
                "execution_price": exec_price,
                "last_close": round(float(row["Close"]), 2),
            }

    last_close = round(float(window["Close"].iloc[-1]), 2)
    return {
        "triggered": False,
        "trigger_type": None,
        "trigger_date": None,
        "execution_price": None,
        "last_close": last_close,
    }


def get_trading_days(
    start_date: str = DEFAULT_SIM_START,
    end_date: str = DEFAULT_SIM_END,
    cache_dir: Path = BACKTEST_CACHE_DIR,
    allow_network: bool = True,
) -> list[str]:
    """
    `SPY` endeks barlarını baz alarak `[start_date, end_date]` aralığındaki gerçek ABD borsa
    iş günlerini (resmi tatiller ve haftasonları elenmiş olarak) döndürür.
    """
    spy_df, _ = get_cached_or_fetch_ticker(
        "SPY",
        as_of_date=None,
        cache_dir=cache_dir,
        allow_network=allow_network,
        max_lookback_bars=None,
    )
    start_str = str(start_date)[:10]
    end_str = str(end_date)[:10]

    if not spy_df.empty:
        dates = [_bar_date_str(i) for i in spy_df.index]
        return [d for d in dates if start_str <= d <= end_str]

    # Çevrimdışı / yedek takvim (hafta içi günler)
    cur = date.fromisoformat(start_str)
    end_dt = date.fromisoformat(end_str)
    fallback_days: list[str] = []
    fixed_holidays = {(1, 1), (6, 19), (7, 4), (12, 25)}
    while cur <= end_dt:
        if cur.weekday() < 5 and (cur.month, cur.day) not in fixed_holidays:
            fallback_days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return fallback_days


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest Cevap Anahtarı Deposu ve Veri Önbellek Motoru")
    parser.add_argument(
        "--tickers",
        nargs="*",
        help="Önbelleğe indirilecek semboller (örn. SPY AAPL MSFT). Belirtilmezse SPY ve örnek evren indirilir.",
    )
    parser.add_argument(
        "--all-universe",
        action="store_true",
        help="data/universe.json içindeki tüm 500 S&P 500 hissesini + SPY'ı toplu indirir.",
    )
    parser.add_argument("--start", default=DEFAULT_CACHE_START, help=f"Başlangıç tarihi (Varsayılan: {DEFAULT_CACHE_START})")
    parser.add_argument("--end", default=DEFAULT_CACHE_END, help=f"Bitiş tarihi (Varsayılan: {DEFAULT_CACHE_END})")
    parser.add_argument("--force", action="store_true", help="Mevcut önbelleği ezerek yeniden indirir.")
    parser.add_argument("--cache-dir", type=Path, default=BACKTEST_CACHE_DIR, help="Önbellek klasörü yolu.")
    args = parser.parse_args()

    sectors_map: dict[str, str] = {}
    universe_tickers: list[str] = []
    if UNIVERSE_FILE.exists():
        with UNIVERSE_FILE.open("r", encoding="utf-8") as f:
            u_data = json.load(f)
            universe_tickers = u_data.get("tickers", [])
            sectors_map = u_data.get("sectors", {})

    if args.all_universe:
        target_tickers = ["SPY"] + universe_tickers
    elif args.tickers:
        target_tickers = ["SPY"] + list(args.tickers)
    else:
        # Varsayılan: SPY + açık pozisyon/izleme listesi + ilk 25 likit hisse
        target_tickers = ["SPY"] + universe_tickers[:25]

    print("=" * 60)
    print("Cevap Anahtarı Deposu — Tarihsel Veri Önbellekleme Motoru")
    print("=" * 60)
    print(f"[*] Önbellek Dizini : {args.cache_dir}")
    print(f"[*] Tarih Aralığı   : {args.start} -> {args.end}")
    print(f"[*] Hedef Semboller : {len(set(target_tickers))} adet")

    manifest = download_batch_to_cache(
        target_tickers,
        start_date=args.start,
        end_date=args.end,
        cache_dir=args.cache_dir,
        force=args.force,
        sectors_map=sectors_map,
    )
    print(f"\n[✓] Önbellekleme tamamlandı:")
    print(f"    - Zaten Önbellekte : {manifest['cached_already']}")
    print(f"    - Yeni İndirilen   : {manifest['newly_saved']}")
    print(f"    - Başarısız        : {len(manifest['failed_tickers'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

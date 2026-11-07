#!/usr/bin/env python3
"""
src/update_universe.py
Otonom Borsa Orkestrası — S&P 500 Evren Güncelleyici ve Ticker Normalizasyon Motoru

Görevler:
1. Güncel S&P 500 bileşenlerini (Wikipedia S&P 500 tablosu veya açık veri kaynağından) çekmek.
2. Sembolleri yfinance formatına normalize etmek (ör. BRK.B -> BRK-B, BF.B -> BF-B, boşluk temizliği).
3. Aynı şirketin mükerrer pay sınıflarından ikincil olanları (GOOG, FOX, NWS) eleyip tekilleştirmek.
4. data/universe.json dosyasını ~500 hisse ve GICS sektör bilgileriyle atomik olarak güncellemek.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.paths import UNIVERSE_FILE

# Aynı şirketin S&P 500'de yer alan ikincil pay sınıfları:
# Alphabet: GOOGL (tutulur) / GOOG (elenir)
# Fox Corp: FOXA (tutulur) / FOX (elenir)
# News Corp: NWSA (tutulur) / NWS (elenir)
SECONDARY_SHARE_CLASSES: set[str] = {"GOOG", "FOX", "NWS"}

WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
GITHUB_SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
)

# Çevrimdışı / Sandbox yedek S&P 500 bileşenleri ve GICS sektör haritası (500 tekil şirket)
EMBEDDED_SP500_SECTORS: dict[str, list[str]] = {
    "Information Technology": [
        "AAPL", "ACN", "ADBE", "ADI", "ADP", "ADSK", "AKAM", "AMAT", "AMD", "ANET",
        "ANSS", "APH", "APTV", "AVGO", "CDNS", "CDW", "CRM", "CRWD", "CSCO", "CTSH",
        "DELL", "ENPH", "EPAM", "FFIV", "FICO", "FSLR", "FTNT", "GDDY", "GEN", "GLW",
        "HPE", "HPQ", "IBM", "INTC", "INTU", "IT", "JBL", "KEYS", "KLAC", "LDOS",
        "LRCX", "MCHP", "MPWR", "MSFT", "MSI", "MU", "NOW", "NTAP", "NVDA", "NXPI",
        "ON", "ORCL", "PANW", "PLTR", "PTC", "QCOM", "QRVO", "ROP", "SMCI", "SNPS",
        "STX", "SWKS", "TDY", "TEL", "TER", "TRMB", "TXN", "TYL", "UBER", "VRSN",
        "WDC", "WDAY", "ZBRA",
    ],
    "Financials": [
        "ACGL", "AFL", "AIG", "AIZ", "AJG", "ALL", "AMP", "AON", "APO", "AXP",
        "BAC", "BEN", "BK", "BLK", "BRK.B", "BX", "C", "CB", "CBOE", "CFG",
        "CINF", "CME", "COF", "COR", "CPAY", "DFS", "EG", "ERIE", "FDS", "FI",
        "FIS", "FITB", "GPN", "GS", "HBAN", "HIG", "ICE", "IVZ", "JKHY", "JPM",
        "KEY", "KKR", "L", "MA", "MCO", "MET", "MKTX", "MMC", "MS", "MSCI",
        "MTB", "NDAQ", "NTRS", "PFG", "PGR", "PNC", "PRU", "PYPL", "RF", "RJF",
        "SCHW", "SPGI", "STT", "SYF", "TFC", "TROW", "TRV", "USB", "V", "WFC",
        "WRB", "WTW",
    ],
    "Health Care": [
        "A", "ABBV", "ABT", "ALGN", "AMGN", "BAX", "BDX", "BIIB", "BMY", "BSX",
        "CAH", "CI", "CNC", "COO", "CRL", "CVS", "DGX", "DHR", "DXCM", "ELV",
        "EW", "GEHC", "GILD", "HCA", "HOLX", "HSIC", "HUM", "IDXX", "INCY", "IQV",
        "ISRG", "JNJ", "LH", "LLY", "MCK", "MDT", "MOH", "MRK", "MRNA", "MTD",
        "PFE", "PODD", "REGN", "RMD", "RVTY", "SOLV", "STE", "SYK", "TECH", "TMO",
        "UHS", "UNH", "VRTX", "VTRS", "WAT", "WST", "ZBH", "ZTS",
    ],
    "Consumer Discretionary": [
        "ABNB", "AMZN", "AZO", "BBY", "BKNG", "BLDR", "BWA", "CCL", "CMG", "CZR",
        "DECK", "DHI", "DPZ", "DRI", "EBAY", "EXPE", "F", "GM", "GPC", "GRMN",
        "HAS", "HD", "HLT", "KMX", "LEN", "LKQ", "LOW", "LULU", "LVS", "MAR",
        "MCD", "MGM", "MHK", "NCLH", "NKE", "NVR", "ORLY", "PHM", "POOL", "RCL",
        "RL", "ROST", "SBUX", "TJX", "TPR", "TSCO", "TSLA", "ULTA", "WSM", "WYNN",
        "YUM",
    ],
    "Industrials": [
        "ADP", "ALLE", "AME", "AOS", "AXON", "BA", "BR", "CARR", "CAT", "CHRW",
        "CMI", "CPRT", "CSX", "CTAS", "DAL", "DAY", "DE", "DOV", "EFX", "EME",
        "EMR", "ETN", "EXPD", "FAST", "FDX", "FTV", "GD", "GE", "GEV", "GNRC",
        "GWW", "HII", "HON", "HUBB", "HWM", "IEX", "IR", "ITW", "J", "JBHT",
        "JCI", "LDOS", "LHX", "LII", "LMT", "LUV", "MAS", "MMM", "NDSN", "NOC",
        "NSC", "ODFL", "OTIS", "PAYC", "PAYX", "PCAR", "PH", "PNR", "PWR", "ROK",
        "ROL", "RSG", "RTX", "SNA", "SWK", "TDG", "TT", "TXT", "UAL", "UNP",
        "UPS", "URI", "VLTO", "VRSK", "WAB", "WM", "XYL",
    ],
    "Communication Services": [
        "CHTR", "CMCSA", "DIS", "EA", "FOXA", "FOX", "GOOGL", "GOOG", "IPG", "LYV",
        "META", "MTCH", "NFLX", "NWSA", "NWS", "OMC", "PARA", "T", "TMUS", "TTWO",
        "VZ", "WBD",
    ],
    "Consumer Staples": [
        "ADM", "BF.B", "BG", "CAG", "CHD", "CL", "CLX", "COST", "CPB", "DG",
        "DLTR", "EL", "GIS", "HRL", "HSY", "K", "KDP", "KHC", "KMB", "KO",
        "KR", "KVUE", "LW", "MDLZ", "MKC", "MNST", "MO", "PEP", "PG", "PM",
        "SJM", "STZ", "SYY", "TAP", "TGT", "TSN", "WBA", "WMT",
    ],
    "Energy": [
        "APA", "BKR", "COP", "CTRA", "CVX", "DVN", "EOG", "EQT", "FANG", "HAL",
        "HES", "KMI", "MPC", "MRO", "OKE", "OXY", "PSX", "SLB", "TPL", "TRGP",
        "VLO", "WMB", "XOM",
    ],
    "Utilities": [
        "AEE", "AEP", "AES", "ATO", "AWK", "CEG", "CMS", "CNP", "D", "DTE",
        "DUK", "ED", "EIX", "ES", "ETR", "EVRG", "EXC", "FE", "LNT", "NEE",
        "NI", "NRG", "PCG", "PEG", "PNW", "PPL", "SO", "SRE", "VST", "WEC",
        "XEL",
    ],
    "Real Estate": [
        "ARE", "AVB", "BXP", "CBRE", "CCI", "CPT", "CSGP", "DLR", "DOC", "EQIX",
        "EQR", "ESS", "EXR", "FRT", "HST", "INVH", "IRM", "KIM", "MAA", "O",
        "PLD", "PSA", "REG", "SBAC", "SPG", "UDR", "VICI", "VTR", "WELL", "WY",
    ],
    "Materials": [
        "ALB", "AMCR", "APD", "AVY", "BALL", "CE", "CF", "CTVA", "DD", "DOW",
        "ECL", "EMN", "FCX", "FMC", "IFF", "IP", "LIN", "LYB", "MLM", "MOS",
        "NEM", "NUE", "PKG", "PPG", "SHW", "SMG", "STLD", "SW", "VMC", "WRK",
    ],
}

# 500 hisse barajını tam karşılamak için ek S&P 500 / likit ABD bileşenleri
ADDITIONAL_SP500_CONSTITUENTS: list[tuple[str, str]] = [
    ("AAL", "Industrials"),
    ("AAP", "Consumer Discretionary"),
    ("ALK", "Industrials"),
    ("ALLE", "Industrials"),
    ("AMTM", "Industrials"),
    ("AOS", "Industrials"),
    ("APG", "Industrials"),
    ("ARES", "Financials"),
    ("ARMK", "Consumer Discretionary"),
    ("ASML", "Information Technology"),
    ("AXON", "Industrials"),
    ("BIO", "Health Care"),
    ("BMRN", "Health Care"),
    ("BRO", "Financials"),
    ("BURL", "Consumer Discretionary"),
    ("CAR", "Industrials"),
    ("CASE", "Industrials"),
    ("CBOE", "Financials"),
    ("CDAY", "Information Technology"),
    ("CEG", "Utilities"),
    ("CHWY", "Consumer Discretionary"),
    ("CIEN", "Information Technology"),
    ("CLF", "Materials"),
    ("CNM", "Industrials"),
    ("COIN", "Financials"),
    ("COKE", "Consumer Staples"),
    ("COO", "Health Care"),
    ("CPRI", "Consumer Discretionary"),
    ("CRH", "Materials"),
    ("CSL", "Industrials"),
    ("CTLT", "Health Care"),
    ("CYBR", "Information Technology"),
    ("DAR", "Consumer Staples"),
    ("DASH", "Consumer Discretionary"),
    ("DDOG", "Information Technology"),
    ("DKS", "Consumer Discretionary"),
    ("DLB", "Information Technology"),
    ("DOCU", "Information Technology"),
    ("DOX", "Information Technology"),
    ("DT", "Information Technology"),
    ("DXC", "Information Technology"),
    ("ehc", "Health Care"),
    ("ELANCO", "Health Care"),
    ("ENTG", "Information Technology"),
    ("EPAM", "Information Technology"),
    ("ESAB", "Industrials"),
    ("ESTC", "Information Technology"),
    ("ETSY", "Consumer Discretionary"),
    ("EVR", "Financials"),
    ("EXAS", "Health Care"),
    ("EXEL", "Health Care"),
    ("EXP", "Materials"),
    ("FBIN", "Industrials"),
    ("FCN", "Industrials"),
    ("FHN", "Financials"),
    ("FIVE", "Consumer Discretionary"),
    ("FIX", "Industrials"),
    ("FLEX", "Information Technology"),
    ("FLO", "Consumer Staples"),
    ("FLR", "Industrials"),
    ("FLT", "Financials"),
    ("FND", "Consumer Discretionary"),
    ("FNF", "Financials"),
    ("FORM", "Information Technology"),
    ("FR", "Real Estate"),
]


class _WikipediaTableParser(HTMLParser):
    """Wikipedia S&P 500 tablosundaki ('constituents') satır ve hücreleri ayrıştırır."""

    def __init__(self) -> None:
        super().__init__()
        self.in_constituents_table = False
        self.in_tr = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.current_row: list[str] = []
        self.current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "table" and attr_dict.get("id") == "constituents":
            self.in_constituents_table = True
        elif self.in_constituents_table and tag == "tr":
            self.in_tr = True
            self.current_row = []
        elif self.in_tr and tag in ("td", "th"):
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_constituents_table and tag == "table":
            self.in_constituents_table = False
        elif self.in_tr and tag == "tr":
            self.in_tr = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif self.in_cell and tag in ("td", "th"):
            self.in_cell = False
            cell_text = "".join(self.current_cell).strip()
            self.current_row.append(cell_text)

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def normalize_ticker(ticker: str) -> str:
    """
    Sembolü yfinance formatına normalize eder:
    - Baş/son boşlukları temizler ve büyük harfe çevirir
    - Nokta (.) karakterini tire (-) karakterine dönüştürür (BRK.B -> BRK-B, BF.B -> BF-B)
    """
    if not ticker:
        return ""
    cleaned = str(ticker).strip().upper()
    cleaned = cleaned.replace(".", "-")
    cleaned = re.sub(r"[^A-Z0-9\-]", "", cleaned)
    return cleaned


def normalize_and_deduplicate_constituents(
    raw_items: list[dict[str, str]],
) -> tuple[list[str], dict[str, str], list[dict[str, str]]]:
    """
    Ham hisse listesini normalize eder, ikincil pay sınıflarını (GOOG, FOX, NWS) eler
    ve mükerrer sembolleri tekilleştirir.
    """
    tickers: list[str] = []
    sectors: dict[str, str] = {}
    constituents: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in raw_items:
        raw_t = item.get("ticker", "")
        norm_t = normalize_ticker(raw_t)
        if not norm_t:
            continue
        if norm_t in SECONDARY_SHARE_CLASSES:
            continue
        if norm_t in seen:
            continue

        seen.add(norm_t)
        sector = str(item.get("sector") or "Unknown").strip()
        name = str(item.get("name") or norm_t).strip()
        tickers.append(norm_t)
        sectors[norm_t] = sector
        constituents.append({
            "ticker": norm_t,
            "name": name,
            "sector": sector,
        })

    return tickers, sectors, constituents


def fetch_sp500_from_wikipedia(timeout: int = 10) -> list[dict[str, str]]:
    """Wikipedia S&P 500 tablosundan hisse ve GICS sektör bilgilerini çeker."""
    req = urllib.request.Request(
        WIKIPEDIA_SP500_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html_text = resp.read().decode("utf-8", errors="replace")

    parser = _WikipediaTableParser()
    parser.feed(html_text)
    if len(parser.rows) < 400:
        raise ValueError(f"Wikipedia tablosundan beklenen satır sayısı okunamadı ({len(parser.rows)}).")

    items: list[dict[str, str]] = []
    for row in parser.rows[1:]:
        if len(row) >= 3:
            items.append({
                "ticker": row[0],
                "name": row[1],
                "sector": row[2],
            })
    return items


def fetch_sp500_from_github_csv(timeout: int = 10) -> list[dict[str, str]]:
    """Açık kaynak GitHub S&P 500 CSV veri setinden bileşenleri çeker."""
    req = urllib.request.Request(
        GITHUB_SP500_CSV_URL,
        headers={"User-Agent": "Mozilla/5.0 (Trader-SP500-Updater/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        csv_text = resp.read().decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text))
    items: list[dict[str, str]] = []
    for row in reader:
        sym = row.get("Symbol") or row.get("symbol") or ""
        sec = row.get("GICS Sector") or row.get("Sector") or "Unknown"
        name = row.get("Security") or row.get("Name") or sym
        if sym:
            items.append({"ticker": sym, "name": name, "sector": sec})
    if len(items) < 400:
        raise ValueError(f"GitHub CSV kaynağından yeterli hisse okunamadı ({len(items)}).")
    return items


def get_embedded_sp500_fallback() -> list[dict[str, str]]:
    """Ağ erişimi olmadığında veya sandbox ortamında kullanılan yerleşik S&P 500 + GICS sektör listesi."""
    items: list[dict[str, str]] = []
    for sector, sym_list in EMBEDDED_SP500_SECTORS.items():
        for sym in sym_list:
            items.append({"ticker": sym, "name": sym, "sector": sector})
    for sym, sector in ADDITIONAL_SP500_CONSTITUENTS:
        items.append({"ticker": sym, "name": sym, "sector": sector})
    return items


def build_sp500_universe() -> tuple[dict[str, Any], str]:
    """
    Sırasıyla Wikipedia, GitHub açık veri seti ve yerleşik S&P 500 listesini deneyerek
    normalize edilmiş ve tekilleştirilmiş ~500 hisselik evren verisini üretir.
    """
    raw_items: list[dict[str, str]] = []
    source_used = "EMBEDDED_SP500_SNAPSHOT"

    try:
        raw_items = fetch_sp500_from_wikipedia(timeout=8)
        source_used = WIKIPEDIA_SP500_URL
    except Exception:
        try:
            raw_items = fetch_sp500_from_github_csv(timeout=8)
            source_used = GITHUB_SP500_CSV_URL
        except Exception:
            raw_items = get_embedded_sp500_fallback()
            source_used = "EMBEDDED_SP500_SNAPSHOT"

    tickers, sectors, constituents = normalize_and_deduplicate_constituents(raw_items)

    # Eğer çekilen listede 490'dan az hisse varsa yerleşik listeyle 500 hisseye tamamla
    if len(tickers) < 490:
        fallback_items = get_embedded_sp500_fallback()
        tickers, sectors, constituents = normalize_and_deduplicate_constituents(raw_items + fallback_items)
        tickers = tickers[:500]
        constituents = constituents[:500]
        sectors = {c["ticker"]: c["sector"] for c in constituents}
    elif source_used == "EMBEDDED_SP500_SNAPSHOT" and len(tickers) > 500:
        tickers = tickers[:500]
        constituents = constituents[:500]
        sectors = {c["ticker"]: c["sector"] for c in constituents}

    payload = {
        "market": "US_SP500",
        "updated_at": datetime.now().isoformat(),
        "source": source_used,
        "total_count": len(tickers),
        "excluded_secondary_classes": sorted(SECONDARY_SHARE_CLASSES),
        "tickers": tickers,
        "sectors": sectors,
        "constituents": constituents,
    }
    return payload, source_used


def save_universe_atomic(filepath: Path, data: dict[str, Any]) -> None:
    """universe.json dosyasını önce .tmp olarak yazıp ardından atomik olarak taşır."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_name(f"{filepath.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, filepath)


def main(target_file: Path | None = None) -> int:
    out_path = target_file or UNIVERSE_FILE
    print("=" * 60)
    print("S&P 500 Evren Güncelleyici (src/update_universe.py)")
    print("=" * 60)

    payload, source_used = build_sp500_universe()
    save_universe_atomic(out_path, payload)

    tickers = payload["tickers"]
    sectors = payload["sectors"]
    unique_sectors = sorted(set(sectors.values()))

    print(f"[*] Kaynak: {source_used}")
    print(f"[✓] Normalize edilen ve tekilleştirilen hisse sayısı: {len(tickers)}")
    print(f"[✓] Elenen ikincil pay sınıfları: {', '.join(payload['excluded_secondary_classes'])}")
    print(f"[✓] GICS Sektör Sayısı: {len(unique_sectors)} ({', '.join(unique_sectors[:5])}...)")
    print(f"[✓] Örnek normalize semboller: BRK-B={('BRK-B' in tickers)}, BF-B={('BF-B' in tickers)}")
    print(f"[✓] Evren dosyası güncellendi: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

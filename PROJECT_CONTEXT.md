# PROJE ANAYASASI: Otonom Borsa Orkestrası (Paper Trading)

Bu belge, konuşma geçmişi sıfırlansa veya model bağlamı kaybetse bile projenin mimarisini, kurallarını ve sınırlarını korumak için oluşturulmuş **Tek Doğruluk Kaynağıdır (Single Source of Truth)**.

---

## 1. Proje Özeti ve Amaç
- **Temel Altyapı:** `tradermonty/claude-trading-skills` GitHub reposundaki 11 ajanlık yatırım komitesi mimarisi ve analiz becerileri (skills).
- **Amaç:** Belirli periyotlarla ABD borsasındaki hisseleri tarayan, açık pozisyonları ve izleme listesini takip eden, 11 ajanın ortak kararıyla sanal al-sat (Paper Trading) yapan yerel bir finans orkestrası kurmak.
- **Çalışma Ortamı:** Fedora Linux (Yerel sistem).
- **LLM & Kota Yönetimi:** Harici ücretli API anahtarı KULLANILMAYACAK. Tüm model/ajan çıkarımları kullanıcının **Gemini Pro** aboneliğinin tanımladığı **Antigravity (AGY)** kullanım kotası üzerinden yürütülecek.
- **Geliştirme Yöntemi:** Mimari adımlar kullanıcı ile adım adım el ile kurulacak; tekrarlayan kod yazımı ve şablon dönüştürme gibi angarya işler Antigravity'ye (AGY) yaptırılacak.

---

## 2. Kasa, Pazar ve Komisyon Kuralları (Simülasyon)
- **Hedef Pazar:** ABD Borsaları (S&P 500 / NASDAQ likit hisseleri). *(Veri kalitesi ve `tradermonty` uyumu nedeniyle ABD ile başlanmıştır; verim alınamazsa BIST 100'e geçilecektir).*
- **Başlangıç Sanal Bakiyesi:** **3.500 $** (~120.000 TL karşılığı).
- **Maksimum Pozisyon Büyüklüğü:** Kasanın en fazla **%20'si** (başlangıçta maksimum 700 $) tek bir hisseye yatırılabilir.
- **Komisyon Kuralı (Midas Tarifesi):** Gerçekçilik için her **AL (BUY)** ve her **SAT (SELL)** işleminde kasadan sabit **1.50 $** işlem komisyonu düşülür.

---

## 3. Çalışma Döngüsü ve Kota Koruma Kuralı (X ve Y Parametreleri)
- **Çalışma Sıklığı (X):** Başlangıçta günde 1 kez (ABD borsası kapanışı sonrası) manuel tetiklenecek; sistem stabil olunca Linux script/otomasyon ile periyodik hale getirilecek.
- **Tek Seferde Maksimum Analiz Limiti (Y = 5):** Antigravity kotasını tek seferde bitirmemek için her çalışmada **TOPLAM MAKSİMUM 5 HİSSE** analiz edilir.
- **5 Hissenin Öncelik Sırası (Queue):**
  1. **Açık Pozisyonlar (`open_positions`):** Eldeki hisseler kontrol edilir (Stop-Loss patladı mı, Take-Profit geldi mi, trend döndü mü -> `SELL` veya `HOLD`).
  2. **İzleme Listesi (`watchlist`):** Daha önce "Almak için bekle" (`WAIT_BUY`) denilen hisseler kontrol edilir (Hedef giriş fiyatına geldi mi -> `BUY`, `WAIT` veya `DROP`).
  3. **Yeni Keşif (`random_discovery`):** İlk iki maddeden arta kalan kontenjan kadar (`5 - (açık_pozisyon + watchlist)`) rastgele yeni ABD hissesi havuzdan çekilip analiz edilir.

---

## 4. İzleme Listesi (Watchlist) Temizlik Kuralları
İzleme listesinin şişip 5 hisselik kotayı kilitlememesi için otomatik temizlik kuralları:
1. **Zaman Aşımı (TTL):** İzleme listesine giren bir hisse **14 gün** içinde hedef alım seviyesine gelmezse listeden otomatik silinir (`EXPIRED`).
2. **Trend Bozulması:** Komite tekrar baktığında hissenin kritik destek seviyesini kırdığını veya temel/teknik görünümünün bozulduğunu tespit ederse listeden çıkarır (`INVALIDATED`).

---

## 5. Veri Saklama Yapısı (`state.json`)
Tüm hafıza yerel diskte tek bir `state.json` dosyasında tutulur. Şema yapısı:
- `portfolio_summary`: `cash_usd`, `total_equity_usd`, `total_fees_paid_usd`, `last_run_timestamp`
- `open_positions`: `[ { ticker, shares, avg_buy_price, current_price, stop_loss, take_profit, buy_date, thesis } ]`
- `watchlist`: `[ { ticker, added_date, expires_date, target_entry_price, stop_loss_plan, status, reason } ]`
- `trade_history`: `[ { date, ticker, action (BUY/SELL), shares, price, fee_usd, pnl_usd, committee_summary } ]`

---

## 6. Adım Adım Kurulum Yol Haritası
- [x] **Adım 1:** Proje dizininin oluşturulması ve `tradermonty/claude-trading-skills` reposunun klonlanıp incelenmesi.
- [x] **Adım 2:** `state.json` başlangıç dosyasının (3.500 $ bakiye ile) ve S&P 500 hisse havuzu listesinin oluşturulması.
- [x] **Adım 3:** Veri çekme script'inin (`yfinance` vb.) hazırlanması: 5 hisseyi seçip güncel fiyat, indikatör (RSI, SMA, MACD) ve temel verilerini tek bir özet dosyaya döken Python betiği (`prepare_daily_batch.py`).
- [x] **Adım 4:** `tradermonty` içindeki ajan kurallarının Antigravity'nin tek seferde okuyup `state.json` dosyasını güncelleyebileceği orkestra yapısına bağlanması (`COMMITTEE_PROMPT.md` ve `execute_decisions.py`).
- [x] **Adım 5:** İlk 5 hisselik kuru çalıştırma (Dry Run) ve `state.json` güncelleme testi (`daily_briefing.json` üretimi tamamlandı).


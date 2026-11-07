# 🤖 CLAUDE.md — Kalıcı Ajan Hafıza ve Mimari Kılavuzu

Bu belge, Otonom Borsa Orkestrası (Paper Trading) projesi üzerinde çalışan tüm yapay zeka ajanlarının (Antigravity / Claude) her oturum başında ilk okuyacağı ve %100 uymakla yükümlü olduğu **Operasyonel ve Mimari Referans Kılavuzudur**.

---

## 1. PROJE KİMLİĞİ & MODÜLER DİZİN YAPISI

- **Çalışma Dizini:** `/home/memin/Projects/Trader`
- **Python Çalışma Ortamı:** `/home/memin/Projects/Trader/.venv/bin/python` (Tüm betikler ve testler bu sanal ortam üzerinden çalıştırılır).
- **Veri Kaynağı Kuralı:** Harici ücretli API anahtarları (FMP, Finviz Elite vb.) **KESİNLİKLE KULLANILMAZ**. Piyasa, fiyat, hacim ve temel rasyo verilerinin tek kaynağı `yfinance` kütüphanesidir.
- **Modüler Klasör ve Dosya Yapısı:**
  - **Kök Dizin (`/home/memin/Projects/Trader`):**
    - `README.md`: Kullanıcı dostu proje özeti ve ilerleme durumu.
    - `AGENTS.md` & `CLAUDE.md`: Ajanların oturum başında otomatik okuduğu mimari kılavuz.
  - **`src/` (Kaynak Kodlar):**
    - `src/paths.py`: Tüm dosya yollarını çalışma dizininden bağımsız (`CWD-independent`) çözümleyen merkezi modül.
    - `src/prepare_daily_batch.py`: Günlük izleme listesi temizliği, 5 hisselik öncelikli kuyruk oluşturma, `yfinance` veri çekimi ve `data/daily_briefing.json` üretim motoru.
    - `src/execute_decisions.py`: Komite kararlarını (`data/decisions.json`) icra eden, portföy muhasebesini yürüten, `data/state.json`, `docs/PORTFOLIO_DASHBOARD.md` ve `docs/dashboard.html` dosyalarını güncelleyen yürütücü.
    - `src/ui_dashboard.py`: 11 ajan karar karnesini sentezleyen, Markdown/ASCII (`docs/PORTFOLIO_DASHBOARD.md`) ve yerel interaktif HTML (`docs/dashboard.html`) panolarını üreten ve canlı mod gizlilik kalkanını (`Privacy Mode` / `LIVE`) uygulayan UI motoru.
  - **`data/` (Canlı Hafıza ve Veri Dosyaları):**
    - `data/state.json`: Portföy bakiyesi, açık pozisyonlar, izleme listesi ve işlem geçmişini tutan canlı hafıza dosyası.
    - `data/universe.json`: Keşif için taranan likit ABD hisseleri (S&P 500 / NASDAQ) havuzu.
    - `data/daily_briefing.json`: Günlük 5 aday hissenin teknik, temel ve risk/boyutlandırma verilerini içeren brifing paketi.
    - `data/decisions.json`: 11 adımlı komitenin ürettiği günlük işlem kararları.
  - **`docs/` (Anayasa, Panolar ve Şartnameler):**
    - `docs/PORTFOLIO_DASHBOARD.md`: İnsan tarafından okunabilir güncel portföy ve 11 ajan performans gösterge paneli (`LIVE` modda kişisel rakamlar maskelenir).
    - `docs/dashboard.html`: `.gitignore` korumasında yalnızca yerel bilgisayarda çalışan, sunucusuz interaktif HTML5 gösterge paneli.
    - `docs/Kanban.md`: Proje görevlerinin ve geliştirme adımlarının takip edildiği canlı Kanban panosu.
    - `docs/PROJECT_CONTEXT.md`: Projenin kuruluş anayasası ve tek doğruluk kaynağı.
    - `docs/COMMITTEE_PROMPT.md`: 11 ajanlık yatırım komitesinin karar süzgeci ve `decisions.json` üretim kuralları.
    - `docs/test_senaryolari.md`: 21 senaryolu resmi QA ve test şartnamesi.
  - **`tests/` (Doğrulama ve QA Test Paketi):**
    - `tests/validate_system.py`: Gerçek dosyalara dokunmadan (`Zero-Touch SHA-256`) izole geçici dosyalar üzerinde çalışan 21 senaryolu kapsamlı doğrulama test paketi.

---

## 2. KASA VE MUHASEBE KURALLARI (DOKUNULMAZ)

- **Başlangıç Sermayesi:** `3.500,00 $`
- **İşlem Komisyonu (Midas Tarifesi):** Her `BUY` (Alım) ve her `SELL` (Satım) işleminde kasadan sabit **`1.50 $`** komisyon düşülür (Tam kapanan bir işlem döngüsünde toplam `3.00 $` komisyon ödenir).
- **Maksimum Pozisyon Tavanı (%20 Kuralı):** Tek bir hisseye toplam portföy varlığının (`total_equity_usd`) en fazla **%20'si** yatırılabilir. Bu sınır **asla esnetilemez** (`* 1.02` gibi tolerans payları kesinlikle yasaktır). Aynı hissede mevcut açık pozisyon varsa, ek alımlarda mevcut pozisyon büyüklüğü %20 tavanından düşülür.
- **Pay Yuvarlama ve Eksi Bakiye Yasağı:**
  - Alım adedi hesaplanırken `_floor_shares` (`Decimal` + `ROUND_FLOOR`) kullanılarak pay miktarı her zaman 2 ondalık basamağa **AŞAĞI yuvarlanır**.
  - `cash_usd` bakiyesi **asla `0.00 $`'ın altına (eksiye) düşemez**.
  - Tüm işlem tutarları (`position_cost`, `gross_proceeds`, `net_proceeds`, `pnl_usd`) işlem anında cent hassasiyetine (`round(..., 2)`) yuvarlanır; `cash_usd + açık_pozisyon_değeri == total_equity_usd` denkliği kuruşu kuruşuna korunur.

---

## 3. KUYRUK (QUEUE) VE WATCHLIST KURALLARI

- **Günlük Analiz Kotası:** Antigravity kota koruma kuralı gereği her çalıştırmada **toplam maksimum 5 hisse** analiz edilir.
- **Kuyruk Öncelik Sırası (`build_analysis_queue`):**
  1. `open_positions` (Açık pozisyonlar: Stop-Loss, Take-Profit veya trend takibi)
  2. `watchlist` (İzleme listesindeki aktif `WAIT_BUY` hisseleri)
  3. `data/universe.json` (İlk iki gruptan kalan boş kontenjan kadar rastgele ve **mükerrer olmayan** yeni keşif)
- **Taşma (Overflow) Kuralı:** `open_positions` + `watchlist` sayısı 5'i aşarsa sistem çökmez; öncelik sırasını koruyarak kuyruğu tam 5 hissede kırpar (truncate).
- **Watchlist Zaman Aşımı (TTL = 14 Gün):** İzleme listesine eklenen bir hissenin geçerlilik süresi **14 gündür** (`expires_date`). Süresi dolan hisseler `clean_watchlist` tarafından `EXPIRED` olarak işaretlenir ve `state["watchlist"]` dizisinden **fiziksel olarak silinir**.

---

## 4. GERÇEK MODÜL ENTEGRASYONU (`claude-trading-skills`)

- `claude-trading-skills` reposundaki aşağıdaki modüller `src/prepare_daily_batch.py` içerisinden doğrudan `sys.path` ile import edilerek gerçek hesaplamalarla çalıştırılır (**yüzeysel veya mock hesaplama yapılması kesinlikle yasaktır**):
  1. `drawdown-circuit-breaker/scripts/check_circuit_breaker.py` (`evaluate_circuit_breaker`, `CircuitConfig`, `parse_as_of`)
  2. `technical-analyst/scripts/weekly_price_action.py` (`run_weekly_price_action`)
  3. `position-sizer/scripts/position_sizer.py` (`calculate_position`, `SizingParameters`)
- **Devre Kesici Kilidi:** Devre kesici (`circuit_breaker`) durumu `HALTED` veya `COOLDOWN` döndürürse **kesinlikle yeni `BUY` işlemi yapılamaz** (`src/execute_decisions.py` bu durumda `BUY` emirlerini otomatik olarak reddeder).

---

## 5. GÜNLÜK ÇALIŞMA VE DOĞRULAMA KOMUTLARI

### Günlük Operasyon Döngüsü
```bash
# 1. Günlük veri paketini ve 5 hisselik kuyruğu hazırla (data/daily_briefing.json üretir)
/home/memin/Projects/Trader/.venv/bin/python /home/memin/Projects/Trader/src/prepare_daily_batch.py

# 2. data/daily_briefing.json verilerini docs/COMMITTEE_PROMPT.md içindeki 11 adımlı komite süzgecinden geçir
#    ve kararları /home/memin/Projects/Trader/data/decisions.json dosyasına yaz.

# 3. Kararları yürüt, data/state.json ve docs/PORTFOLIO_DASHBOARD.md dosyalarını güncelle
/home/memin/Projects/Trader/.venv/bin/python /home/memin/Projects/Trader/src/execute_decisions.py
```

### Zorunlu QA ve Doğrulama Kuralı
Kodlarda (`src/prepare_daily_batch.py`, `src/execute_decisions.py` vb.) herhangi bir değişiklik yapıldığında, gerçek `data/state.json` ve `docs/PORTFOLIO_DASHBOARD.md` dosyalarına **dokunmadan** aşağıdaki doğrulama paketinin çalıştırılması ve **21 testin tamamının (`OK`) geçmesi zorunludur**:
```bash
/home/memin/Projects/Trader/.venv/bin/python /home/memin/Projects/Trader/tests/validate_system.py
```

---

## 6. KANBAN VE GÖREV TAKİBİ (DOKUNULMAZ SENKRONİZASYON KURALI)

- **Çift Yönlü Canlı Pano:** Görev takibi hem yerel doküman (`/home/memin/Projects/Trader/docs/Kanban.md`) hem de GitHub üzerindeki canlı **[Trader Project #10](https://github.com/users/Memin-ckn/projects/10)** panosu üzerinden yürütülür.
- **Sütun ve Statü Eşleşmesi (1:1 Standart):**
  - `# To do` <---> `Backlog`
  - `# In Progress` <---> `In progress`
  - `# Testing` <---> `In review`
  - `# Complete` <---> `Done`
- **Zorunlu Senkronizasyon Kuralı:**
  1. **Oturum Başında:** Ajan çalışmaya başlamadan önce GitHub üzerindeki olası web değişikliklerini yerel dosyaya çekmek için senkronizasyonu kontrol eder / eşitler:
     ```bash
     /home/memin/Projects/Trader/.venv/bin/python /home/memin/Projects/Trader/src/sync_kanban.py --pull
     ```
  2. **Geliştirme Sırasında / Görev Taşıma:** Herhangi bir görev sütun değiştirdiğinde (`In progress`, `Testing`, `Done`) veya yeni görev eklendiğinde ajan `docs/Kanban.md` dosyasını günceller ve **HEMEN** GitHub'a senkronize eder:
     ```bash
     # Tüm yerel değişiklikleri GitHub'a iter:
     /home/memin/Projects/Trader/.venv/bin/python /home/memin/Projects/Trader/src/sync_kanban.py --push
     # VEYA tek bir görevi doğrudan taşır:
     /home/memin/Projects/Trader/.venv/bin/python /home/memin/Projects/Trader/src/sync_kanban.py --move "Görev Adı" --to "In progress"
     ```
  3. **Git Commit Öncesi Otomatik Koruma:** `.git/hooks/pre-commit` kancası kuruludur; `docs/Kanban.md` değiştiğinde commit anında GitHub panosu otomatik güncellenir.
- **Kullanıcı Onayı Kuralı:** `To do` (Backlog) kısmı onay alındığı takdirde ajanın kendi anlayacağı şekilde düzenlenebilir; ancak görevler önem sırasına göre sıralandığı için değişiklik yapılmadan önce **kullanıcıdan mutlaka onay alınması** gerekmektedir.

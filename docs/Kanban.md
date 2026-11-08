> 🔗 **Canlı GitHub Project Panosu:** [Trader Project #10](https://github.com/users/Memin-ckn/projects/10)

# To do
- Optimizasyon
    - Projede kullanılmayan, işe yaramayan, daha optimize şekilde yapılabilecek, tekrar eden ne varsa silinmeli. Tekrarlar fonksiyon haline getirilip kullanılmalı. Projede kalabalık yaratan ve verimliliği azaltan her şeyden kurtulunup tertemiz hale getirilmeli.

# In Progress

# Testing

# Complete
- Backtest Simülasyonunun Yürütülmesi (Kasım 2024 – Kasım 2026)
    - Gerçek 11 ajanlı AGY komitesi kararlarıyla (`docs/COMMITTEE_PROMPT.md`, zero look-ahead) `src/backtest_step.py` üzerinden 105+ haftalık 2 yıllık simülasyon %100 tamamlandı (`COMPLETED`).
    - Strateji V2 disiplini (1% mekanik risk kilidi, maks 2 sektör kotası, akıllı ön tarayıcı) uygulandı; tüm detaylar, equity eğrisi ve trade logları `docs/BACKTEST_REPORT.md` içinde belgelendi.
- Backtest Simülasyonu — Altyapı (alt görev 1, 2, 3 & 4)
    - **1. Cevap Anahtarı Deposu ve Toplu Veri Önbelleği (`src/backtest_data.py` & `data/backtest_cache/`):** OHLCV verileri ve `SPY` kıyas endeksi yerel önbellekte tutuluyor (SMA(200) / 52 haftalık indikatörler Kasım 2024 başında hazır).
    - **2. Zaman Kilidi ve Geleceği Görmeme Kalkanı (`Point-in-Time Slicing` / `src/prepare_daily_batch.py`):** `--as-of` ve yerel önbellek desteği; `hist.loc[:as_of_date]` kesimi ile Look-Ahead Bias engellendi.
    - **3. İzole Checkpoint Kasası (`data/backtest_state.json`):** `src/backtest_step.py --init` ile 3.500 $ başlangıçlı, `current_sim_date` / `status` (`READY` / `AWAITING_DECISIONS` / `COMPLETED`) taşıyan kasa kuruldu; kaldığı yerden devam eder.
    - **4. Adım Adım Backtest Yürütücüsü (`src/backtest_step.py` & `docs/BACKTEST_REPORT.md`):** `--prepare` (tarih ilerletme, ara gün SL/TP otomatik satış, Zaman Kilitli brifing), `--execute` (kararları `process_decisions` ile işleme, equity_curve + SPY kıyası, karne), `--status` modları kodlandı. 21 test geçti.
- Borsa (S&P 500 Takibi)
    - `src/update_universe.py` betiği yazılarak S&P 500 bileşenleri ve 11 GICS sektör bilgisi çekildi; semboller `yfinance` formatına (`BRK.B` -> `BRK-B`, `BF.B` -> `BF-B`) normalize edildi.
    - Aynı şirketin ikincil pay sınıfları (`GOOG`, `FOX`, `NWS`) elenip tekilleştirilerek `data/universe.json` dosyası tam 500 tekil S&P 500 hissesi ve sektör haritasıyla güncellendi.
    - `src/prepare_daily_batch.py` içinde hatalı/eksik `yfinance` verilerinde 5 hisselik kotayı koruyan `Discovery Fallback` (`TC-15`) döngüsü ve ABD seansı kapanmadan (16:00 ET öncesi) yarım günlük hacim yanılsamasını önleyen `strip_incomplete_intraday_bar` / `is_market_session_valid` (`TC-16`) korumaları devreye alındı.
- UI
    - `src/ui_dashboard.py` ile incelenen her hisse için 11 komite ajanının/adımının ayrı ayrı kararını (`✅ ONAY`, `⚠️ UYARI`, `❌ RED`), metriklerini ve gerekçelerini sentezleyen 11 Ajan Karar Karnesi motoru kuruldu.
    - Hem GitHub/IDE uyumlu ASCII grafikli ve 11 ajan tablolu `docs/PORTFOLIO_DASHBOARD.md` hem de sunucu gerektirmeyen, tek dosyalık koyu temalı interaktif web paneli (`docs/dashboard.html`) üretildi.
    - Gizlilik ve Canlı Mod Kalkanı (`Privacy Mode` / `LIVE`) eklendi: `docs/dashboard.html` `.gitignore` ile yalnızca yerel bilgisayarda tutulurken, canlı parayla işlemlere geçildiğinde public Markdown dosyasındaki kişisel bakiye, lot ve işlem tutarlarının otomatik maskelenmesi sağlandı.
- Dosya Mimarisi ve Modüler Klasör Yapısı (`src/`, `data/`, `docs/`, `tests/`)
    - Kök dizindeki tüm dağınık dosyalar görevlerine göre `src/`, `data/`, `docs/` ve `tests/` alt klasörlerine taşındı; kök dizinde yalnızca `README.md` ve ajan kılavuzları (`AGENTS.md` / `CLAUDE.md`) bırakılarak maksimum sadelik sağlandı.
    - `src/paths.py` ile merkezi ve çalışma dizininden bağımsız (CWD-independent) yol çözümleme sistemi kuruldu.
    - Taşıma sırasında `data/state.json`, `data/universe.json`, `docs/PORTFOLIO_DASHBOARD.md` ve `docs/COMMITTEE_PROMPT.md` dosyalarının SHA-256 özetleri korunarak sıfır veri kaybı doğrulandı ve 21 test senaryosu yeni mimaride başarıyla geçirildi.
- Validation ve 21 Senaryolu Kapsamlı Test Paketi (`tests/validate_system.py` & `docs/test_senaryolari.md`)
    - Proje üzerinde yapılan her değişikliğin sisteme uygun, hatasız ve temiz olduğunu test eden 21 test senaryosu eksiksiz kodlandı.
    - Sıfır Canlı Temas (Zero-Touch SHA-256) kuralı uygulandı; canlı `state.json`, `universe.json`, `COMMITTEE_PROMPT.md` ve `PORTFOLIO_DASHBOARD.md` dosyalarına dokunulmadan izole geçici ortamlarda çalışması sağlandı.
    - `claude-trading-skills` modülleri mock'lanmadan gerçek hesaplamalarla entegre edildi.
    - Kademeli alım (Scale-In), kısmi satış (Scale-Out), devre kesici kilitleri, atomik yazma (`.tmp` + `os.replace`), idempotency ve Forex Factory makro süzgeci dahil 21 test senaryosunun tamamı başarıyla geçti.
- Proje Altyapısı ve Anayasa Kurulumu (`docs/PROJECT_CONTEXT.md`)
    - Çalışma dizini, `.venv` Python ortamı ve `tradermonty/claude-trading-skills` reposu kuruldu.
    - 3.500 $ başlangıç bakiyeli `data/state.json` ve 50 likit ABD hissesinden oluşan `data/universe.json` havuzu oluşturuldu.
- Günlük Veri ve Kuyruk Motoru (`src/prepare_daily_batch.py`)
    - 5 hisselik öncelikli kuyruk (`open_positions` -> `watchlist` -> `random_discovery`) ve `yfinance` teknik/temel veri çekim motoru yazıldı.
    - `check_circuit_breaker.py`, `weekly_price_action.py` ve `position_sizer.py` modülleri gerçek hesaplamalarla sisteme entegre edildi ve `data/daily_briefing.json` üretildi.
- Komite Süzgeci ve Karar Yürütücüsü (`docs/COMMITTEE_PROMPT.md` & `src/execute_decisions.py`)
    - 11 adımlı yatırım komitesi karar şeması (`data/decisions.json`) ve portföy muhasebe yürütücüsü (`src/execute_decisions.py`) kuruldu.
    - `docs/PORTFOLIO_DASHBOARD.md` gösterge paneli oluşturuldu ve ilk 5 hisselik gerçek veriyle Dry Run tamamlandı.
- Kıdemli QA Denetimi ve Kritik Bug Düzeltmeleri
    - `BUY` işleminde `%20` pozisyon sınırını delen `* 1.02` toleransı kaldırıldı; `_floor_shares` (`Decimal` + `ROUND_FLOOR`) ile pay adedinin her zaman aşağı yuvarlanması sağlandı.
    - Yetersiz nakit durumunda `round()` kaynaklı eksi bakiye (`cash_usd < 0`) hatası giderildi ve devre kesici (`HALTED` / `COOLDOWN`) alım kilidi eklendi.
    - Küsüratlı `BUY`/`SELL` işlemlerindeki 1 cent (`0.01$`) yuvarlama sapması düzeltilerek kuruşu kuruşuna muhasebe denkliği sağlandı.
    - 14 günü dolan `watchlist` hisselerinin `EXPIRED` olarak işaretlenip listeden fiziksel olarak silinmesi (`clean_watchlist`) sağlandı.
    - `yfinance` `NaN` ve eksik fiyat/hacim verilerinde çökme açıkları (`_sanitize_history_df`, `_is_finite_number`) kapatıldı.
- Kalıcı Ajan Hafıza ve Mimari Kılavuzu (`AGENTS.md` & `CLAUDE.md`)
    - Her oturum başında okunacak proje kuralları, dokunulmaz muhasebe ilkeleri, günlük komutlar ve Kanban takip kuralları dokümante edildi.

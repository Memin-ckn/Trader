# To do
- UI
    - 11 agent'ın verdiği kararlar, gerekçeleri, nihai karar, portfolyodaki hisseler, toplam para, kar/zarar gibi bilgileri görebileceğim bir ui istiyorum.
    - Bu UI hangisi daha kolay olacaksa o şekilde yapılsın. Basit web app, csv dosyası, ASCII art ile oluşturulmuş markdown ve benzeri herhangi bir şeyi kabul ederim. Yalnızca bilmem gerekenleri göreyim yeterli benim için.
- Borsa
    - Şu an anladığım kadarıyla test amaçlı yazdığımız 50 adet hisseyi kullanıyor ancak bunun planladığımız abd borsalarını (s&p 500 gibi) takip etmesi gerekiyor.
- Forex Factory diye bir site var onun işimize yarayıp yaramadığı kontrol edilecek. Eğer iyiyse belki bir agent onun için ekleyebiliriz ya da şu anki agentlar orayı kontrol edebilir analiz için.
- Backtest
    - Kullandığımız teknolojilerin izin verdiği kadar (maks 3 yıl min 1 yıl) geriye gidip 1 yıllık süreci simüle edeceğiz. Bu sayede oluşturduğumuz sistemin 1 yıllık getirisini tahmini olarak hesaplayabilriiz.

# In Progress

# Testing

# Complete
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

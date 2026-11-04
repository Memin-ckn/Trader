# To do
- Dosya Mimarisi
    - Dosyalar şu anda rastgele bir şekilde root'ta falan duruyor. Bunları gerekli klasörlere yerleştirip gelecekteki geliştirmeler için uygun hale getirmemiz lazım. Temiz ve okunabilir durmalı.
- UI
    - 11 agent'ın verdiği kararlar, gerekçeleri, nihai karar, portfolyodaki hisseler, toplam para, kar/zarar gibi bilgileri görebileceğim bir ui istiyorum.
    - Bu UI hangisi daha kolay olacaksa o şekilde yapılsın. Basit web app, csv dosyası, ASCII art ile oluşturulmuş markdown ve benzeri herhangi bir şeyi kabul ederim. Yalnızca bilmem gerekenleri göreyim yeterli benim için.
- Borsa
    - Şu an anladığım kadarıyla test amaçlı yazdığımız 50 adet hisseyi kullanıyor ancak bunun planladığımız abd borsalarını (s&p 500 gibi) takip etmesi gerekiyor.
- Forex Factory diye bir site var onun işimize yarayıp yaramadığı kontrol edilecek. Eğer iyiyse belki bir agent onun için ekleyebiliriz ya da şu anki agentlar orayı kontrol edebilir analiz için.
- Backtest
    - Kullandığımız teknolojilerin izin verdiği kadar (maks 3 yıl min 1 yıl) geriye gidip 1 yıllık süreci simüle edeceğiz. Bu sayede oluşturduğumuz sistemin 1 yıllık getirisini tahmini olarak hesaplayabilriiz.

# In Progress
- Validation (`validate_system.py` & `test_senaryolari.md`)
    - Proje üzerinde yapılan her değişikliğin sisteme uygun, hatasız ve temiz olduğunu test edebileceğimiz senaryolar oluşturulacak.
    - Bu senaryolar her değişiklik sonrası test edilecek ve bütün testlerden geçilmeden hiçbir değişiklik onaylanmayacak.
    - **Mevcut Durum:** İzole geçici dosyalar üzerinde çalışan ilk doğrulama paketi (`validate_system.py`) oluşturuldu (Kuyruk önceliği/taşma, 14 gün `EXPIRED` temizliği, `BUY -> HOLD -> SELL` muhasebe denkliği, %20 pozisyon tavanı/yetersiz bakiye ve `yfinance` `NaN` dayanıklılığı). Ayrıca tüm gerçek ABD borsası (S&P 500 / NASDAQ), gerçek tarihsel veriyle backtest, kademeli alım/kısmi satış komisyon muhasebesi, 11 ajan UI görünürlüğü ve Forex Factory (`USD` odaklı) testlerini kapsayan `test_senaryolari.md` şartnamesi revize edilerek tamamlandı.
    - **Eksikler / Yapılacaklar:** `test_senaryolari.md` içinde tanımlanan yeni uç durum ve gerçek piyasa verisi senaryoları `validate_system.py` içerisine kodlanarak aktif test sayısı artırılacak.

# Testing

# Complete
- Proje Altyapısı ve Anayasa Kurulumu (`PROJECT_CONTEXT.md`)
    - Çalışma dizini, `.venv` Python ortamı ve `tradermonty/claude-trading-skills` reposu kuruldu.
    - 3.500 $ başlangıç bakiyeli `state.json` ve 50 likit ABD hissesinden oluşan `universe.json` havuzu oluşturuldu.
- Günlük Veri ve Kuyruk Motoru (`prepare_daily_batch.py`)
    - 5 hisselik öncelikli kuyruk (`open_positions` -> `watchlist` -> `random_discovery`) ve `yfinance` teknik/temel veri çekim motoru yazıldı.
    - `check_circuit_breaker.py`, `weekly_price_action.py` ve `position_sizer.py` modülleri gerçek hesaplamalarla sisteme entegre edildi ve `daily_briefing.json` üretildi.
- Komite Süzgeci ve Karar Yürütücüsü (`COMMITTEE_PROMPT.md` & `execute_decisions.py`)
    - 11 adımlı yatırım komitesi karar şeması (`decisions.json`) ve portföy muhasebe yürütücüsü (`execute_decisions.py`) kuruldu.
    - `PORTFOLIO_DASHBOARD.md` gösterge paneli oluşturuldu ve ilk 5 hisselik gerçek veriyle Dry Run tamamlandı.
- Kıdemli QA Denetimi ve Kritik Bug Düzeltmeleri
    - `BUY` işleminde `%20` pozisyon sınırını delen `* 1.02` toleransı kaldırıldı; `_floor_shares` (`Decimal` + `ROUND_FLOOR`) ile pay adedinin her zaman aşağı yuvarlanması sağlandı.
    - Yetersiz nakit durumunda `round()` kaynaklı eksi bakiye (`cash_usd < 0`) hatası giderildi ve devre kesici (`HALTED` / `COOLDOWN`) alım kilidi eklendi.
    - Küsüratlı `BUY`/`SELL` işlemlerindeki 1 cent (`0.01$`) yuvarlama sapması düzeltilerek kuruşu kuruşuna muhasebe denkliği sağlandı.
    - 14 günü dolan `watchlist` hisselerinin `EXPIRED` olarak işaretlenip listeden fiziksel olarak silinmesi (`clean_watchlist`) sağlandı.
    - `yfinance` `NaN` ve eksik fiyat/hacim verilerinde çökme açıkları (`_sanitize_history_df`, `_is_finite_number`) kapatıldı.
- Kalıcı Ajan Hafıza ve Mimari Kılavuzu (`AGENTS.md` & `CLAUDE.md`)
    - Her oturum başında okunacak proje kuralları, dokunulmaz muhasebe ilkeleri, günlük komutlar ve Kanban takip kuralları dokümante edildi.

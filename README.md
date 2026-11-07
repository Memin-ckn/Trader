# 📈 Otonom Borsa Orkestrası (Sanal Yatırım Sistemi)

Bu proje, ABD borsasındaki (Apple, Microsoft, Nvidia gibi) büyük şirketlerin hisselerini her gün otomatik olarak tarayan ve **11 farklı uzman yapay zeka karakterinden oluşan bir "Yatırım Komitesi"** ile alım-satım kararları veren sanal bir borsa simülasyonudur.

Gerçek para riske atmadan, **3.500 $ sanal bakiye** ve gerçekçi aracı kurum kurallarıyla (işlem başı 1.50 $ komisyon, tek hisseye en fazla %20 yatırım sınırı vb.) sistemin ne kadar başarılı olacağını test ediyoruz.

---

## 🚀 Proje Ne Aşamada? (Genel İlerleme: %55)

`███████████░░░░░░░░░` **%55 Tamamlandı**

Kanban görev tablomuza göre toplam **11 ana görevin 6'sı tamamen bitti, 5'i ise sırada bekliyor.**

---

### ✅ Neleri Tamamladık? (Bitenler)

1. **Sanal Kasa ve Kuralların Kurulumu:** 3.500 $ başlangıç kasası, komisyon kuralları ve takip edilecek 50 büyük ABD hissesinin havuzu oluşturuldu.
2. **Günlük Piyasa Tarayıcısı:** Sistemin her gün borsadaki güncel fiyatları, grafik göstergelerini ve şirket verilerini otomatik çekip en önemli 5 hisseyi seçtiği motor yazıldı.
3. **11 Kişilik Yapay Zeka Komitesi ve Karar Sistemi:** Hisseleri farklı açılardan (trend, risk, karşıt görüş, senaryo analizi) inceleyip **"Al / Sat / Bekle / İptal Et"** kararı veren ve kasayı otomatik güncelleyen yapı kuruldu. İlk deneme işlemleri başarıyla yapıldı.
4. **Muhasebe ve Güvenlik Denetimi:** Kasanın eksiye düşmesini, tek bir hisseye fazla para yatırılmasını veya kuruş hesaplamalarındaki hataları engelleyen güvenlik kilitleri eklendi.
5. **Yapay Zeka Hafıza Sistemi:** Sistemin kuralları hiç unutmaması ve her gün aynı disiplinle çalışması için kalıcı rehber dosyaları hazırlandı.
6. **21 Senaryolu Otomatik Doğrulama ve Test Sistemi:** Sıfır canlı temas (Zero-Touch SHA-256) garantisiyle çalışan, kademeli alım, kısmi satış, devre kesici, atomik yazma ve makro filtre dahil 21 senaryoyu kapsayan test paketi (`validate_system.py`) tamamlandı.

---

### 🚧 Şu An Üzerinde Çalıştığımız Kısım (Devam Eden)

- *Doğrulama ve test aşaması tamamlandı; sıradaki görev (Dosya Mimarisi / UI) için hazır bekliyor.*

---

### 📋 Sırada Ne Var? (Yapılacaklar)

1. **Temiz Dosya Mimarisi:** Dosyaların modüler klasörlere (`src/`, `config/` vb.) yerleştirilerek projenin daha düzenli, okunabilir ve profesyonel bir yapıya kavuşturulması.
2. **Görsel Takip Ekranı (UI):** 11 uzmanın kararlarını, gerekçelerini, portföydeki hisseleri ve toplam kâr/zarar durumunu kolayca görebileceğimiz sade bir arayüz/pano hazırlanması.
3. **Gerçek Borsa Havuzu (S&P 500 / NASDAQ):** 50 hisselik test havuzunun genişletilerek planlanan gerçek ABD borsası endekslerinin taranması.
4. **Ekonomik Takvim ve Haber Takibi (Forex Factory):** ABD faiz kararları, enflasyon gibi piyasayı dalgalandıran kritik makro haberleri takip edip riskli günlerde işlem açılmasını engelleyen bir haber analizi/ajanı eklenmesi.
5. **Geçmişe Dönük Test (Backtest):** Sistemin 1 ila 3 yıllık geçmiş borsa verileri üzerinde simüle edilerek olası getirisinin ve başarısının hesaplanması.

---

*📌 Not: Güncel cüzdan ve açık pozisyon durumu için [PORTFOLIO_DASHBOARD.md](PORTFOLIO_DASHBOARD.md) dosyasına, detaylı iş takibi için [Kanban.md](Kanban.md) tablosuna göz atabilirsiniz.*

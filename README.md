# 📈 Otonom Borsa Orkestrası (Sanal Yatırım Sistemi)

Bu proje, ABD borsasındaki (Apple, Microsoft, Nvidia gibi) büyük şirketlerin hisselerini her gün otomatik olarak tarayan ve **11 farklı uzman yapay zeka karakterinden oluşan bir "Yatırım Komitesi"** ile alım-satım kararları veren sanal bir borsa simülasyonudur.

Gerçek para riske atmadan, **3.500 $ sanal bakiye** ve gerçekçi aracı kurum kurallarıyla (işlem başı 1.50 $ komisyon, tek hisseye en fazla %20 yatırım sınırı vb.) sistemin ne kadar başarılı olacağını test ediyoruz.

---

## 🚀 Proje Ne Aşamada? (Genel İlerleme: %75)

`███████████████░░░░░` **%75 Tamamlandı**

Kanban görev tablomuza göre toplam **12 ana görevin 9'u tamamen bitti, 3'ü ise sırada bekliyor.**

---

### ✅ Neleri Tamamladık? (Bitenler)

1. **Sanal Kasa ve Kuralların Kurulumu:** 3.500 $ başlangıç kasası ve gerçekçi komisyon kuralları oluşturuldu.
2. **Günlük Piyasa Tarayıcısı:** Sistemin her gün borsadaki güncel fiyatları, grafik göstergelerini ve şirket verilerini otomatik çekip en önemli 5 hisseyi seçtiği motor yazıldı.
3. **11 Kişilik Yapay Zeka Komitesi ve Karar Sistemi:** Hisseleri farklı açılardan (trend, risk, karşıt görüş, senaryo analizi) inceleyip **"Al / Sat / Bekle / İptal Et"** kararı veren ve kasayı otomatik güncelleyen yapı kuruldu. İlk deneme işlemleri başarıyla yapıldı.
4. **Muhasebe ve Güvenlik Denetimi:** Kasanın eksiye düşmesini, tek bir hisseye fazla para yatırılmasını veya kuruş hesaplamalarındaki hataları engelleyen güvenlik kilitleri eklendi.
5. **Yapay Zeka Hafıza Sistemi:** Sistemin kuralları hiç unutmaması ve her gün aynı disiplinle çalışması için kalıcı rehber dosyaları hazırlandı.
6. **21 Senaryolu Otomatik Doğrulama ve Test Sistemi:** Sıfır canlı temas (Zero-Touch SHA-256) garantisiyle çalışan, kademeli alım, kısmi satış, devre kesici, atomik yazma ve makro filtre dahil 21 senaryoyu kapsayan test paketi tamamlandı.
7. **Temiz ve Modüler Dosya Mimarisi:** Kök dizindeki kalabalık giderilerek tüm kaynak kodlar (`src/`), canlı veriler (`data/`), belgeler/panolar (`docs/`) ve testler (`tests/`) kendi klasörlerine yerleştirildi.
8. **Görsel Takip Ekranı (UI) ve 11 Uzman Karnesi:** İncelenen her hisse için 11 uzmanın ayrı ayrı verdiği kararları (`✅ Onay / ⚠️ Uyarı / ❌ Red`), gerekçelerini, portföy dağılımını ve kâr/zarar durumunu gösteren hem GitHub uyumlu (`docs/PORTFOLIO_DASHBOARD.md`) hem de yerel interaktif web arayüzü (`docs/dashboard.html`) ile kişisel gizlilik kalkanı kuruldu.
9. **Gerçek ABD Borsası Havuzu (S&P 500 Takibi):** 50 hisselik test havuzu yerine S&P 500 endeksindeki 500 dev ABD şirketi (ve 11 sektör bilgisi) sisteme entegre edildi; hatalı hisselerde otomatik yedek aday seçimi ve ABD borsa seansı kapanış/hacim koruması devreye alındı.

---

### 🚧 Şu An Üzerinde Çalıştığımız Kısım (Devam Eden)

- *S&P 500 borsa havuzu entegrasyonu tamamlandı; sıradaki görev (Ekonomik Takvim ve Haber Takibi — Forex Factory) için hazır bekliyor.*

---

### 📋 Sırada Ne Var? (Yapılacaklar)

1. **Ekonomik Takvim ve Haber Takibi (Forex Factory):** ABD faiz kararları, enflasyon gibi piyasayı dalgalandıran kritik makro haberleri takip edip riskli günlerde işlem açılmasını engelleyen bir haber analizi/ajanı eklenmesi.
2. **Geçmişe Dönük Test (Backtest):** Sistemin 1 ila 3 yıllık geçmiş borsa verileri üzerinde simüle edilerek olası getirisinin ve başarısının hesaplanması.
3. **Kod Temizliği ve Optimizasyon:** Projedeki tekrar eden kodların birleştirilmesi ve maksimum verimlilik için genel optimizasyon yapılması.

---

*📌 Not: Güncel cüzdan ve açık pozisyon durumu için [PORTFOLIO_DASHBOARD.md](docs/PORTFOLIO_DASHBOARD.md) dosyasına, detaylı iş takibi için [Kanban.md](docs/Kanban.md) tablosuna veya canlı [GitHub Project #10 (Trader)](https://github.com/users/Memin-ckn/projects/10) panosuna göz atabilirsiniz.*

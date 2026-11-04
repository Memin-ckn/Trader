# 📈 Otonom Borsa Orkestrası (Sanal Yatırım Sistemi)

Bu proje, ABD borsasındaki (Apple, Microsoft, Nvidia gibi) büyük şirketlerin hisselerini her gün otomatik olarak tarayan ve **11 farklı uzman yapay zeka karakterinden oluşan bir "Yatırım Komitesi"** ile alım-satım kararları veren sanal bir borsa simülasyonudur.

Gerçek para riske atmadan, **3.500 $ sanal bakiye** ve gerçekçi aracı kurum kurallarıyla (işlem başı 1.50 $ komisyon, tek hisseye en fazla %20 yatırım sınırı vb.) sistemin ne kadar başarılı olacağını test ediyoruz.

---

## 🚀 Proje Ne Aşamada? (Genel İlerleme: %68)

`██████████████░░░░░░` **%68 Tamamlandı**

Kanban görev tablomuza göre toplam **8 ana aşamanın 5'i tamamen bitti, 1'i yapım aşamasında, 2'si ise sırada bekliyor.**

---

### ✅ Neleri Tamamladık? (Bitenler)

1. **Sanal Kasa ve Kuralların Kurulumu:** 3.500 $ başlangıç kasası, komisyon kuralları ve takip edilecek 50 büyük ABD hissesinin havuzu oluşturuldu.
2. **Günlük Piyasa Tarayıcısı:** Sistemin her gün borsadaki güncel fiyatları, grafik göstergelerini ve şirket verilerini otomatik çekip en önemli 5 hisseyi seçtiği motor yazıldı.
3. **11 Kişilik Yapay Zeka Komitesi ve Karar Sistemi:** Hisseleri farklı açılardan (trend, risk, karşıt görüş, senaryo analizi) inceleyip **"Al / Sat / Bekle / İptal Et"** kararı veren ve kasayı otomatik güncelleyen yapı kuruldu. İlk deneme işlemleri başarıyla yapıldı.
4. **Muhasebe ve Güvenlik Denetimi:** Kasanın eksiye düşmesini, tek bir hisseye fazla para yatırılmasını veya kuruş hesaplamalarındaki hataları engelleyen güvenlik kilitleri eklendi.
5. **Yapay Zeka Hafıza Sistemi:** Sistemin kuralları hiç unutmaması ve her gün aynı disiplinle çalışması için kalıcı rehber dosyaları hazırlandı.

---

### 🚧 Şu An Üzerinde Çalıştığımız Kısmı (Devam Eden)

- **Otomatik Kontrol ve Test Sistemi (Validation):** Sistemde bir değişiklik yaptığımızda hiçbir hesabın şaşmadığından emin olmak için kendi kendini test eden bir mekanizma kuruyoruz. Temel testler çalışıyor, şu an daha detaylı senaryolar ekliyoruz.

---

### 📋 Sırada Ne Var? (Yapılacaklar)

1. **Görsel Takip Ekranı (UI):** Komitenin hangi hisseye neden karar verdiğini, elimizdeki hisseleri ve toplam kâr/zarar durumunu kolayca görebileceğimiz sade ve anlaşılır bir ekran yapılacak.
2. **Geçmişe Dönük Test (Backtest):** "Bu sistemi 1-3 yıl önce çalıştırmaya başlasaydık bugün paramız ne kadar olurdu?" sorusunun cevabını görmek için geçmiş borsa verileriyle hızlandırılmış simülasyon yapılacak.

---

*📌 Not: Güncel cüzdan ve açık pozisyon durumu için [PORTFOLIO_DASHBOARD.md](PORTFOLIO_DASHBOARD.md) dosyasına, detaylı iş takibi için [Kanban.md](Kanban.md) tablosuna göz atabilirsiniz.*

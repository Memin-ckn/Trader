# 🏛️ YATIRIM KOMİTESİ ÇALIŞMA KILAVUZU (COMMITTEE PROMPT)

Bu kılavuz, **Antigravity (AGY)** yapay zeka modelinin `claude-trading-skills` reposundaki 11 adımlık yatırım disiplini ve ajan mantığını uygulayarak, günlük piyasa verilerini analiz etmesini ve bağlayıcı alım-satım kararları (`decisions.json`) üretmesini sağlayan operasyonel anayasadır.

---

## 🎯 Komitenin Temel Amacı ve Çalışma Döngüsü

Her çalışma periyodunda AGY sırasıyla şu 3 adımı icra eder:
1. **Veri ve Kuyruk Motorunu Tetikle:**
   ```bash
   .venv/bin/python prepare_daily_batch.py
   ```
   Bu script `state.json` dosyasını inceler, süresi dolan izleme listesi hisselerini temizler, en fazla 5 hisselik öncelikli kuyruğu (Açık Pozisyonlar > İzleme Listesi > Yeni Keşif) oluşturur ve `daily_briefing.json` dosyasını hazırlar.
2. **11 Kuralı Sentezleyerek Analiz Et:**
   `daily_briefing.json` içindeki verileri ve makro koşulları aşağıdaki 11 aşamalı komite süzgecinden geçirir.
3. **Karar Dosyasını Yaz ve Yürüt:**
   Analiz sonucunu kesin formatta `/home/memin/Projects/Trader/decisions.json` dosyasına kaydeder ve yürütücüyü tetikler:
   ```bash
   .venv/bin/python execute_decisions.py
   ```

---

## 📋 11 Adımlık Komite Analiz ve Disiplin Sistemi

### Adım 1: Hesap Devre Kesici Kontrolü (`drawdown-circuit-breaker`)
- `daily_briefing.json` içindeki `circuit_breaker.recommendation` değerini kontrol et.
- **Kural:**
  - Eğer `HALTED` veya `COOLDOWN` ise: **KESİNLİKLE YENİ ALIM (BUY) YAPILAMAZ.**
  - Sadece mevcut açık pozisyonlar korunabilir (`HOLD`) veya risk azaltmak için satılabilir (`SELL`).
  - Yeni hisseler en fazla izlemeye alınabilir (`WAIT_BUY` - koşullu) veya reddedilir (`DROP`).
  - Eğer `TRADING_ALLOWED` ise: Yeni risk alımına izin verilir.

### Adım 2: Öncelikli Kuyruk Yönetimi (`queue-management`)
- Tek seferde toplam **maksimum 5 hisse** incelenir (Antigravity kota koruma kuralı).
- Öncelik Sıralaması:
  1. `open_positions`: Portföydeki açık hisseler öncelikle incelenir. Stop-loss patladı mı? Kâr al seviyesine ulaşıldı mı? Trend bozuldu mu?
  2. `watchlist`: Daha önce "bekle" denilen hisseler hedef alım seviyesine ulaştı mı? 14 günlük süre doldu mu?
  3. `discovery`: Kalan boş kontenjan kadar `universe.json` içinden seçilen yeni adaylar.

### Adım 3: Minervini Trend Şablonu (Stage 2 Uptrend Gate)
- Mark Minervini'nin 7 kriterlik Trend Şablonu (`trend_template`):
  - Fiyat > SMA(150) ve Fiyat > SMA(200)
  - SMA(150) > SMA(200)
  - SMA(200) en az 22 gündür yukarı eğimli
  - Fiyat > SMA(50)
  - Fiyat, 52 haftalık dibinin en az %25 üzerinde
  - Fiyat, 52 haftalık zirvesinin en fazla %25 uzağında
  - 1 yıllık getiri pozitif (Göreceli Güç - RS)
- **Kural:** Stage 2 puanı en az %70 olmayan veya düşüş trendindeki hisselere ALIM kararı verilmez.

### Adım 4: Haftalık Fiyat Hareketi ve Fraktal Swing Seviyeleri (`technical-analyst`)
- `weekly_price_action` modülünün çıktılarını değerlendir:
  - `weekly_key_reversal`: Yeni zirve/dip sonrası haftalık kapanış dönüş sinyali verdi mi?
  - `failed_extreme` & `failed_breakout`: Sahte kırılım (boğa/ayı tuzağı) var mı?
  - `continuation`: Trend sağlıklı şekilde devam ediyor mu?
  - Fraktal Pivotlar: `nearest_swing_low` ve `nearest_swing_high` seviyeleri stop-loss ve hedef belirlemede ana referanstır.

### Adım 5: Hacim ve Momentum Doğrulaması
- Hacim: Kırılım günlerinde 20 günlük ortalama hacmin üzerinde (%20+ hacim artışı) kurumsal ilgi teyidi aranır.
- RSI(14): 45 - 70 aralığı idealdir. 75 üzeri aşırı alım (kovalama, düzeltme bekle -> `WAIT_BUY`), 30 altı aşırı satış/düşüş trendi (bıçak tutma -> `DROP`).
- MACD: Histogramın sıfırın üzerine çıkması veya yukarı kesişim aranır.

### Adım 6: Temel Değerleme ve Sağlamlık Filtresi
- F/K (P/E) ve PD/DD (P/B) rasyolarını sektör normlarına göre değerlendir.
- Negatif özkaynak, kontrolsüz borçluluk veya ani kâr çöküşü olan hisselerde teknik sinyal olsa dahi pozisyon büyüklüğü kısılır veya pas geçilir.

### Adım 7: Senaryo Analisti Değerlendirmesi (`scenario-analyst`)
- Her aday hisse ve ait olduğu sektör için 18 aylık 3 senaryoyu zihinsel olarak simüle et:
  - **Base Case (%50-60):** En olası makro/sektörel patika.
  - **Bull Case (%15-25):** Pozitif katalizörler, faiz indirimi, talep patlaması.
  - **Bear Case (%20-30):** Negatif düzenlemeler, resesyon, maliyet baskısı.
- 1., 2. ve 3. derece etkileri (hammadde, tedarik zinciri, tüketici davranışı) tart.

### Adım 8: Şeytanın Avukatı / Karşı Görüş (`strategy-reviewer`)
- Pozitif görünen teze karşı eleştirel sorular sor:
  - "Bu işlemde piyasanın gördüğü ama bizim kaçırdığımız kör nokta ne?"
  - "Eğer yarın sert bir satış gelirse hissenin ilk tutunacağı destek neresi?"
  - "Risk/Ödül Oranı (R:R): Potansiyel kâr, göze alınan zararın (stop mesafesi) en az 2 katı (1:2) mı?"

### Adım 9: Pozisyon Boyutlandırma ve Risk Bütçesi (`position-sizer`)
- **Maksimum Pozisyon Kuralı:** Tek bir hisseye kasanın en fazla **%20'si** yatırılabilir (Başlangıçta maksimum 700 $).
- **Tek İşlem Risk Limiti:** Kasanın en fazla **%1'i** (~35 $) riske atılabilir (`(Giriş - Stop) * Adet <= 35 $`).
- `position_sizer` çıktısındaki `recommended_shares` değerine tam uyulur.

### Adım 10: İşlem Öncesi Disiplin Kapısı (`pre-trade-discipline-gate`)
- Bir hisseye `BUY` kararı vermeden önce şu 5 soruya "EVET" denmelidir:
  1. [ ] Yazılı bir yatırım tezi ve net giriş seviyesi var mı?
  2. [ ] Önceden belirlenmiş matematiksel bir stop-loss fiyatı var mı?
  3. [ ] Pozisyon büyüklüğü kasanın %20'sini ve %1 risk bütçesini aşmıyor mu?
  4. [ ] Devre kesici `TRADING_ALLOWED` durumunda mı?
  5. [ ] Son kapanan işlemlerden kaynaklı duygusal/intikam işlemi (revenge trade) riski yok mu?
- Biri bile "HAYIR" ise `BUY` kararı verilemez; ya `WAIT_BUY` yapılır ya da `DROP`.

### Adım 11: Karar Sentezi ve Hafıza Güncellemesi (`trader-memory-core`)
- İncelenen 5 hissenin her biri için kesin karar üretilir:
  - `BUY`: Koşullar tam olgunlaşmışsa, belirlenen adet ve stop-loss ile anında al.
  - `SELL`: Açık pozisyonda stop patlamışsa, kâr hedefine gelinmişse veya tez bozulmuşsa kapat.
  - `HOLD`: Açık pozisyon kârda veya planda ilerliyorsa koru.
  - `WAIT_BUY`: Hisse kaliteli ama henüz alım seviyesinde değilse (destek bekleniyor veya kırılım teyidi bekleniyorsa), hedef giriş fiyatı ve stop planı belirleyerek izleme listesine (`watchlist`) ekle.
  - `DROP`: Trendi bozuk, tezi çökmüş veya 14 günlük izleme süresi dolmuş hisseleri takipten çıkar.

---

## 📤 decisions.json Dosya Şeması ve Formatı

Komitenin üreteceği `decisions.json` dosyası şu standart yapıda olmalıdır:

```json
{
  "decisions_date": "YYYY-MM-DD",
  "circuit_breaker_acknowledged": "TRADING_ALLOWED | COOLDOWN | HALTED",
  "committee_overall_note": "Piyasa genel görünümü ve bugünkü kararların ana mantığı.",
  "decisions": [
    {
      "ticker": "AAPL",
      "action": "BUY | SELL | WAIT_BUY | HOLD | DROP",
      "shares": 2.05,
      "price": 338.32,
      "stop_loss": 325.80,
      "take_profit": 375.00,
      "target_entry_price": 335.00,
      "stop_loss_plan": 320.00,
      "thesis": "Mark Minervini Stage 2 teyidi, 52 haftalık zirveye yakın taban konsolidasyonu, MACD pozitif.",
      "reason": "11 disiplin kuralından başarıyla geçti. Risk $25.70 (%0.73) bütçe dahilinde."
    }
  ]
}
```

---

## ⚡ Çalıştırma ve Otomasyon Komut Dizisi

Günlük çalışma rutini Antigravity tarafından tek oturumda şu sırayla yürütülür:

```bash
# 1. Günlük kuyruk ve veri paketini hazırla
.venv/bin/python prepare_daily_batch.py

# 2. daily_briefing.json incelenir, 11 kural işletilir ve decisions.json dosyası yazılır (AGY tarafından)

# 3. Kararlar icra edilir, kasa ve PORTFOLIO_DASHBOARD.md güncellenir
.venv/bin/python execute_decisions.py
```

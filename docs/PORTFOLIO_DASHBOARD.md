# 📊 PORTFOLIO DASHBOARD (Paper Trading)
**Son Güncelleme:** 2026-11-07 18:36:11  |  **Tarih:** 2026-11-04

## 1. Portföy Özeti
| Metrik | Değer |
|---|---|
| **Nakit Bakiye (Cash)** | `$2,955.50` |
| **Hisse Pozisyon Değeri** | `$543.00` |
| **Toplam Varlık (Total Equity)** | `$3,498.50` |
| **Başlangıç Sermayesi** | `$3,500.00` |
| **Toplam Net Kâr / Zarar** | `$-1.50` (`-0.04%`) |
| **Ödenen Toplam Komisyon** | `$1.50` (Midas 1.50$/işlem) |
| **Maksimum Pozisyon Limiti** | `%20` (Maks `$699.70`) |

### 📈 Kasa Dağılımı (ASCII Görünüm)
```text
Nakit Oranı  [█████████████████████░░░░] % 84.5
Hisse Oranı  [████░░░░░░░░░░░░░░░░░░░░░] % 15.5
```

## 2. Açık Pozisyonlar (`open_positions`)
| Sembol | Adet | Alış Fiyatı | Güncel Fiyat | Piyasa Değeri | Kâr/Zarar ($) | Kâr/Zarar (%) | Stop-Loss | Kâr Al (TP) | Yatırım Tezi |
|---|---|---|---|---|---|---|---|---|---|
| **MRK** | 3.66 | `$148.36` | `$148.36` | `$543.00` | `$+0.00` | `+0.00%` | `$138.80` | `$168.00` | Minervini Stage 2 tam puanı (100/100). Fiyat SMA50, SMA150 ve SMA200 üzerinde. 52 haftalık zirvesine %5 mesafede dar konsolidasyon sergiliyor. RSI(14)=58.4 dengeli bölgede ve MACD pozitif momentum teyidi veriyor. |

## 3. İzleme Listesi (`watchlist`)
| Sembol | Eklenme Tarihi | Son Geçerlilik | Hedef Giriş Fiyatı | Planlanan Stop | Durum | Gerekçe |
|---|---|---|---|---|---|---|
| **LLY** | 2026-11-04 | 2026-11-18 | `$1350.00` | `$1285.00` | `WAIT_BUY` | Tepe kovalamama kuralı işletildi. SMA50'ye doğru $1350.00 seviyesinde bir geri çekilme (pullback) beklenmek üzere 14 günlük süreyle izleme listesine eklendi. |
| **MSFT** | 2026-11-04 | 2026-11-18 | `$500.00` | `$480.00` | `WAIT_BUY` | Düşen bıçak tutmama kuralı. $500.00 psikolojik desteğinin test edilip taban oluşturması beklenmek üzere izleme listesine alındı. |

## 4. Son İşlem Geçmişi (`trade_history` - Son 10 İşlem)
| Tarih | Sembol | İşlem | Adet | Fiyat | Komisyon | Net PnL ($) | Komite Özeti |
|---|---|---|---|---|---|---|---|
| 2026-11-04 | **MRK** | `BUY` | 3.66 | `$148.36` | `$1.50` | - | Minervini Stage 2 tam puanı (100/100). Fiyat SMA50, SMA150 ve SMA200 üzerinde. 52 haftalık zirvesine %5 mesafede dar konsolidasyon sergiliyor. RSI(14)=58.4 dengeli bölgede ve MACD pozitif momentum teyidi veriyor. |

## 5. Bugünkü Komite Karar Özeti
**Devre Kesici Onayı:** `TRADING_ALLOWED`
**Komite Genel Notu:** Devre kesici TRADING_ALLOWED durumunda; hesap yeni risk alımına açık. Analiz edilen 5 hisse arasından Minervini Stage 2 kriterlerini kusursuz sağlayan ve RSI'ı ideal dengede (58.4) olan MRK için AL (BUY) kararı üretildi. Aşırı alımdaki LLY (RSI 81.9) ve dip arayışındaki MSFT (RSI 27.8) disiplin kuralı gereği hedef pullback fiyatlarıyla izleme listesine (WAIT_BUY) eklendi. Trendi çökmüş ve Stage 2 filtresinden geçemeyen META ve NFLX ise elendi (DROP).

## 6. 11 Ajan Komite Karar Karnesi (Hisse Bazlı Detay)
### 📌 MRK (`$148.36`) — Nihai Karar: `BUY` (✅ 11 | ⚠️ 0 | ❌ 0)
| # | Uzman Ajan / Komite Adımı | Karar | Gerekçe ve Metrikler |
|---|---|---|---|
| **1** | Hesap Devre Kesici (Circuit Breaker) | ✅ ONAY | No account-level circuit breaker rules are active; new trade risk may proceed. |
| **2** | Öncelikli Kuyruk Yönetimi (Queue) | ✅ ONAY | 3. Öncelik: Evren (universe.json) yeni aday keşfi (5 hisse kotası dahilinde). |
| **3** | Minervini Trend Şablonu (Stage 2) | ✅ ONAY | Stage 2 Puanı: 100.0/100 (7/7 kriter geçti) / Fiyat: $148.36 (SMA50: $146.52, SMA150: $129.48, SMA200: $125.71). |
| **4** | Haftalık Fiyat Hareketi & Swing | ✅ ONAY | Haftalık Sinyal: NOT_CONFIRMED (no_reversal_evidence) / Swing Dip: $138.80, Swing Tepe: $153.57, Stop Ref: $138.80. |
| **5** | Hacim ve Momentum (RSI / MACD) | ✅ ONAY | RSI(14): 58.4 / MACD Hist: +0.2901 / 20g Hacim Değişimi: -12.1%. (İdeal momentum ve dengeli RSI bölgesi.) |
| **6** | Temel Değerleme Filtresi (P/E & P/B) | ✅ ONAY | F/K (P/E): 149.86 / PD/DD (P/B): 8.73 — Kurumsal bilanço ve özkaynak yapısı uygun. |
| **7** | Senaryo Analisti (18 Ay Base/Bull/Bear) | ✅ ONAY | 18 Aylık Base/Bull senaryo ağırlıklı pozitif tez: Minervini Stage 2 tam puanı (100/100). Fiyat SMA50, SMA150 ve SMA200 üzerinde. 52 haftalık zirvesine %5 mesafede dar konsolidasyon sergiliyor. RSI(14)=58.4 dengeli bölgede ve MACD pozitif momentum teyidi veriyor. |
| **8** | Şeytanın Avukatı & Risk/Ödül (R:R) | ✅ ONAY | Giriş: $148.36 / Stop: $138.80 / Hedef: $168.00 (R:R = 1:2.1). Kör nokta ve destek testi onaylandı. |
| **9** | Pozisyon Boyutlandırma (%20 / %1 Risk) | ✅ ONAY | Önerilen Adet: 3.66 lot ($543.00 <= %20 kasa tavanı) / Maksimum Risk: $34.99 (%1.00 <= %1.00 kasa riski). |
| **10** | İşlem Öncesi Disiplin Kapısı (5 Kural) | ✅ ONAY | 5/5 Disiplin Kriteri Onaylandı: [✓] Yazılı Tez [✓] Matematiksel Stop [✓] <=%20 Kasa & <=%1 Risk [✓] Devre Kesici Açık [✓] Sıfır Duygusal İşlem. |
| **11** | Nihai Komite Sentezi (Final Decision) | ✅ ONAY | NİHAİ KARAR: BUY (MRK) — 11 disiplin kuralının tamamından onay aldı. Pozisyon tutarı $543.00 (%15.51 <= %20 kasa tavanı). Göze alınan risk $34.99 (%1.00 kasa riski). R:R oranı ~1:2. |

### 📌 LLY (`$1410.99`) — Nihai Karar: `WAIT_BUY` (✅ 4 | ⚠️ 7 | ❌ 0)
| # | Uzman Ajan / Komite Adımı | Karar | Gerekçe ve Metrikler |
|---|---|---|---|
| **1** | Hesap Devre Kesici (Circuit Breaker) | ✅ ONAY | No account-level circuit breaker rules are active; new trade risk may proceed. |
| **2** | Öncelikli Kuyruk Yönetimi (Queue) | ✅ ONAY | 3. Öncelik: Evren (universe.json) yeni aday keşfi (5 hisse kotası dahilinde). |
| **3** | Minervini Trend Şablonu (Stage 2) | ✅ ONAY | Stage 2 Puanı: 100.0/100 (7/7 kriter geçti) / Fiyat: $1410.99 (SMA50: $1200.25, SMA150: $1121.43, SMA200: $1091.20). |
| **4** | Haftalık Fiyat Hareketi & Swing | ⚠️ UYARI | Haftalık Sinyal: NOT_CONFIRMED (continuation_intact) / Swing Dip: $1131.21, Swing Tepe: $1292.65, Stop Ref: $1314.51. |
| **5** | Hacim ve Momentum (RSI / MACD) | ⚠️ UYARI | RSI(14): 81.9 / MACD Hist: +16.5624 / 20g Hacim Değişimi: +38.1%. (Aşırı alım bölgesi (RSI > 72); tepe kovalamama kuralı devrede.) |
| **6** | Temel Değerleme Filtresi (P/E & P/B) | ✅ ONAY | F/K (P/E): 45.80 / PD/DD (P/B): 31.23 — Kurumsal bilanço ve özkaynak yapısı uygun. |
| **7** | Senaryo Analisti (18 Ay Base/Bull/Bear) | ⚠️ UYARI | Uzun vadeli tez pozitif ancak kısa vadeli giriş zamanlaması bekleniyor: Minervini Stage 2 tam puan (100/100) ve güçlü kurumsal lider. Ancak 1 aylık +%23.5 rallinin ardından RSI(14)=81.9 ile aşırı alım bölgesinde. |
| **8** | Şeytanın Avukatı & Risk/Ödül (R:R) | ⚠️ UYARI | Mevcut fiyat ($1410.99) R:R oranını zayıflatıyor; $1350.00 destek/pullback seviyesi ve $1285.00 stop planı bekleniyor. |
| **9** | Pozisyon Boyutlandırma (%20 / %1 Risk) | ⚠️ UYARI | Hedef fiyata ($1350.00) gelindiğinde maks %20 kasa ve %1 risk bütçesiyle (0.36 adet) boyutlandırılacak. |
| **10** | İşlem Öncesi Disiplin Kapısı (5 Kural) | ⚠️ UYARI | Disiplin Kapısı Beklemede: Hisse kaliteli ancak giriş fiyatı/indikatör soğuması gerçekleşmeden erken alıma izin verilmedi. |
| **11** | Nihai Komite Sentezi (Final Decision) | ⚠️ UYARI | NİHAİ KARAR: WAIT_BUY (LLY) — Tepe kovalamama kuralı işletildi. SMA50'ye doğru $1350.00 seviyesinde bir geri çekilme (pullback) beklenmek üzere 14 günlük süreyle izleme listesine eklendi. |

### 📌 MSFT (`$507.12`) — Nihai Karar: `WAIT_BUY` (✅ 5 | ⚠️ 6 | ❌ 0)
| # | Uzman Ajan / Komite Adımı | Karar | Gerekçe ve Metrikler |
|---|---|---|---|
| **1** | Hesap Devre Kesici (Circuit Breaker) | ✅ ONAY | No account-level circuit breaker rules are active; new trade risk may proceed. |
| **2** | Öncelikli Kuyruk Yönetimi (Queue) | ✅ ONAY | 3. Öncelik: Evren (universe.json) yeni aday keşfi (5 hisse kotası dahilinde). |
| **3** | Minervini Trend Şablonu (Stage 2) | ✅ ONAY | Stage 2 Puanı: 71.4/100 (5/7 kriter geçti) / Fiyat: $507.12 (SMA50: $513.39, SMA150: $447.35, SMA200: $437.12). |
| **4** | Haftalık Fiyat Hareketi & Swing | ✅ ONAY | Haftalık Sinyal: CONFIRMED (failed_extreme) / Swing Dip: $348.54, Swing Tepe: $551.15, Stop Ref: $481.54. |
| **5** | Hacim ve Momentum (RSI / MACD) | ⚠️ UYARI | RSI(14): 27.8 / MACD Hist: -3.4594 / 20g Hacim Değişimi: +54.2%. (Aşırı satım / sert satış baskısı (RSI < 32); düşen bıçak tutulmaz.) |
| **6** | Temel Değerleme Filtresi (P/E & P/B) | ✅ ONAY | F/K (P/E): 26.47 / PD/DD (P/B): 8.00 — Kurumsal bilanço ve özkaynak yapısı uygun. |
| **7** | Senaryo Analisti (18 Ay Base/Bull/Bear) | ⚠️ UYARI | Uzun vadeli tez pozitif ancak kısa vadeli giriş zamanlaması bekleniyor: Haftalık fiyat hareketinde dönüş (failed extreme) teyidi mevcut ve Stage 2 puanı 71.4. Ancak RSI=27.8 ile kısa vadeli satış baskısı devam ediyor. |
| **8** | Şeytanın Avukatı & Risk/Ödül (R:R) | ⚠️ UYARI | Mevcut fiyat ($507.12) R:R oranını zayıflatıyor; $500.00 destek/pullback seviyesi ve $480.00 stop planı bekleniyor. |
| **9** | Pozisyon Boyutlandırma (%20 / %1 Risk) | ⚠️ UYARI | Hedef fiyata ($500.00) gelindiğinde maks %20 kasa ve %1 risk bütçesiyle (1.36 adet) boyutlandırılacak. |
| **10** | İşlem Öncesi Disiplin Kapısı (5 Kural) | ⚠️ UYARI | Disiplin Kapısı Beklemede: Hisse kaliteli ancak giriş fiyatı/indikatör soğuması gerçekleşmeden erken alıma izin verilmedi. |
| **11** | Nihai Komite Sentezi (Final Decision) | ⚠️ UYARI | NİHAİ KARAR: WAIT_BUY (MSFT) — Düşen bıçak tutmama kuralı. $500.00 psikolojik desteğinin test edilip taban oluşturması beklenmek üzere izleme listesine alındı. |

### 📌 META (`$606.73`) — Nihai Karar: `DROP` (✅ 2 | ⚠️ 1 | ❌ 8)
| # | Uzman Ajan / Komite Adımı | Karar | Gerekçe ve Metrikler |
|---|---|---|---|
| **1** | Hesap Devre Kesici (Circuit Breaker) | ✅ ONAY | No account-level circuit breaker rules are active; new trade risk may proceed. |
| **2** | Öncelikli Kuyruk Yönetimi (Queue) | ✅ ONAY | 3. Öncelik: Evren (universe.json) yeni aday keşfi (5 hisse kotası dahilinde). |
| **3** | Minervini Trend Şablonu (Stage 2) | ❌ RED | Stage 2 Puanı: 28.6/100 (2/7 kriter geçti) / Fiyat: $606.73 (SMA50: $670.93, SMA150: $628.17, SMA200: $631.21). |
| **4** | Haftalık Fiyat Hareketi & Swing | ❌ RED | Haftalık Sinyal: NOT_CONFIRMED (no_reversal_evidence) / Swing Dip: $536.85, Swing Tepe: $771.27, Stop Ref: $536.85. |
| **5** | Hacim ve Momentum (RSI / MACD) | ❌ RED | RSI(14): 8.2 / MACD Hist: -12.6930 / 20g Hacim Değişimi: -18.2%. (Aşırı satım / sert satış baskısı (RSI < 32); düşen bıçak tutulmaz.) |
| **6** | Temel Değerleme Filtresi (P/E & P/B) | ⚠️ UYARI | F/K (P/E): 20.70 / PD/DD (P/B): 5.69 — Kurumsal bilanço ve özkaynak yapısı uygun. |
| **7** | Senaryo Analisti (18 Ay Base/Bull/Bear) | ❌ RED | Bear Case (ayı senaryosu) baskın; yatırım tezi reddedildi: Minervini Stage 2 filtresinden geçemedi (28.6/100). Fiyat tüm hareketli ortalamalarının (SMA50, SMA150, SMA200) altında, RSI=8.2 ile sert çöküşte. Yatırım tezi geçersiz. |
| **8** | Şeytanın Avukatı & Risk/Ödül (R:R) | ❌ RED | Stop-Loss koruma seviyesi: $536.85 / Risk/Ödül disiplini denetlendi. |
| **9** | Pozisyon Boyutlandırma (%20 / %1 Risk) | ❌ RED | İşlem reddedildiği (DROP) için sermaye tahsisi yapılmadı ($0.00). |
| **10** | İşlem Öncesi Disiplin Kapısı (5 Kural) | ❌ RED | Disiplin Kapısından Geçemedi: Teknik/trend kriterleri sağlanmadığı için alım emri engellendi. |
| **11** | Nihai Komite Sentezi (Final Decision) | ❌ RED | NİHAİ KARAR: DROP (META) — Minervini Stage 2 filtresinden geçemedi (28.6/100). Fiyat tüm hareketli ortalamalarının (SMA50, SMA150, SMA200) altında, RSI=8.2 ile sert çöküşte. Yatırım tezi geçersiz. |

### 📌 NFLX (`$62.34`) — Nihai Karar: `DROP` (✅ 2 | ⚠️ 1 | ❌ 8)
| # | Uzman Ajan / Komite Adımı | Karar | Gerekçe ve Metrikler |
|---|---|---|---|
| **1** | Hesap Devre Kesici (Circuit Breaker) | ✅ ONAY | No account-level circuit breaker rules are active; new trade risk may proceed. |
| **2** | Öncelikli Kuyruk Yönetimi (Queue) | ✅ ONAY | 3. Öncelik: Evren (universe.json) yeni aday keşfi (5 hisse kotası dahilinde). |
| **3** | Minervini Trend Şablonu (Stage 2) | ❌ RED | Stage 2 Puanı: 0.0/100 (0/7 kriter geçti) / Fiyat: $62.34 (SMA50: $72.33, SMA150: $79.43, SMA200: $81.47). |
| **4** | Haftalık Fiyat Hareketi & Swing | ❌ RED | Haftalık Sinyal: NOT_CONFIRMED (no_reversal_evidence) / Swing Dip: $65.08, Swing Tepe: $73.07, Stop Ref: $58.10. |
| **5** | Hacim ve Momentum (RSI / MACD) | ❌ RED | RSI(14): 26.3 / MACD Hist: -0.4524 / 20g Hacim Değişimi: -10.5%. (Aşırı satım / sert satış baskısı (RSI < 32); düşen bıçak tutulmaz.) |
| **6** | Temel Değerleme Filtresi (P/E & P/B) | ⚠️ UYARI | F/K (P/E): 18.02 / PD/DD (P/B): 8.74 — Kurumsal bilanço ve özkaynak yapısı uygun. |
| **7** | Senaryo Analisti (18 Ay Base/Bull/Bear) | ❌ RED | Bear Case (ayı senaryosu) baskın; yatırım tezi reddedildi: Minervini Stage 2 kriterlerinden 0/100 puan aldı. 1 yıllık getiri -%44.3, 52 haftalık dip seviyesinde Stage 4 düşüş trendinde. Listeye alınması uygun değil. |
| **8** | Şeytanın Avukatı & Risk/Ödül (R:R) | ❌ RED | Stop-Loss koruma seviyesi: $58.10 / Risk/Ödül disiplini denetlendi. |
| **9** | Pozisyon Boyutlandırma (%20 / %1 Risk) | ❌ RED | İşlem reddedildiği (DROP) için sermaye tahsisi yapılmadı ($0.00). |
| **10** | İşlem Öncesi Disiplin Kapısı (5 Kural) | ❌ RED | Disiplin Kapısından Geçemedi: Teknik/trend kriterleri sağlanmadığı için alım emri engellendi. |
| **11** | Nihai Komite Sentezi (Final Decision) | ❌ RED | NİHAİ KARAR: DROP (NFLX) — Minervini Stage 2 kriterlerinden 0/100 puan aldı. 1 yıllık getiri -%44.3, 52 haftalık dip seviyesinde Stage 4 düşüş trendinde. Listeye alınması uygun değil. |

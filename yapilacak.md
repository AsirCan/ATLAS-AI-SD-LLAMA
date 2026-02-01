# ATLAS AI – Profesyonel Yol Haritası (v1)

Bu dosya, mevcut kodu inceleyerek “profesyonel seviyede ürün” hedefi için
eklenmesi ve düzeltilmesi gerekenleri öncelikli bir yol haritası halinde listeler.

---

## 1) Kritik Düzeltmeler (Hemen / 0–2 hafta)
- UTF‑8 kodlama standardı: tüm .py/.jsx/.md dosyalarını düzgün UTF‑8 olarak normalize et, mojibake (Ã¶, Ã§ vb.) sorununu temizle.
- `core/sd_client.py`: `response.raise_for_status()` + JSON parse koruması; başarısız yanıtları logla, hataları üst katmana taşı.
- `core/agents/visual_agent.py`: LLM’in ürettiği `negative_prompt` kullanılamıyor; SD payload’a geçir.
- `core/carousel_agent.py`: JSON parse yerine `LLMService.generate_json()` ile şemaya bağlı güvenilir çıktı üret.
- `web/backend/video_generator.py`: `piper` çağrısını `PIPER_BIN`/safe path ile standartlaştır (backend ile tutarlı olsun).
- Global progress state: aynı anda birden fazla görev gelirse çakışma var. Job‑ID tabanlı ilerleme takibi şart.

---

## 2) Mimari & Altyapı
- Tüm “içerik üretim” akışlarını tek bir pipeline altında birleştir (daily + carousel + video).
- “Task Queue” ekle: uzun işler için arka plan worker (Celery + Redis / RQ / Dramatiq).
- `PipelineState`’i job‑ID, timestamps, asset metadata ile genişlet; tüm çıktıları tek yerde topla.
- Konfigürasyonu `Pydantic Settings` ile merkezileştir (ör. `core/config.py` + `.env`).
- SD, LLM ve TTS katmanlarını “service layer” olarak soyutla (tek sorumluluk, test edilebilirlik).

---

## 3) Güvenlik & Gizlilik
- API için basit auth (API key veya local token) + CORS whitelist.
- Instagram session/credential dosyalarını kullanıcı profiline taşı, dosya izinlerini sıkılaştır.
- UGC/risk filtreleri için audit log (hangi haber neden elendi).
- “Live mode” için ek onay/uyarı adımı (UI’da net risk bildirimi).

---

## 4) Performans & Kaynak Yönetimi
- GPU kilidi / tek iş kuralı: LLM ↔ SD geçişinde VRAM yönetimini merkezi bir “resource manager” ile yap.
- `core/llm.py`: retry/backoff stratejisini netleştir, timeout’ları tek yerden konfigüre et.
- Çıktı klasörleri için “retention policy” (örn. 7 gün) + disk kullanım kontrolü.
- Carousel üretiminde batch/queue ve progress yüzdesi (sadece log değil gerçek progress).

---

## 5) Kalite Güvence (Test & Lint)
- Birim testler: agent’lar, prompt builder, risk filtre, JSON şema doğrulama.
- Entegrasyon testleri: FastAPI endpoint’leri (TestClient) + mock LLM/SD.
- Lint/format: `ruff` + `black` + `eslint` + `prettier`.
- CI pipeline (GitHub Actions): test + lint + build.

---

## 6) Ürün & UX
- `ErrorBoundary` ana entry’ye bağlanmalı (`web/frontend/src/main.jsx`).
- Studio ekranında gerçek durumlar: “Servis kontrolü / LLM / SD / Upload” adım göstergesi.
- Üretilen görseller için “metadata panel” (prompt, seed, tarih, haber kaynağı).
- Galeriye filtre/sıralama (tarih, tip, kaynak).
- Sistem durumu paneli: SD/Ollama/FFmpeg/Piper bağlantı kontrolü.

---

## 7) İçerik Kalitesi & Güvenlik
- Haber seçiminde tekrarları engellemek için TTL‑tabanlı “kullanılmış haber” deposu (SQLite).
- Risk filtresine whitelist/blacklist + kategori bazlı eşikler ekle.
- Carousel prompt standardı: tek tema, farklı varyasyon ekseni, consistent kamera/ışık.

---

## 8) Operasyon & Dağıtım
- `uvicorn` production modu (reload kapalı, worker sayısı kontrollü).
- “Tek komut” kurulum: opsiyonel Docker (SD hariç) + `.env` şablonu.
- Log yönetimi: dosya + rotate + minimal telemetri.

---

## 9) Dokümantasyon
- README’yi baştan sadeleştir, net “Quick Start”.
- Her servis için troubleshooting bölümü (Ollama, SD, Piper, FFmpeg).
- “Live upload” şartları ve risk notları (Instagram policy).

---

## 10) Teknik Borç Temizliği
- `daily_visual_agent.py` ve `news_fetcher.py` tekrarlarını birleştir (tek RSS katmanı).
- `run.py` süreç yönetimini iyileştir (exit cleanup, port çakışması, npm path).
- `requirements.txt` ve `package.json` sürüm sabitlemeleri (reproducible build).

---

## 11) İleri Seviye (Opsiyonel)
- Çoklu model desteği (Ollama model switching).
- A/B prompt testleri (otomatik varyasyon + performans metriği).
- Kısa içerik takvimi (weekly planner + scheduler).


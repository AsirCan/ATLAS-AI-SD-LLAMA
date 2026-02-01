# Atlas Assistant (Web + Otonom Ajan)

Bu repo, web arayüzlü bir sesli asistan/üretim stüdyosu ve Instagram için **otonom (multi-agent) içerik üretim ajanı** içerir.

## Özellikler

### Web arayüz (React/Vite)
- **Chat**: `/api/chat` üzerinden Ollama ile sohbet.
- **Görsel çizim**: `/api/image` üzerinden Stable Diffusion (Forge API) ile görsel üretimi.
- **STT/TTS**: `/api/stt` ve `/api/tts` ile konuşma → yazı ve yazı → ses.
- **Instagram Studio**:
  - Günlük tek içerik üretimi (haber → prompt → görsel → caption).
  - 10’lu carousel üretimi.
  - “Otonom ajan”ı UI’den başlatma, adım adım ilerleme ekranı ve canlı log görüntüleme.

### Otonom ajan (Multi-Agent Pipeline)
- **Orchestrator tabanlı pipeline**: haber seçimi → risk filtresi → görsel üretimi → caption → zamanlama → (dry-run veya upload).
- **UI’de anlaşılır durum**:
  - `stage` + yüzde ilerleme + adım listesi + canlı loglar.
  - Ajan çalışırken UI, GPU/VRAM’i yormamak için diğer işlemleri ve navigasyonu kilitler.
- **İptal**:
  - UI’den “İptal Et” ile **güvenli durdurma** (cooperative cancel).
  - Not: Eğer o an Stable Diffusion çiziyorsa, iptal isteği **o adım bitince** uygulanır.

## Kurulum

## Sıfırdan hızlı başlangıç (Windows)

Bu bölüm “hiç bilmeyen” biri için en baştan kullanım adımlarını özetler.

1. Repoyu indir/klonla ve klasöre gir.

2. Python sanal ortamını oluştur ve aktif et:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

3. Kurulum sihirbazını çalıştır (Python paketleri + Forge + model + Ollama model pull):

```powershell
python install.py
```

4. `.env.example` → `.env` yap ve Instagram bilgilerini gir:
   - `INSTA_USERNAME`
   - Şifre UI’den “Instagram Giriş (Kaydet)” ile Windows Credential Manager’a kaydedilir.

5. Uygulamayı başlat:

```powershell
python run.py
```

6. Tarayıcıda açılan arayüzde:
   - **Chat**: yaz/konuş → cevap al.
   - **Studio**: “Günlük Tek İçerik”, “10’lu Carousel” veya “Otonom Ajan”.
   - **Video**: gündem videosu üret.

Notlar:
- Ajan çalışırken UI diğer işlemleri ve navigasyonu kilitler (GPU/VRAM için).
- “İptal Et” butonu **güvenli durdurma** yapar; SD çizim anında ise adım bitince durur.

### Gereksinimler
- **Python**: 3.10+
- **Node.js**: (frontend için)
- **Ollama**: `https://ollama.com/`
- **Stable Diffusion**: Forge veya WebUI API (varsayılan: `127.0.0.1:7860`)
- (Video modunu kullanacaksan) **FFmpeg** sistemde kurulu olmalı.

### TTS (Piper) notu (Windows)
- TTS için `models/` altında şu iki dosya gerekir:
  - `tr_TR-fahrettin-medium.onnx`
  - `tr_TR-fahrettin-medium.onnx.json`
- Windows’ta bazı `pip install piper-tts` kurulumlarında `espeakbridge` eksik olduğu için `/api/tts` hata verebilir.
  - Çözüm: **standalone Piper** (piper.exe) kullan.
  - `.env` içine `PIPER_BIN=C:\...\piper.exe` yaz **veya** `tools/piper/piper.exe` olarak projeye koy (otomatik bulunur).

### Yükleme
1. Bağımlılıkları kur:

```powershell
python install.py
```

2. `.env.example` dosyasını `.env` yap ve gerekli alanları doldur:
   - `INSTA_USERNAME`
   - Şifre UI’den “Instagram Giriş (Kaydet)” ile Windows Credential Manager’a kaydedilir.

## Çalıştırma

### Web UI (önerilen)
Backend + Frontend’i birlikte başlatır ve tarayıcıyı açar:

```powershell
python run.py
```

### CLI: Otonom ajan
UI olmadan, doğrudan pipeline çalıştırır:

**Dry Run (Instagram’a yüklemez)**

```powershell
python run.py --agent
```

**Live Mode (Instagram’a yükler)**

```powershell
python run.py --agent --live
```

## API (kısa özet)
- **Chat**: `POST /api/chat`
- **Image**: `POST /api/image`
- **STT**: `POST /api/stt`
- **TTS**: `POST /api/tts`
- **Ajan başlat**: `POST /api/agent/run?live=false|true`
- **Ajan durum**: `GET /api/agent/progress` (status/percent/stage/current_task/logs/…)
- **Ajan iptal**: `POST /api/agent/cancel` (cooperative cancel)

## Mimari (dosya düzeyi)
- **Backend (FastAPI)**: `web/backend/main.py`
- **Frontend (React/Vite)**: `web/frontend/`
- **Agent Orchestrator**: `core/orchestrator.py`
- **Agent’lar**: `core/agents/`
  - `NewsAgent` → haberleri toplar ve skorlar
  - `RiskAgent` → güvenlik filtresi
  - `VisualDirectorAgent` → görsel prompt + SD çizim
  - `CaptionAgent` → caption üretimi
  - `SchedulerAgent` → paylaşım zamanı
- **LLM katmanı (tek yol)**: `core/llm.py` (`LLMService` + legacy wrapper’lar)
- **Stable Diffusion istemcisi**: `core/sd_client.py`

## Otonom ajan algoritması (adım adım)

### 0) UI/Backend koordinasyonu
- UI, `POST /api/agent/run` ile background job başlatır.
- UI, `GET /api/agent/progress` ile her saniye durum çeker:
  - `status`: `idle | running | done | error | cancelled`
  - `stage`: `services_check | init | news | risk | visual | caption | schedule | publish | done | error | cancelled`
  - `percent`: 0–100
  - `logs`: canlı log satırları
- UI, ajan çalışırken diğer işlemleri ve sidebar navigasyonunu kilitler (VRAM/GPU yükünü azaltmak için).
- UI’den `POST /api/agent/cancel` ile iptal isteği gönderilebilir (cooperative).

### 1) Servis kontrolü (backend)
1. Ollama portu kontrol edilir; çalışmıyorsa başlatılır.
2. Stable Diffusion (Forge API) portu kontrol edilir; çalışmıyorsa başlatılır ve hazır olana kadar beklenir.
3. Bu bekleme sırasında cancel flag set edilirse job güvenli şekilde durur.

### 2) Orchestrator pipeline (core)
Orchestrator aşağıdaki sırayla ilerler (her adım loglanır ve UI’ye yansır):
1. **News Gathering**: RSS kaynaklarından haberleri alır ve skorlar.
2. **Risk Analysis**: marka güvenliği/risk filtresi uygular.
3. **Visual Generation**: seçilen haberden görsel prompt üretir ve SD ile görsel çizer.
4. **Captioning**: caption üretir.
5. **Scheduling**: paylaşım zamanı belirler.
6. **Publishing**:
   - Dry-run ise upload atlanır.
   - Live ise Instagram upload yapılır.

### 3) Tamamlama
- Başarılı: `status=done`, `percent=100`
- İptal: `status=cancelled` (cooperative)
- Hata: `status=error` + `error` alanı
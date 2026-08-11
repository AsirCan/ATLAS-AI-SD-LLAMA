import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import speech_recognition as sr

# Add root directory to path to allow importing core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import requests
import uvicorn
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import core modules
# Config is safe to import early
try:
    from core.runtime.config import GREEN, RED, RESET, YELLOW
except ImportError:
    # Fallback colors if config is missing (unlikely)
    RED, YELLOW, GREEN, RESET = "", "", "", ""

# API token dogrulamasi. Import edilemezse koruma acilamaz; bunu sessizce
# gecmek yerine acikca belirtiyoruz ki guvenlik durumu gorunur olsun.
try:
    from core.runtime import jobs
    from core.runtime.api_auth import HEADER_NAME as AUTH_HEADER_NAME
    from core.runtime.api_auth import is_authorized, read_api_token
except ImportError as e:
    print(f"{RED}⚠️ api_auth yuklenemedi ({e}); /api/* korumasiz calisacak.{RESET}")
    AUTH_HEADER_NAME = "X-Atlas-Token"

    def read_api_token():
        return ""

    def is_authorized(provided, expected=None):
        return False

try:
    from core.clients.insta_client import login_and_upload, login_and_upload_album, prepare_insta_caption
    from core.clients.llm import llm_answer, ollama_warmup, visual_prompt_generator
    from core.clients.sd_client import resim_ciz
    from core.content.daily_visual_agent import gunluk_instagram_gorseli_uret
    from core.runtime.system_check import ensure_sd_running

    # We will implement custom TTS logic here to avoid playing on server
    # Import model config (no local playback, config only)
    from core.runtime.tts_config import PIPER_BIN, PIPER_CONFIG, PIPER_MODEL
except ImportError as e:
    print(f"Warning: Could not import core modules: {e}")
    # Define fallback if import fails (so execution doesn't crash)
    PIPER_MODEL = "models/tr_TR-fahrettin-medium.onnx"
    PIPER_CONFIG = "models/tr_TR-fahrettin-medium.onnx.json"
    PIPER_BIN = "piper"

# SAFE PIPER EXECUTION LOGIC
# Windows often fails when tools run from paths with non-ASCII chars (like 'Ses_Asistanı').
# We copy Piper AND Models to a temp dir to ensure everything runs from a clean path.
SAFE_PIPER_BIN = None
SAFE_PIPER_DIR = None


def setup_safe_piper():
    global SAFE_PIPER_BIN, SAFE_PIPER_DIR
    try:
        # 1. Find original Piper directory
        if os.path.exists("tools/piper/piper.exe"):
            original_piper_dir = os.path.abspath("tools/piper")
        elif os.path.exists(PIPER_BIN) and os.path.isabs(PIPER_BIN):
            original_piper_dir = os.path.dirname(PIPER_BIN)
        else:
            print(f"{YELLOW}⚠️ Piper not found locally, skipping safe setup.{RESET}")
            SAFE_PIPER_BIN = PIPER_BIN  # Fallback
            return

        # 2. Define safe temp path
        # Use user's temp dir which is usually safe (e.g. C:\Users\User\AppData\Local\Temp)
        # tempfile.gettempdir(): os.environ["TEMP"] POSIX'te KeyError firlatiyordu.
        safe_dir = os.path.join(tempfile.gettempdir(), "atlas_safe_piper")
        SAFE_PIPER_DIR = safe_dir

        # 3. Clean and Copy Piper Binaries
        if os.path.exists(safe_dir):
            try:
                shutil.rmtree(safe_dir)
            except Exception as e:
                print(f"{YELLOW}⚠️ Could not clean safe piper dir: {e}{RESET}")

        print(f"{YELLOW}🛠️ Setting up safe Piper environment in {safe_dir}...{RESET}")
        shutil.copytree(original_piper_dir, safe_dir)

        # 4. Copy Models to Safe Dir
        # We need to copy the model files to the safe directory so their paths are also clean.
        safe_models_dir = os.path.join(safe_dir, "models")
        os.makedirs(safe_models_dir, exist_ok=True)

        # PIPER_MODEL is relative "models/..."
        # We resolve it relative to current working directory (project root)
        local_model_path = os.path.abspath(PIPER_MODEL)
        local_config_path = os.path.abspath(PIPER_CONFIG)

        if os.path.exists(local_model_path):
            shutil.copy2(local_model_path, safe_models_dir)
            shutil.copy2(local_config_path, safe_models_dir)
            print(f"{GREEN}✅ Models copied to safe dir.{RESET}")
        else:
            print(f"{RED}⚠️ Models not found at {local_model_path}{RESET}")

        SAFE_PIPER_BIN = os.path.join(safe_dir, "piper.exe")
        print(f"{GREEN}✅ Safe Piper ready: {SAFE_PIPER_BIN}{RESET}")

    except Exception as e:
        print(f"{RED}❌ Safe Piper setup failed: {e}{RESET}")
        SAFE_PIPER_BIN = PIPER_BIN  # Fallback


app = FastAPI(title="Ses Asistanı API", version="1.0.0")

# ==================================================
# GUVENLIK
# Bu backend yerel kullanim icin tasarlandi ve 127.0.0.1'e baglanir.
# Cloudflare tuneli artik bu servise DEGIL, yalnizca statik gorsel sunan
# web/backend/image_server.py'ye baglanir (bkz. tools/setup_tunnel.py).
# Ek savunma hatti olarak /api/* uclari paylasimli token ile korunur.
# ==================================================

# Izinli origin listesi. Varsayilan: yerel Vite dev sunucusu.
_DEFAULT_ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
_env_origins = (os.getenv("ALLOWED_ORIGINS") or "").strip()
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _DEFAULT_ALLOWED_ORIGINS
)

# Token dogrulamasi gerektirmeyen yollar.
_PUBLIC_PATHS = {"/", "/robots.txt", "/healthz"}
_PUBLIC_PREFIXES = ("/images/", "/videos/", "/docs", "/openapi.json", "/redoc")


def _is_public_path(path: str) -> bool:
    if path in _PUBLIC_PATHS:
        return True
    return path.startswith(_PUBLIC_PREFIXES)


@app.middleware("http")
async def api_token_middleware(request, call_next):
    """
    /api/* uclarini X-Atlas-Token basligi ile korur.

    Token .env icindeki ATLAS_API_TOKEN'dan okunur; run.py ilk calistirmada
    uretir ve frontend'e VITE_ATLAS_API_TOKEN olarak aktarir.
    """
    path = request.url.path

    # CORS preflight istekleri token tasiyamaz; CORS katmani cevaplasin.
    if request.method == "OPTIONS":
        return await call_next(request)

    if not path.startswith("/api/") or _is_public_path(path):
        return await call_next(request)

    expected = read_api_token()
    if not expected:
        # Token hic kurulmamis: yerel gelistirme icin gecis ver ama uyar.
        if not getattr(app.state, "warned_missing_token", False):
            print(
                f"{YELLOW}⚠️ ATLAS_API_TOKEN tanimli degil; /api/* korumasiz calisiyor. "
                f"'python run.py' ile baslatmak token uretir.{RESET}"
            )
            app.state.warned_missing_token = True
        return await call_next(request)

    provided = request.headers.get(AUTH_HEADER_NAME) or request.query_params.get("token")
    if not is_authorized(provided, expected):
        return JSONResponse(
            status_code=401,
            content={"detail": "Gecersiz veya eksik API token."},
        )

    return await call_next(request)


# CORS, auth middleware'inden SONRA eklenir; boylece dista kalir ve
# preflight isteklerini token kontrolune takilmadan cevaplayabilir.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", AUTH_HEADER_NAME],
)

# Mount generated images directory
IMAGES_DIR = Path("generated_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

# Mount generated videos directory
# Mount generated videos directory
VIDEOS_DIR = Path("generated_videos")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")

# Mount temp directory for TTS
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)


class ChatRequest(BaseModel):
    message: str


class ImageRequest(BaseModel):
    prompt: str


class TTSRequest(BaseModel):
    text: str


class InstaUploadRequest(BaseModel):
    image_path: str
    caption: str


class InstaCarouselUploadRequest(BaseModel):
    image_paths: list[str]
    caption: str


class InstaCredentialsRequest(BaseModel):
    username: str
    password: str


class InstaGraphConfigRequest(BaseModel):
    fb_app_id: str = ""
    fb_app_secret: str = ""
    fb_page_id: str = ""
    ig_user_id: str = ""
    fb_access_token: str = ""
    public_base_url: str = ""
    ig_graph_version: str = "v24.0"


class ImgBBConfigRequest(BaseModel):
    imgbb_api_key: str = ""


@app.get("/")
def read_root():
    return {"status": "online", "message": "Ses Asistanı Backend Running"}


@app.get("/robots.txt")
def robots_txt():
    return Response(content="User-agent: *\nAllow: /\n", media_type="text/plain")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        response = llm_answer(req.message)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/image")
def image_endpoint(req: ImageRequest):
    try:
        # Step 1: Optimize prompt
        english_prompt = visual_prompt_generator(req.prompt)

        # Step 2: Generate Image
        import time

        start_time = time.time()
        success, file_path, used_prompt = resim_ciz(english_prompt)
        end_time = time.time()
        duration = round(end_time - start_time, 2)

        if success and file_path:
            # Convert absolute path to relative URL
            # file_path is like generated_images/2025-01-17/atlas_001.png
            # We need to extract the part after generated_images
            rel_path = os.path.relpath(file_path, str(IMAGES_DIR))
            # Cache-buster ekliyoruz (?v=...)
            image_url = f"http://127.0.0.1:8000/images/{rel_path}?v={uuid.uuid4()}".replace("\\", "/")
            return {
                "success": True,
                "original": req.prompt,
                "optimized_prompt": used_prompt,
                "image_url": image_url,
                "duration": duration,
            }
        else:
            return {"success": False, "error": "Image generation failed"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress")
async def progress_endpoint():
    try:
        # Proxy to SD Forge progress API
        r = requests.get("http://127.0.0.1:7860/sdapi/v1/progress", timeout=2)
        if r.status_code == 200:
            data = r.json()
            return data
        return {"progress": 0, "state": {}}
    except Exception as e:
        print(f"Progress Error: {e}")
        return {"progress": 0, "state": {}}


@app.post("/api/news/generate")
def news_generate_endpoint():
    try:
        # 1. Run the daily visual agent logic
        # It returns: (success, file_path, prompt_or_error)
        import time

        start_time = time.time()
        success, file_path, extra_data = gunluk_instagram_gorseli_uret()
        end_time = time.time()
        duration = round(end_time - start_time, 2)

        if success and file_path:
            # Generate a caption using the news/prompt data
            news_text = extra_data.get("news", "")
            prompt_text = extra_data.get("prompt", "")

            caption = prepare_insta_caption(news_text)

            # Convert absolute path to relative API URL for frontend display
            rel_path = os.path.relpath(file_path, str(IMAGES_DIR))
            image_url = f"http://127.0.0.1:8000/images/{rel_path}?v={uuid.uuid4()}".replace("\\", "/")

            return {
                "success": True,
                "image_url": image_url,
                "image_path": file_path,  # Keep absolute path for backend upload
                "caption": caption,
                "news_summary": news_text,  # The actual news text
                "prompt": prompt_text,  # The image generation prompt
                "duration": duration,
            }
        else:
            return {"success": False, "error": extra_data or "News generation failed"}
    except Exception as e:
        print(f"News Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Uzun isler (ajan / carousel / video) job-ID tabanli kayit defterinde izlenir.
# Global sozluk kullanilmaz: ayni anda iki is baslatildiginda durumlar
# birbirinin ustune yaziyordu (bkz. core/runtime/jobs.py).


def _start_job(kind: str):
    """
    Yeni is olusturur. Baska bir is devam ediyorsa (409) hata sozlugu doner.

    "Ayni anda tek GPU isi" kurali burada zorlanir; UI kilidine guvenilmez.
    """
    try:
        return jobs.registry.create(kind), None
    except jobs.JobConflict as conflict:
        return None, {
            "success": False,
            "error": str(conflict),
            "active_job": conflict.active_kind,
            "active_job_id": conflict.active_job_id,
        }


@app.get("/api/news/video_progress")
def video_progress_endpoint(job_id: str = None):
    return jobs.registry.snapshot(job_id, kind="video")


def run_video_generation_task(job_id: str):
    job = jobs.registry.get(job_id)
    if job is None:
        return

    job.set_stage("generating", 0, "Haberler taranıyor...")

    try:
        from video_generator import process_daily_news_video

        def progress_callback(payload):
            if isinstance(payload, dict):
                task = payload.get("task") or payload.get("message") or ""
                percent = payload.get("percent")
                if task:
                    job.current_task = str(task)
                    job.log(str(task))
                if percent is not None:
                    try:
                        job.percent = max(0, min(100, int(percent)))
                    except (TypeError, ValueError):
                        pass
                return

            msg = str(payload)
            job.current_task = msg
            job.log(msg)

        success, result = process_daily_news_video(progress_callback)

        if success:
            # Result is absolute path: .../generated_videos/YYYY-MM-DD/filename.mp4
            # We need relative path from generated_videos root
            video_rel_path = os.path.relpath(result, str(VIDEOS_DIR))
            video_url = f"http://127.0.0.1:8000/videos/{video_rel_path}".replace("\\", "/")
            job.finish("done", task="Tamamlandı!", result=video_url)
        else:
            job.finish("error", task=f"Hata: {result}", error=str(result))

    except Exception as e:
        print(f"Background Video Gen Error: {e}")
        job.finish("error", task="Kritik Hata", error=str(e))


@app.post("/api/news/video_generate")
async def news_video_generate_endpoint(background_tasks: BackgroundTasks):
    job, conflict = _start_job("video")
    if conflict:
        return conflict

    background_tasks.add_task(run_video_generation_task, job.id)
    return {"success": True, "job_id": job.id, "message": "Video generation started in background"}


# --- AGENT LOGIC ---

def run_agent_task(job_id: str, live_mode: bool = False):
    job = jobs.registry.get(job_id)
    if job is None:
        return

    job.set_stage("starting", 0, "Agent Başlatılıyor...")

    try:
        from core.pipeline.orchestrator import Orchestrator
        from core.runtime.system_check import ensure_ollama_running, ensure_sd_running

        def set_stage(stage: str, percent: int, task: str):
            job.set_stage(stage, percent, task)

        def is_cancelled() -> bool:
            return job.cancel_requested

        def cancel_guard(where: str) -> bool:
            if is_cancelled():
                job.finish("cancelled", task=f"İptal edildi ({where}).")
                return True
            return False

        # 1. Services Check
        set_stage("services_check", 5, "Servisler kontrol ediliyor (Ollama/SD)...")
        if not ensure_ollama_running(cancel_checker=is_cancelled):
            cancel_guard("servis_kontrol")
            return
        if cancel_guard("servis_kontrol"):
            return
        if not ensure_sd_running(cancel_checker=is_cancelled):
            cancel_guard("servis_kontrol")
            return
        if cancel_guard("servis_kontrol"):
            return

        # 2. Initialize
        set_stage("init", 10, "Ajanlar hazırlanıyor...")
        # We can pass a callback lambda to update progress if we modify orchestrator,
        # but for now we will just run it and assume it takes time.
        # Ideally Orchestrator should yield progress updates.

        dry_run = not live_mode
        orchestrator = Orchestrator(dry_run=dry_run)
        orchestrator.set_cancel_checker(is_cancelled)

        # Orchestrator adim loglarini stage/percent'e esler.
        STEP_STAGES = {
            "Step 1/6": ("news", 20),
            "Step 2/6": ("risk", 35),
            "Step 3/6": ("visual", 55),
            "Step 4/6": ("caption", 70),
            "Step 5/6": ("schedule", 85),
            "Step 6/6": ("publish", 95),
        }

        def log_capture(msg):
            job.log(msg)
            # Son satiri guncel gorev olarak goster (UI dostu)
            job.current_task = msg

            if "[Orchestrator]" in msg:
                for marker, (stage, percent) in STEP_STAGES.items():
                    if marker in msg:
                        job.stage = stage
                        job.percent = percent
                        break

        orchestrator.set_logger(log_capture)

        set_stage("running", 15, "Pipeline çalışıyor...")
        if cancel_guard("pipeline_baslangic"):
            return

        # Synchrounous run
        final_state = orchestrator.run_pipeline()

        # If cancel was requested at any time, surface it as a cancelled status
        if is_cancelled() or (final_state.upload_status and final_state.upload_status.get("message") == "Cancelled"):
            job.finish("cancelled", task="İptal edildi.")
            return

        if final_state.upload_status and final_state.upload_status.get("success"):
            job.finish(
                "done",
                task="İşlem başarıyla tamamlandı.",
                result=final_state.upload_status,
            )
        elif dry_run:
            job.finish(
                "done",
                task="Test Tamamlandı (Dry Run)",
                result={"images": final_state.generated_images} if final_state.generated_images else None,
            )
        else:
            # If upload status exists, bubble the real reason to UI
            reason = (final_state.upload_status or {}).get("message")
            if reason:
                job.finish("error", task=f"Hata: {reason}", error=reason)
            else:
                job.finish(
                    "error",
                    task="İşlem tamamlanamadı.",
                    error="Pipeline bir noktada durdu veya upload başarısız.",
                )

    except Exception as e:
        print(f"Agent Error: {e}")
        job.finish("error", task="Kritik Hata", error=str(e))


def _interrupt_stable_diffusion():
    """Bloke eden bir SD cizimini hizlica uyandirmak icin en iyi cabayla dener."""
    try:
        requests.post("http://127.0.0.1:7860/sdapi/v1/interrupt", timeout=2)
    except requests.RequestException:
        pass


@app.post("/api/agent/cancel")
@app.post("/api/agent/cancel/{job_id}")
async def cancel_agent_endpoint(job_id: str = None):
    """
    Cooperative cancel:
    - Sets a flag checked by the background job between steps.
    - If SD generation is in progress, also sends Forge interrupt for faster stop.

    job_id verilmezse en son ajan isi iptal edilir (geriye donuk uyumluluk).
    """
    job = jobs.registry.request_cancel(job_id, kind="agent")
    if job is None:
        return {"success": False, "error": "Agent is not running."}

    _interrupt_stable_diffusion()
    return {"success": True, "job_id": job.id, "message": "Cancel requested"}


@app.post("/api/agent/run")
async def run_agent_endpoint(background_tasks: BackgroundTasks, live: bool = False):
    job, conflict = _start_job("agent")
    if conflict:
        return conflict

    background_tasks.add_task(run_agent_task, job.id, live_mode=live)
    return {"success": True, "job_id": job.id, "message": "Autonomous Agent started"}


@app.get("/api/agent/progress")
@app.get("/api/agent/progress/{job_id}")
def agent_progress_endpoint(job_id: str = None):
    """job_id verilmezse en son ajan isi dondurulur (geriye donuk uyumluluk)."""
    return jobs.registry.snapshot(job_id, kind="agent")


# --- CAROUSEL LOGIC ---


def run_carousel_generation_task(job_id: str):
    job = jobs.registry.get(job_id)
    if job is None:
        return

    job.set_stage("generating", 0, "Gündem taranıyor...")

    try:
        from core.content.carousel_agent import generate_carousel_content

        def progress_callback(msg):
            # "LAYER_UPDATE:" oneki UI icin temizlenir
            clean_msg = msg.replace("LAYER_UPDATE:", "") if msg.startswith("LAYER_UPDATE:") else msg
            job.current_task = clean_msg
            job.log(clean_msg)

        success, images, caption = generate_carousel_content(progress_callback)

        if success:
            # Görselleri URL'e çevir
            image_urls = []
            for img in images:
                abs_path = img["path"]
                rel_path = os.path.relpath(abs_path, str(IMAGES_DIR))
                url = f"http://127.0.0.1:8000/images/{rel_path}?v={uuid.uuid4()}".replace("\\", "/")
                image_urls.append(
                    {
                        "url": url,
                        "prompt": img["prompt"],
                        "path": abs_path,  # Upload için lazım
                    }
                )

            job.finish(
                "done",
                task="Tamamlandı!",
                result={"images": image_urls, "caption": caption},
            )
        else:
            # Hata mesajı caption içinde dönüyor agent'ta
            job.finish("error", task="Hata oluştu.", error=str(caption))

    except Exception as e:
        print(f"Carousel Gen Error: {e}")
        job.finish("error", task="Kritik Hata", error=str(e))


@app.post("/api/carousel/generate")
async def carousel_generate_endpoint(background_tasks: BackgroundTasks):
    job, conflict = _start_job("carousel")
    if conflict:
        return conflict

    background_tasks.add_task(run_carousel_generation_task, job.id)
    return {"success": True, "job_id": job.id, "message": "Carousel generation started"}


@app.get("/api/carousel/progress")
def carousel_progress_endpoint(job_id: str = None):
    return jobs.registry.snapshot(job_id, kind="carousel")


@app.post("/api/instagram/upload")
async def instagram_upload_endpoint(req: InstaUploadRequest):
    try:
        token_status = _graph_token_status_from_env()
        if token_status.get("configured"):
            if not token_status.get("success"):
                return {
                    "success": False,
                    "message": "Graph token kontrolu basarisiz. Token durumunu UI'dan yenileyip tekrar dene.",
                }
            if not token_status.get("is_valid", False):
                return {
                    "success": False,
                    "message": "FB_ACCESS_TOKEN gecersiz veya suresi dolmus. Graph Explorer'dan yeni token alip UI'dan kaydet.",
                }
        success, message = login_and_upload(req.image_path, req.caption)
        return {"success": success, "message": message}
    except Exception as e:
        print(f"Insta Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/carousel/upload")
async def carousel_upload_endpoint(req: InstaCarouselUploadRequest):
    try:
        success, message = login_and_upload_album(req.image_paths, req.caption)
        return {"success": success, "message": message}
    except Exception as e:
        print(f"Carousel Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/instagram/credentials")
async def instagram_credentials_endpoint(req: InstaCredentialsRequest):
    """
    Stores Instagram credentials in OS credential manager (keyring).
    This avoids keeping passwords in .env.
    """
    try:
        from core.clients.insta_client import set_instagram_credentials

        set_instagram_credentials(req.username, req.password)
        return {"success": True, "message": "Credentials saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/instagram/session/reset")
async def instagram_session_reset_endpoint():
    """Deletes insta_session.json to force a fresh login next upload."""
    try:
        from core.clients.insta_client import reset_instagram_session

        ok = reset_instagram_session()
        return {"success": bool(ok)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/instagram/graph-config")
async def instagram_graph_config_endpoint(req: InstaGraphConfigRequest):
    """Saves Graph API fields into .env for first-time setup from UI."""
    try:
        values = _upsert_env_values(
            {
                "FB_APP_ID": req.fb_app_id,
                "FB_APP_SECRET": req.fb_app_secret,
                "FB_PAGE_ID": req.fb_page_id,
                "IG_USER_ID": req.ig_user_id,
                "FB_ACCESS_TOKEN": req.fb_access_token,
                "PUBLIC_BASE_URL": req.public_base_url,
                "IG_GRAPH_VERSION": req.ig_graph_version or "v24.0",
            }
        )
        ready = all(
            values.get(k, "").strip()
            for k in [
                "FB_APP_ID",
                "FB_APP_SECRET",
                "FB_PAGE_ID",
                "IG_USER_ID",
                "FB_ACCESS_TOKEN",
                "PUBLIC_BASE_URL",
            ]
        )
        return {"success": True, "graph_ready": ready}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/instagram/graph-config")
async def instagram_graph_config_get_endpoint():
    """Returns Graph API setup completeness for UI status badges."""
    try:
        env_path = Path(".env")
        values = {}
        if env_path.exists():
            for ln in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = ln.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                values[k.strip()] = v.strip()

        keys = ["FB_APP_ID", "FB_APP_SECRET", "FB_PAGE_ID", "IG_USER_ID", "FB_ACCESS_TOKEN", "PUBLIC_BASE_URL"]
        filled = [k for k in keys if values.get(k)]
        return {
            "success": True,
            "graph_ready": len(filled) == len(keys),
            "filled_count": len(filled),
            "required_count": len(keys),
            "public_base_url": values.get("PUBLIC_BASE_URL", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/instagram/token-status")
async def instagram_token_status_endpoint():
    """Returns Graph access token validity and expiration status."""
    try:
        return _graph_token_status_from_env()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/imgbb/config")
async def imgbb_config_post_endpoint(req: ImgBBConfigRequest):
    """Saves ImgBB API Key to .env"""
    try:
        _upsert_env_values({"IMGBB_API_KEY": req.imgbb_api_key})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _mask_secret(value: str) -> str:
    """Sirri geri dondurmeden 'dolu mu' bilgisini gosterebilmek icin maskeler."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= 4:
        return "*" * len(v)
    return f"{'*' * (len(v) - 4)}{v[-4:]}"


@app.get("/api/imgbb/config")
async def imgbb_config_get_endpoint():
    """
    ImgBB ayarinin durumunu dondurur.

    API key'in kendisi ASLA dondurulmez; yalnizca kurulu olup olmadigi ve
    son 4 hanesi gonderilir. Anahtar alani UI'da yalniz-yazilir olarak calisir.
    """
    try:
        values = _read_env_values()
        key = values.get("IMGBB_API_KEY", "").strip()
        return {
            "success": True,
            "configured": bool(key),
            "masked": _mask_secret(key),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def remove_file(path: str):
    try:
        os.remove(path)
    except Exception:
        pass


def _upsert_env_values(env_updates: dict):
    env_path = Path(".env")
    existing = {}
    lines = []

    if env_path.exists():
        raw = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        lines = raw[:]
        for ln in raw:
            s = ln.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            existing[k.strip()] = v

    for key, value in env_updates.items():
        if value is None:
            continue
        value = str(value).strip()
        updated = False
        for i, ln in enumerate(lines):
            if ln.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}")
        existing[key] = value

    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return existing


def _read_env_values():
    env_path = Path(".env")
    values = {}
    if env_path.exists():
        for ln in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def _graph_token_status_from_env():
    values = _read_env_values()
    app_id = values.get("FB_APP_ID", "").strip()
    app_secret = values.get("FB_APP_SECRET", "").strip()
    access_token = values.get("FB_ACCESS_TOKEN", "").strip()

    configured = bool(app_id and app_secret and access_token)
    if not configured:
        return {
            "success": True,
            "configured": False,
            "is_valid": False,
            "needs_refresh": False,
            "message": "Token kontrolu icin FB_APP_ID, FB_APP_SECRET ve FB_ACCESS_TOKEN gerekli.",
        }

    app_token = f"{app_id}|{app_secret}"
    try:
        r = requests.get(
            "https://graph.facebook.com/debug_token",
            params={"input_token": access_token, "access_token": app_token},
            timeout=20,
        )
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok:
            return {
                "success": False,
                "configured": True,
                "is_valid": False,
                "needs_refresh": True,
                "message": f"Token debug hatasi: {body or r.text}",
            }

        data = body.get("data", {}) if isinstance(body, dict) else {}
        is_valid = bool(data.get("is_valid"))
        expires_at = int(data.get("expires_at") or 0)
        data_access_expires_at = int(data.get("data_access_expires_at") or 0)
        now = int(time.time())
        expires_in = None if expires_at <= 0 else max(0, expires_at - now)
        needs_refresh = (not is_valid) or (expires_in is not None and expires_in < 7 * 24 * 3600)

        return {
            "success": True,
            "configured": True,
            "is_valid": is_valid,
            "needs_refresh": needs_refresh,
            "expires_at": expires_at if expires_at > 0 else None,
            "expires_in_seconds": expires_in,
            "data_access_expires_at": data_access_expires_at if data_access_expires_at > 0 else None,
            "scopes": data.get("scopes", []),
            "type": data.get("type"),
            "app_id": data.get("app_id"),
            "message": "ok" if is_valid else "Token invalid.",
        }
    except Exception as e:
        return {
            "success": False,
            "configured": True,
            "is_valid": False,
            "needs_refresh": True,
            "message": f"Token debug istegi basarisiz: {e}",
        }


@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest, background_tasks: BackgroundTasks):
    """
    Generates TTS audio and returns the file.
    Does NOT play on server.
    """
    try:
        print(f"{YELLOW}🎤 TTS İstendi: {req.text}{RESET}")
        print(f"   Model Yolu: {PIPER_MODEL}")
        print(f"   Piper Bin: {PIPER_BIN}")

        if not os.path.exists(PIPER_MODEL):
            print(f"{RED}❌ HATA: Model dosyası bulunamadı! {PIPER_MODEL}{RESET}")
            raise HTTPException(status_code=500, detail="Model file not found backend")
        if isinstance(PIPER_BIN, str) and (os.path.isabs(PIPER_BIN) or os.path.sep in PIPER_BIN):
            if not os.path.exists(PIPER_BIN):
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Piper executable not found: {PIPER_BIN}. "
                        "Set PIPER_BIN to a valid piper.exe path (standalone Piper recommended on Windows)."
                    ),
                )

        filename = f"tts_{uuid.uuid4()}.wav"
        output_path = TEMP_DIR / filename

        # Write text to temporary file (avoids stdin encoding issues on Windows)
        text_filename = f"tts_input_{uuid.uuid4()}.txt"
        text_path = TEMP_DIR / text_filename

        with open(text_path, "w", encoding="utf-8") as f:
            f.write(req.text)


        # Run Piper from FULLY ISOLATED environment
        # All paths (Exe, Model, Config, Output, CWD) will be in %TEMP% (Safe, ASCII)

        if SAFE_PIPER_BIN and SAFE_PIPER_DIR:
            executable = SAFE_PIPER_BIN
            cwd_dir = SAFE_PIPER_DIR

            # Model filename from config
            model_filename = os.path.basename(PIPER_MODEL)
            config_filename = os.path.basename(PIPER_CONFIG)

            safe_model_path = os.path.join(SAFE_PIPER_DIR, "models", model_filename)
            safe_config_path = os.path.join(SAFE_PIPER_DIR, "models", config_filename)

            # Temporary output in safe dir
            safe_output_filename = f"out_{uuid.uuid4()}.wav"
            safe_output_path = os.path.join(SAFE_PIPER_DIR, safe_output_filename)

        else:
            # Fallback to mixed mode (might fail on Windows)
            executable = PIPER_BIN
            cwd_dir = os.path.dirname(os.path.abspath(PIPER_BIN)) if os.path.exists("tools/piper") else os.getcwd()
            safe_model_path = os.path.abspath(PIPER_MODEL)
            safe_config_path = os.path.abspath(PIPER_CONFIG)
            safe_output_path = os.path.abspath(str(output_path))

        cmd = [
            executable,
            "-m",
            safe_model_path,
            "-c",
            safe_config_path,
            "-f",
            safe_output_path,
            "--length-scale",
            "0.95",
        ]

        # print(f"   Komut: {cmd}")
        # print(f"   CWD: {cwd_dir}")
        # print(f"   Text File: {text_path}")

        try:
            # Use input string directly if file reading is problematic,
            # but usually file input works best for encoding.
            # We'll use the temp text file we already created.
            with open(text_path, encoding="utf-8") as f:
                process = subprocess.run(cmd, stdin=f, capture_output=True, text=True, cwd=cwd_dir)

            if process.returncode != 0:
                print(f"{RED}Piper Error: {process.stderr}{RESET}")
                print(f"{RED}Piper Stdout: {process.stdout}{RESET}")
                raise Exception(process.stderr)

            # Move the safe output to the expected project temp location
            if SAFE_PIPER_DIR and os.path.exists(safe_output_path):
                shutil.move(safe_output_path, str(output_path))
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Piper command not found. "
                    "On Windows, install standalone Piper and set PIPER_BIN to piper.exe, then restart backend."
                ),
            )

        if process.returncode != 0:
            print(f"{RED}Piper Error: {process.stderr}{RESET}")
            stderr = (process.stderr or "").strip()
            if "espeakbridge" in stderr:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "Piper failed due to missing espeak phonemizer component (espeakbridge). "
                        "This commonly happens on Windows with some pip-installed piper-tts builds. "
                        "Fix: download a standalone Piper release (piper.exe) and set PIPER_BIN to its full path, "
                        "then restart backend."
                    ),
                )
            raise Exception(f"TTS Generation failed: {stderr}")

        # Check file size
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            # print(f"   Audio Generated: {size} bytes")
            if size < 100:
                print(f"{RED}⚠️ Audio file too small! Possible silence.{RESET}")
        else:
            print(f"{RED}❌ Audio file missing!{RESET}")

        # Add background tasks to remove files after response is sent
        background_tasks.add_task(remove_file, str(output_path))
        background_tasks.add_task(remove_file, str(text_path))

        # Return file
        return FileResponse(path=output_path, media_type="audio/wav", filename="response.wav")
    except Exception as e:
        print(f"{RED}TTS Endpoint Error: {e}{RESET}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    """
    Accepts an audio file (blob), converts it to proper WAV using ffmpeg/pydub,
    and performs Speech-to-Text.
    """
    temp_in_path = None
    temp_wav_path = None

    try:
        # Pydub import here to ensure it's loaded after install
        from pydub import AudioSegment

        filename = f"stt_in_{uuid.uuid4()}"  # Extension unknown potentially
        temp_in_path = TEMP_DIR / filename

        # Save uploaded bytes (likely WebM/Opus from browser)
        with open(temp_in_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Convert to standard WAV for SpeechRecognition
        # AudioSegment.from_file handles format detection (webm, m4a, etc.)
        audio = AudioSegment.from_file(str(temp_in_path))

        # Export as 16kHz Mono WAV (best for SR)
        temp_wav_path = TEMP_DIR / f"stt_out_{uuid.uuid4()}.wav"
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(str(temp_wav_path), format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(str(temp_wav_path)) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language="tr-TR")
                return {"text": text}
            except sr.UnknownValueError:
                return {"text": ""}
            except sr.RequestError as e:
                raise HTTPException(status_code=500, detail=f"STT Error: {e}")

    except Exception as e:
        print(f"STT Critical Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        try:
            if temp_in_path and os.path.exists(temp_in_path):
                os.remove(temp_in_path)
            if temp_wav_path and os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
        except Exception:
            pass


@app.on_event("startup")
async def startup_event():
    print(f"{YELLOW}🚀 Initializing Backend Services...{RESET}")

    # 1. Start/Check Ollama
    print(f"{YELLOW}🧠 Warming up Ollama...{RESET}")
    try:
        ollama_warmup()
    except Exception as e:
        print(f"{RED}⚠️ Ollama Error: {e}{RESET}")

    # 1.5 Setup Safe Piper (Tmp Dir)
    setup_safe_piper()

    # 2. Start/Check Stable Diffusion
    print(f"{YELLOW}🎨 Checking Stable Diffusion...{RESET}")
    try:
        ensure_sd_running()
    except Exception as e:
        print(f"{RED}⚠️ SD Start Error: {e}{RESET}")


def server_options() -> dict:
    """
    Sunucu calisma secenekleri.

    reload VARSAYILAN OLARAK KAPALI. Acik oldugunda dosya izleyici sunucuyu
    yeniden baslatiyor; uzun suren bir ajan/video isi ortasindaysa is sessizce
    kayboluyor, ilerleme durumu sifirlaniyor ve UI'daki poller askida kaliyor.
    Ayrica yeniden baslatma sirasinda iki surec ayni anda GPU'ya erismeye
    calisabiliyor.

    Gelistirme icin: DEV_RELOAD=1 python web/backend/main.py
    """
    return {
        "host": os.getenv("BACKEND_HOST", "127.0.0.1"),
        "port": int(os.getenv("BACKEND_PORT", "8000")),
        "reload": os.getenv("DEV_RELOAD", "0").strip() == "1",
    }


if __name__ == "__main__":
    options = server_options()

    if options["reload"]:
        print(f"{YELLOW}⚠️ DEV_RELOAD acik: kod degisiminde sunucu yeniden baslar.{RESET}")
        print(f"{YELLOW}   Devam eden ajan/video isleri kaybolabilir.{RESET}")
        # reload yalnizca import string ile calisir.
        uvicorn.run("main:app", host=options["host"], port=options["port"], reload=True)
    else:
        # Tek GPU: birden fazla worker VRAM'i paylasamaz, workers=1 kalmali.
        uvicorn.run(app, host=options["host"], port=options["port"], workers=1)

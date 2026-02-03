import sys
import os
import shutil
import uuid
import subprocess
import time
import speech_recognition as sr
from pathlib import Path

# Add root directory to path to allow importing core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import requests

# Import core modules
# Config is safe to import early
try:
    from core.config import RED, YELLOW, GREEN, RESET
except ImportError:
    # Fallback colors if config is missing (unlikely)
    RED, YELLOW, GREEN, RESET = "", "", "", ""

try:
    from core.llm import llm_answer, visual_prompt_generator
    from core.sd_client import resim_ciz
    from core.daily_visual_agent import gunluk_instagram_gorseli_uret
    from core.insta_client import login_and_upload, prepare_insta_caption, login_and_upload_album
    from core.system_check import ensure_sd_running
    from core.llm import ollama_warmup
    # We will implement custom TTS logic here to avoid playing on server
    
    # Import model config (no local playback, config only)
    from core.tts_config import PIPER_MODEL, PIPER_CONFIG, PIPER_BIN
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
            SAFE_PIPER_BIN = PIPER_BIN # Fallback
            return

        # 2. Define safe temp path
        # Use user's temp dir which is usually safe (e.g. C:\Users\User\AppData\Local\Temp)
        safe_dir = os.path.join(os.environ["TEMP"], "atlas_safe_piper")
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
        SAFE_PIPER_BIN = PIPER_BIN # Fallback
        



app = FastAPI(title="Ses Asistanı API", version="1.0.0")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
                "duration": duration
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
                "image_path": file_path, # Keep absolute path for backend upload
                "caption": caption,
                "news_summary": news_text, # The actual news text
                "prompt": prompt_text, # The image generation prompt
                "duration": duration
            }
        else:
            return {
                "success": False, 
                "error": extra_data or "News generation failed"
            }
    except Exception as e:
        print(f"News Generation Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Global Progress State
VIDEO_PROGRESS = {
    "status": "idle", 
    "percent": 0, 
    "current_task": "",
    "result": None,
    "error": None
}

CAROUSEL_PROGRESS = {
    "status": "idle",
    "percent": 0,
    "current_task": "",
    "result": None, # { images: [], caption: "" }
    "error": None
}

def update_video_progress(task_name):
    print(f"Video Progress: {task_name}")
    VIDEO_PROGRESS["status"] = "generating"
    VIDEO_PROGRESS["current_task"] = task_name
    
@app.get("/api/news/video_progress")
def video_progress_endpoint():
    return VIDEO_PROGRESS

def run_video_generation_task():
    global VIDEO_PROGRESS
    VIDEO_PROGRESS = {
        "status": "generating", 
        "percent": 0, 
        "current_task": "Haberler taranıyor...",
        "result": None,
        "error": None
    }
    
    try:
        from video_generator import process_daily_news_video
        
        # Define callback to update global state
        def progress_callback(msg):
            VIDEO_PROGRESS["current_task"] = msg
            print(f"Progress Update: {msg}")
            
        success, result = process_daily_news_video(progress_callback)
        
        if success:
             # Result is absolute path: .../generated_videos/YYYY-MM-DD/filename.mp4
             # We need relative path from generated_videos root
             video_rel_path = os.path.relpath(result, str(VIDEOS_DIR))
             video_url = f"http://127.0.0.1:8000/videos/{video_rel_path}".replace("\\", "/")
             
             VIDEO_PROGRESS["status"] = "done"
             VIDEO_PROGRESS["result"] = video_url
             VIDEO_PROGRESS["current_task"] = "Tamamlandı!"
        else:
             VIDEO_PROGRESS["status"] = "error"
             VIDEO_PROGRESS["error"] = result
             VIDEO_PROGRESS["current_task"] = f"Hata: {result}"
             
    except Exception as e:
        print(f"Background Video Gen Error: {e}")
        VIDEO_PROGRESS["status"] = "error"
        VIDEO_PROGRESS["error"] = str(e)
        VIDEO_PROGRESS["current_task"] = "Kritik Hata"

@app.post("/api/news/video_generate")
async def news_video_generate_endpoint(background_tasks: BackgroundTasks):
    # Check if already running
    if VIDEO_PROGRESS["status"] == "generating":
        return {"success": False, "error": "Already generating a video!"}
        
    background_tasks.add_task(run_video_generation_task)
    return {"success": True, "message": "Video generation started in background"}

# --- AGENT LOGIC ---

AGENT_PROGRESS = {
    "status": "idle",
    "percent": 0,
    "stage": "idle",
    "current_task": "",
    "result": None,
    "error": None,
    "cancel_requested": False
}

def run_agent_task(live_mode: bool = False):
    global AGENT_PROGRESS
    AGENT_PROGRESS = {
        "status": "running",
        "percent": 0,
        "stage": "starting",
        "current_task": "Agent Başlatılıyor...",
        "result": None,
        "error": None,
        "cancel_requested": False
    }
    
    try:
        from core.orchestrator import Orchestrator
        from core.system_check import ensure_sd_running, ensure_ollama_running

        def set_stage(stage: str, percent: int, task: str):
            AGENT_PROGRESS["stage"] = stage
            AGENT_PROGRESS["percent"] = percent
            AGENT_PROGRESS["current_task"] = task

        def is_cancelled() -> bool:
            return bool(AGENT_PROGRESS.get("cancel_requested"))

        def cancel_guard(where: str) -> bool:
            if is_cancelled():
                AGENT_PROGRESS["status"] = "cancelled"
                AGENT_PROGRESS["stage"] = "cancelled"
                AGENT_PROGRESS["current_task"] = f"İptal edildi ({where})."
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
        
        # Capture Logs
        import datetime
        def log_capture(msg):
            # Update global state logs
            if "logs" not in AGENT_PROGRESS:
                AGENT_PROGRESS["logs"] = []
            
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            AGENT_PROGRESS["logs"].append(f"[{timestamp}] {msg}")
            
            # Always show last line as current task (UI friendly)
            AGENT_PROGRESS["current_task"] = msg

            # Map orchestrator step logs to stage/percent for a clear progress bar
            if "[Orchestrator]" in msg:
                if "Step 1/6" in msg:
                    AGENT_PROGRESS["stage"] = "news"
                    AGENT_PROGRESS["percent"] = 20
                elif "Step 2/6" in msg:
                    AGENT_PROGRESS["stage"] = "risk"
                    AGENT_PROGRESS["percent"] = 35
                elif "Step 3/6" in msg:
                    AGENT_PROGRESS["stage"] = "visual"
                    AGENT_PROGRESS["percent"] = 55
                elif "Step 4/6" in msg:
                    AGENT_PROGRESS["stage"] = "caption"
                    AGENT_PROGRESS["percent"] = 70
                elif "Step 5/6" in msg:
                    AGENT_PROGRESS["stage"] = "schedule"
                    AGENT_PROGRESS["percent"] = 85
                elif "Step 6/6" in msg:
                    AGENT_PROGRESS["stage"] = "publish"
                    AGENT_PROGRESS["percent"] = 95
            
        orchestrator.set_logger(log_capture)
        
        set_stage("running", 15, "Pipeline çalışıyor...")
        if cancel_guard("pipeline_baslangic"):
            return
        
        # Synchrounous run
        final_state = orchestrator.run_pipeline()
        
        # If cancel was requested at any time, surface it as a cancelled status
        if is_cancelled() or (final_state.upload_status and final_state.upload_status.get("message") == "Cancelled"):
             AGENT_PROGRESS["status"] = "cancelled"
             AGENT_PROGRESS["stage"] = "cancelled"
             AGENT_PROGRESS["current_task"] = "İptal edildi."
             return

        if final_state.upload_status and final_state.upload_status.get("success"):
             AGENT_PROGRESS["status"] = "done"
             AGENT_PROGRESS["stage"] = "done"
             AGENT_PROGRESS["percent"] = 100
             AGENT_PROGRESS["current_task"] = "İşlem başarıyla tamamlandı."
             AGENT_PROGRESS["result"] = final_state.upload_status
        elif dry_run:
             AGENT_PROGRESS["status"] = "done"
             AGENT_PROGRESS["stage"] = "done"
             AGENT_PROGRESS["percent"] = 100
             AGENT_PROGRESS["current_task"] = "Test Tamamlandı (Dry Run)"
             # Return generated images if available
             if final_state.generated_images:
                 AGENT_PROGRESS["result"] = {"images": final_state.generated_images}
        else:
             AGENT_PROGRESS["status"] = "error"
             AGENT_PROGRESS["stage"] = "error"
             # If upload status exists, bubble the real reason to UI
             if final_state.upload_status and final_state.upload_status.get("message"):
                 AGENT_PROGRESS["error"] = final_state.upload_status.get("message")
                 AGENT_PROGRESS["current_task"] = f"Hata: {final_state.upload_status.get('message')}"
             else:
                 AGENT_PROGRESS["error"] = "Pipeline bir noktada durdu veya upload başarısız."
                 AGENT_PROGRESS["current_task"] = "İşlem tamamlanamadı."

    except Exception as e:
        print(f"Agent Error: {e}")
        AGENT_PROGRESS["status"] = "error"
        AGENT_PROGRESS["stage"] = "error"
        AGENT_PROGRESS["error"] = str(e)
        AGENT_PROGRESS["current_task"] = "Kritik Hata"

@app.post("/api/agent/cancel")
async def cancel_agent_endpoint():
    """
    Cooperative cancel:
    - Sets a flag checked by the background job between steps.
    - If currently in a blocking SD generation call, it will cancel after that step completes.
    """
    if AGENT_PROGRESS.get("status") != "running":
        return {"success": False, "error": "Ajan çalışmıyor."}
    AGENT_PROGRESS["cancel_requested"] = True
    AGENT_PROGRESS["current_task"] = "İptal isteği alındı. Güvenli durdurma bekleniyor..."
    return {"success": True, "message": "Cancel requested"}

@app.post("/api/agent/run")
async def run_agent_endpoint(background_tasks: BackgroundTasks, live: bool = False):
    if AGENT_PROGRESS["status"] == "running":
        return {"success": False, "error": "Ajan zaten çalışıyor!"}
    
    background_tasks.add_task(run_agent_task, live_mode=live)
    return {"success": True, "message": "Autonomous Agent started"}

@app.get("/api/agent/progress")
def agent_progress_endpoint():
    return AGENT_PROGRESS

# --- CAROUSEL LOGIC ---

def run_carousel_generation_task():
    global CAROUSEL_PROGRESS
    CAROUSEL_PROGRESS = {
        "status": "generating",
        "percent": 0,
        "current_task": "Gündem taranıyor...",
        "result": None,
        "error": None
    }
    
    try:
        from core.carousel_agent import generate_carousel_content
        
        def progress_callback(msg):
            # Eğer "LAYER_UPDATE:" ile başlıyorsa özel işlem yapabiliriz
            if msg.startswith("LAYER_UPDATE:"):
                clean_msg = msg.replace("LAYER_UPDATE:", "")
                CAROUSEL_PROGRESS["current_task"] = clean_msg
                # İlerlemeyi resim sayısına göre artırabiliriz ama şimdilik metin yeterli
            else:
                CAROUSEL_PROGRESS["current_task"] = msg
            print(f"Carousel Progress: {msg}")

        success, images, caption = generate_carousel_content(progress_callback)
        
        if success:
            # Görselleri URL'e çevir
            image_urls = []
            for img in images:
                abs_path = img["path"]
                rel_path = os.path.relpath(abs_path, str(IMAGES_DIR))
                url = f"http://127.0.0.1:8000/images/{rel_path}?v={uuid.uuid4()}".replace("\\", "/")
                image_urls.append({
                    "url": url,
                    "prompt": img["prompt"],
                    "path": abs_path # Upload için lazım
                })
            
            CAROUSEL_PROGRESS["status"] = "done"
            CAROUSEL_PROGRESS["result"] = {
                "images": image_urls,
                "caption": caption
            }
            CAROUSEL_PROGRESS["current_task"] = "Tamamlandı!"
        else:
            CAROUSEL_PROGRESS["status"] = "error"
            CAROUSEL_PROGRESS["error"] = caption # Hata mesajı caption içinde dönüyor agent'ta
            CAROUSEL_PROGRESS["current_task"] = "Hata oluştu."

    except Exception as e:
        print(f"Carousel Gen Error: {e}")
        CAROUSEL_PROGRESS["status"] = "error"
        CAROUSEL_PROGRESS["error"] = str(e)

@app.post("/api/carousel/generate")
async def carousel_generate_endpoint(background_tasks: BackgroundTasks):
    if CAROUSEL_PROGRESS["status"] == "generating":
        return {"success": False, "error": "Zaten işlem devam ediyor!"}
    
    background_tasks.add_task(run_carousel_generation_task)
    return {"success": True, "message": "Carousel generation started"}

@app.get("/api/carousel/progress")
def carousel_progress_endpoint():
    return CAROUSEL_PROGRESS

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
        from core.insta_client import set_instagram_credentials
        set_instagram_credentials(req.username, req.password)
        return {"success": True, "message": "Credentials saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instagram/session/reset")
async def instagram_session_reset_endpoint():
    """Deletes insta_session.json to force a fresh login next upload."""
    try:
        from core.insta_client import reset_instagram_session
        ok = reset_instagram_session()
        return {"success": bool(ok)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instagram/graph-config")
async def instagram_graph_config_endpoint(req: InstaGraphConfigRequest):
    """Saves Graph API fields into .env for first-time setup from UI."""
    try:
        values = _upsert_env_values({
            "FB_APP_ID": req.fb_app_id,
            "FB_APP_SECRET": req.fb_app_secret,
            "FB_PAGE_ID": req.fb_page_id,
            "IG_USER_ID": req.ig_user_id,
            "FB_ACCESS_TOKEN": req.fb_access_token,
            "PUBLIC_BASE_URL": req.public_base_url,
            "IG_GRAPH_VERSION": req.ig_graph_version or "v24.0",
        })
        ready = all(values.get(k, "").strip() for k in [
            "FB_APP_ID",
            "FB_APP_SECRET",
            "FB_PAGE_ID",
            "IG_USER_ID",
            "FB_ACCESS_TOKEN",
            "PUBLIC_BASE_URL",
        ])
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
        _upsert_env_values({
            "IMGBB_API_KEY": req.imgbb_api_key
        })
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/imgbb/config")
async def imgbb_config_get_endpoint():
    """Returns current ImgBB config"""
    try:
        values = _read_env_values()
        return {
            "success": True,
            "imgbb_api_key": values.get("IMGBB_API_KEY", "")
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
        
        # Convert all paths to absolute to avoid issues with Turkish characters in parent dirs
        abs_model_path = os.path.abspath(PIPER_MODEL)
        abs_config_path = os.path.abspath(PIPER_CONFIG)
        abs_output_path = os.path.abspath(str(output_path))
        abs_text_path = os.path.abspath(str(text_path))
        
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
            "-m", safe_model_path,
            "-c", safe_config_path,
            "-f", safe_output_path,
            "--length-scale", "0.95"
        ]
        
        # print(f"   Komut: {cmd}")
        # print(f"   CWD: {cwd_dir}")
        # print(f"   Text File: {text_path}")

        try:
            # Use input string directly if file reading is problematic, 
            # but usually file input works best for encoding.
            # We'll use the temp text file we already created.
            with open(text_path, "r", encoding="utf-8") as f:
                process = subprocess.run(
                    cmd,
                    stdin=f,
                    capture_output=True,
                    text=True,
                    cwd=cwd_dir
                )
            
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
        return FileResponse(
            path=output_path, 
            media_type="audio/wav", 
            filename="response.wav"
        )
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
        
        filename = f"stt_in_{uuid.uuid4()}" # Extension unknown potentially
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
        except:
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

import sys
import os
import shutil
import uuid
import subprocess
import speech_recognition as sr
from pathlib import Path

# Add root directory to path to allow importing core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
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
    
    # Import model config from core/tts to match user's settings
    from core.tts import PIPER_MODEL, PIPER_CONFIG
except ImportError as e:
    print(f"Warning: Could not import core modules: {e}")
    # Define fallback if import fails (so execution doesn't crash)
    PIPER_MODEL = "models/tr_TR-fahrettin-medium.onnx"
    PIPER_CONFIG = "models/tr_TR-fahrettin-medium.onnx.json"
except ImportError as e:
    print(f"Warning: Could not import core modules: {e}")
    # We continue, but some endpoints might fail
    # Define dummy placeholders if needed or let individual endpoints fail gracefully


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
    
@app.get("/")
def read_root():
    return {"status": "online", "message": "Ses Asistanı Backend Running"}

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

def remove_file(path: str):
    try:
        os.remove(path)
    except Exception:
        pass
        
@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest, background_tasks: BackgroundTasks):
    """
    Generates TTS audio and returns the file.
    Does NOT play on server.
    """
    try:
        print(f"{YELLOW}🎤 TTS İstendi: {req.text}{RESET}")
        print(f"   Model Yolu: {PIPER_MODEL}")
        
        if not os.path.exists(PIPER_MODEL):
             print(f"{RED}❌ HATA: Model dosyası bulunamadı! {PIPER_MODEL}{RESET}")
             raise HTTPException(status_code=500, detail="Model file not found backend")

        filename = f"tts_{uuid.uuid4()}.wav"
        output_path = TEMP_DIR / filename
        
        # Run Piper
        cmd = [
            "piper",
            "-m", PIPER_MODEL,
            "-c", PIPER_CONFIG,
            "-f", str(output_path),
            "--length-scale", "0.95"
        ]
        
        print(f"   Komut: {cmd}")

        process = subprocess.run(
            cmd,
            input=req.text,
            text=True,
            capture_output=True
            # encoding arg removed, falling back to system default (safer for now)
        )
        
        if process.returncode != 0:
            print(f"{RED}Piper Error: {process.stderr}{RESET}")
            raise Exception(f"TTS Generation failed: {process.stderr}")
            
        # Add background task to remove file after response is sent
        background_tasks.add_task(remove_file, str(output_path))
            
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

    # 2. Start/Check Stable Diffusion
    print(f"{YELLOW}🎨 Checking Stable Diffusion...{RESET}")
    try:
        ensure_sd_running()
    except Exception as e:
        print(f"{RED}⚠️ SD Start Error: {e}{RESET}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

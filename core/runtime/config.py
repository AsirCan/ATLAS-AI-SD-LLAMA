import os
import time
from dotenv import load_dotenv

# RENKLER
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

# ==================================================
# STABLE DIFFUSION (RESİM ÜRETİM) AYARLARI
# Instagram için KARE format
# ==================================================

load_dotenv()

SD_WIDTH = 1024
SD_HEIGHT = 1024

SD_STEPS = 30          # kalite / süre dengesi - orta yol 
SD_CFG_SCALE = 7      # prompta bağlılık
SD_SAMPLER = "DPM++ 2M Karras"
SD_RESTORE_FACES = os.getenv("SD_RESTORE_FACES", "1").strip() == "1"
SD_MAX_PROMPT_CHARS = int(os.getenv("SD_MAX_PROMPT_CHARS", "700"))
SD_FACE_RESTORATION_MODEL = os.getenv("SD_FACE_RESTORATION_MODEL", "GFPGAN")

# Optional hires-fix controls (off by default for speed/VRAM safety)
SD_ENABLE_HIRES_FIX = os.getenv("SD_ENABLE_HIRES_FIX", "0").strip() == "1"
SD_HIRES_SCALE = float(os.getenv("SD_HIRES_SCALE", "1.3"))
SD_HIRES_DENOISE = float(os.getenv("SD_HIRES_DENOISE", "0.32"))
SD_HIRES_UPSCALER = os.getenv("SD_HIRES_UPSCALER", "Latent (antialiased)")
SD_AUTO_BEST_HR_UPSCALER = os.getenv("SD_AUTO_BEST_HR_UPSCALER", "1").strip() == "1"
SD_PREFERRED_HR_UPSCALERS = os.getenv(
    "SD_PREFERRED_HR_UPSCALERS",
    "4x-UltraSharp,RealESRGAN 4x+,R-ESRGAN 4x+,Latent (antialiased)",
)

# Optional post-upscale pass (uses Forge extras API + ESRGAN models)
SD_ENABLE_POST_UPSCALE = os.getenv("SD_ENABLE_POST_UPSCALE", "1").strip() == "1"
SD_POST_UPSCALE_FACTOR = float(os.getenv("SD_POST_UPSCALE_FACTOR", "1.15"))
SD_POST_UPSCALER = os.getenv("SD_POST_UPSCALER", "4x-UltraSharp")

# Optional ADetailer pass
SD_ENABLE_ADDETAILER = os.getenv("SD_ENABLE_ADDETAILER", "1").strip() == "1"
SD_ADDETAILER_HUMAN_ONLY = os.getenv("SD_ADDETAILER_HUMAN_ONLY", "1").strip() == "1"
SD_ADDETAILER_ENABLE_HANDS = os.getenv("SD_ADDETAILER_ENABLE_HANDS", "1").strip() == "1"
SD_ADDETAILER_CONFIDENCE = float(os.getenv("SD_ADDETAILER_CONFIDENCE", "0.30"))
SD_ADDETAILER_SKIP_ON_CROWD = os.getenv("SD_ADDETAILER_SKIP_ON_CROWD", "1").strip() == "1"

# Optional ControlNet pass (requires a control image path)
SD_ENABLE_CONTROLNET = os.getenv("SD_ENABLE_CONTROLNET", "0").strip() == "1"
SD_CONTROLNET_WEIGHT = float(os.getenv("SD_CONTROLNET_WEIGHT", "0.65"))
SD_CONTROLNET_GUIDANCE_START = float(os.getenv("SD_CONTROLNET_GUIDANCE_START", "0.0"))
SD_CONTROLNET_GUIDANCE_END = float(os.getenv("SD_CONTROLNET_GUIDANCE_END", "0.85"))

INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_SESSIONID = os.getenv("INSTA_SESSIONID")

# ==================================================
# CONTENT QUALITY & SAFETY
# ==================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_news_memory_db_raw = os.getenv("NEWS_MEMORY_DB_PATH", os.path.join("data", "news_memory.db"))
NEWS_MEMORY_DB = _news_memory_db_raw if os.path.isabs(_news_memory_db_raw) else os.path.join(BASE_DIR, _news_memory_db_raw)

# sqlite | json | mongodb
NEWS_MEMORY_BACKEND = os.getenv("NEWS_MEMORY_BACKEND", "sqlite").strip().lower()

_news_memory_json_raw = os.getenv("NEWS_MEMORY_JSON_PATH", os.path.join("data", "news_memory.json"))
NEWS_MEMORY_JSON = _news_memory_json_raw if os.path.isabs(_news_memory_json_raw) else os.path.join(BASE_DIR, _news_memory_json_raw)

NEWS_MEMORY_MONGO_URI = os.getenv("NEWS_MEMORY_MONGO_URI", "mongodb://localhost:27017")
NEWS_MEMORY_MONGO_DB = os.getenv("NEWS_MEMORY_MONGO_DB", "atlas_ai")
NEWS_MEMORY_MONGO_COLLECTION = os.getenv("NEWS_MEMORY_MONGO_COLLECTION", "used_news")

USED_NEWS_TTL_DAYS = int(os.getenv("USED_NEWS_TTL_DAYS", "7"))

# Risk filter controls
RISK_DEFAULT_THRESHOLD = int(os.getenv("RISK_DEFAULT_THRESHOLD", "4"))
RISK_WHITELIST_MAX_SCORE = int(os.getenv("RISK_WHITELIST_MAX_SCORE", "6"))

RISK_WHITELIST_KEYWORDS = [
    "science",
    "space",
    "nasa",
    "ai",
    "robot",
    "technology",
    "startup",
    "innovation",
    "research",
    "medicine",
    "health",
    "education",
]

RISK_BLACKLIST_KEYWORDS = [
    "war",
    "terror",
    "attack",
    "bomb",
    "shooting",
    "murder",
    "rape",
    "sexual",
    "drugs",
    "abuse",
    "suicide",
]

RISK_CATEGORY_THRESHOLDS = {
    "violence": 2,
    "hate_speech": 2,
    "adult": 2,
    "sexual": 2,
    "politics": 3,
    "political_bias": 3,
    "misinformation": 3,
    "drugs": 3,
}

# Carousel consistency
CAROUSEL_BASE_STYLE = (
    "consistent camera angle, 35mm lens, soft cinematic lighting, "
    "subtle film grain, balanced color grading, no text"
)

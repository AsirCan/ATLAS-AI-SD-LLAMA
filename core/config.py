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

INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_SESSIONID = os.getenv("INSTA_SESSIONID")

# ==================================================
# CONTENT QUALITY & SAFETY
# ==================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_MEMORY_DB = os.path.join(BASE_DIR, "data", "news_memory.db")
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

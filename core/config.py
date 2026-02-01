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
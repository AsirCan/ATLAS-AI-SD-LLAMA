#Buraya SADECE sabitler, listeler ve basit yardımcılar eklencek
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

# KELİMELER
ACMA_FIILLERI = ["aç", "başlat", "çalıştır", "open", "oyna", "gir", "göster"]

UYANMA_KELIMELERI = [
    "hey atlas", "atlas uyan", "uyan atlas", "merhaba atlas", "selam atlas"
]

KAPATMA_KELIMELERI = [
    "kapat", "programı kapat", "kendini kapat", "görüşürüz", "bay bay", "baybay",
    "çık", "çıkış yap", "artık gerek yok"
]

RESET_KELIMELERI = [
    "hafızayı sil", "hafızayı temizle", "unut", "reset at", "baştan başla"
]

# UYGULAMALAR
UYGULAMA_LISTESI = {
    "chrome": "start chrome",
    "google": "start chrome",
    "steam": "start steam://open/main",
    "spotify": "start spotify:",
    "not defteri": "notepad",
    "notepad": "notepad",
    "hesap makinesi": "calc",
    "calculator": "calc",
    "youtube": "url:https://youtube.com",
    "instagram": "url:https://instagram.com",
    "twitter": "url:https://twitter.com",
    "x ": "url:https://x.com",
    "whatsapp": "url:https://web.whatsapp.com"
}

# ARAYÜZ
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def loading(text="Yükleniyor", saniye=1.3):
    for i in range(3):
        print(f"{BLUE}{text}{'.' * (i+1)}{RESET}", end="\r")
        time.sleep(saniye / 3)
    print(" " * 40, end="\r")


# ==================================================
# STABLE DIFFUSION (RESİM ÜRETİM) AYARLARI
# Instagram için KARE format
# ==================================================


load_dotenv()

SD_WIDTH = 1024
SD_HEIGHT = 1024

SD_STEPS = 9          # kalite / süre dengesi - orta yol 
SD_CFG_SCALE = 6      # prompta bağlılık
SD_SAMPLER = "DPM++ 2M Karras"

INSTA_USERNAME = os.getenv("INSTA_USERNAME")
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD")
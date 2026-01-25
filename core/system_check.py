import socket
import subprocess
import time
from core.config import RED, RESET, GREEN, YELLOW

# ==================================================
# Internet / SD (Forge) kontrol yardımcıları
# ==================================================

def check_online_status() -> bool:
    """İnternet var mı yok mu hızlı kontrol."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        return True
    except OSError:
        return False


def is_sd_running(host="127.0.0.1", port=7860) -> bool:
    """Forge API portu açık mı? (SD çalışıyor mu?)"""
    try:
        with socket.create_connection((host, port), timeout=1) as s:
            return True
    except OSError:
        return False


def start_stable_diffusion():
    """Forge'u minimized olarak API modunda başlatır."""
    print("🎨 Stable Diffusion (Forge) başlatılıyor...")
    subprocess.Popen(
        [
            "cmd", "/c",
            "start", "/min",
            "cmd", "/c",
            # --medvram: 6GB kartlar için idealdir.
            # --always-offload-from-vram: Çizim bitince modeli VRAM'den atar, Llama'ya yer açar.
            "cd /d C:\\Forge && webui-user.bat --api --medvram --always-offload-from-vram"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def ensure_sd_running(wait_seconds=20, log_callback=print):
    """
    SD çalışmıyorsa açar. Açtıktan sonra port gelene kadar bekler.
    """
    if is_sd_running():
        log_callback("🎨 Stable Diffusion zaten çalışıyor.")
        return True

    start_stable_diffusion()

    # SD'nin ayağa kalkmasını bekle
    # SD'nin ayağa kalkmasını bekle (Sınırsız döngü)
    log_callback(f"⏳ Stable Diffusion açılıyor... (Hazır olana kadar bekleniyor)")
    
    start_time = time.time()
    last_print_time = start_time
    
    while True:
        if is_sd_running():
            log_callback(f"{GREEN}✅ Stable Diffusion başarıyla bağlandı ve hazır!{RESET}")
            return True
            
        # Kullanıcı dondu sanmasın diye 10 saniyede bir bilgi ver
        current_time = time.time()
        if current_time - last_print_time > 10:
            elapsed = int(current_time - start_time)
            log_callback(f"⏳ Stable Diffusion bekleniyor... ({elapsed} saniye geçti)")
            last_print_time = current_time
            
        time.sleep(2)

    # Bu satıra asla gelmez çünkü while True var
    return True

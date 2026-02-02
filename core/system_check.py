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

def is_ollama_running(host="127.0.0.1", port=11434) -> bool:
    """Ollama API portu açık mı?"""
    try:
        with socket.create_connection((host, port), timeout=1) as s:
            return True
    except OSError:
        return False

def start_ollama():
    """Ollama'yı başlatır."""
    print("🦙 Ollama başlatılıyor...")
    subprocess.Popen(
        ["ollama", "serve"],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

def ensure_ollama_running(log_callback=print, cancel_checker=None):
    if is_ollama_running():
        log_callback("🦙 Ollama zaten çalışıyor.")
        return True
    
    start_ollama()
    log_callback("⏳ Ollama açılıyor...")
    while not is_ollama_running():
        # Optional cooperative cancel (used by UI cancel)
        try:
            if callable(cancel_checker) and cancel_checker():
                log_callback("🛑 İptal istendi (Ollama bekleme durduruldu).")
                return False
        except Exception:
            pass
        time.sleep(2)
    log_callback(f"{GREEN}✅ Ollama hazır!{RESET}")
    return True


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

def ensure_sd_running(wait_seconds=20, log_callback=print, cancel_checker=None, max_wait_seconds=180):
    """
    SD çalışmıyorsa açar. Açtıktan sonra port gelene kadar bekler.
    """
    if is_sd_running():
        log_callback("🎨 Stable Diffusion zaten çalışıyor.")
        return True

    start_stable_diffusion()

    # SD'nin ayağa kalkmasını bekle (sonsuz bekleme yok)
    log_callback(f"⏳ Stable Diffusion açılıyor... (en fazla {max_wait_seconds}s beklenecek)")
    
    start_time = time.time()
    last_print_time = start_time
    
    while True:
        # Optional cooperative cancel (used by UI cancel)
        try:
            if callable(cancel_checker) and cancel_checker():
                log_callback("🛑 İptal istendi (SD bekleme durduruldu).")
                return False
        except Exception:
            pass

        if is_sd_running():
            log_callback(f"{GREEN}✅ Stable Diffusion başarıyla bağlandı ve hazır!{RESET}")
            return True
            
        # Kullanıcı dondu sanmasın diye 10 saniyede bir bilgi ver
        current_time = time.time()
        if current_time - last_print_time > 10:
            elapsed = int(current_time - start_time)
            log_callback(f"⏳ Stable Diffusion bekleniyor... ({elapsed} saniye geçti)")
            last_print_time = current_time

        # Timeout guard: uzun süre takılınca backend'i kilitleme
        if current_time - start_time >= max_wait_seconds:
            log_callback(
                f"{YELLOW}⚠️ Stable Diffusion {max_wait_seconds}s içinde hazır olmadı. "
                f"Backend devam ediyor; SD işlemlerinde hata alırsan Forge'u manuel aç.{RESET}"
            )
            return False
            
        time.sleep(2)

    return False

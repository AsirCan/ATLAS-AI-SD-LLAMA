import os
import subprocess
import sys
import shutil
import ctypes
import io
import zipfile
from shutil import which

# ================= AYARLAR =================
FORGE_PATH = r"C:\Forge"
FORGE_REPO = "https://github.com/lllyasviel/stable-diffusion-webui-forge.git"

# Forge model dizini: bazı kurulumlarda `C:\Forge\models\Stable-diffusion` (klasik),
# bazı eski/özel kurulumlarda `C:\Forge\webui\models\Stable-diffusion` olabilir.
def _resolve_sd_model_dir():
    candidates = [
        os.path.join(FORGE_PATH, "models", "Stable-diffusion"),
        os.path.join(FORGE_PATH, "webui", "models", "Stable-diffusion"),
    ]
    for p in candidates:
        try:
            # varsa tercih et
            if os.path.isdir(p):
                return p
        except Exception:
            pass
    # hiçbiri yoksa klasik yolu oluşturacağız
    return candidates[0]

SD_MODEL_DIR = _resolve_sd_model_dir()
SD_MODEL_REPO = "RunDiffusion/Juggernaut-XL-v9"
SD_MODEL_FILENAME = "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"

# Piper (TTS) - Windows standalone binary (fix for espeakbridge missing)
PIPER_WINDOWS_ZIP_URL = "https://sourceforge.net/projects/piper-tts.mirror/files/2023.11.14-2/piper_windows_amd64.zip/download"
PIPER_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "piper")
PIPER_EXE_PATH = os.path.join(PIPER_TOOLS_DIR, "piper.exe")
PIPER_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
PIPER_TR_MODEL_NAME = "tr_TR-fahrettin-medium.onnx"
PIPER_TR_CONFIG_NAME = "tr_TR-fahrettin-medium.onnx.json"
def _hf_list_files(repo):
    """Return a list of filenames in a Hugging Face repo via the API."""
    import requests  # noqa: E402

    api_url = f"https://huggingface.co/api/models/{repo}"
    r = requests.get(api_url, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    siblings = data.get("siblings", [])
    return [s.get("rfilename") for s in siblings if s.get("rfilename")]

def _build_piper_url_candidates():
    """Build a list of possible Hugging Face URLs for the Fahrettin model."""
    repos = [
        "speaches-ai/piper-tr_TR-fahrettin-medium",
        "speeches-ai/piper-tr_TR-fahrettin-medium",
    ]

    model_urls = []
    config_urls = []

    # Try to discover files dynamically via HF API
    for repo in repos:
        files = _hf_list_files(repo)
        if not files:
            continue
        onnx_files = [f for f in files if f.lower().endswith(".onnx")]
        json_files = [f for f in files if f.lower().endswith(".json")]
        if not onnx_files or not json_files:
            continue

        # Prefer config.json if present, otherwise any .onnx.json
        config_file = None
        for f in json_files:
            if f.lower().endswith("config.json"):
                config_file = f
                break
        if not config_file:
            for f in json_files:
                if f.lower().endswith(".onnx.json"):
                    config_file = f
                    break
        if not config_file:
            continue

        model_file = onnx_files[0]
        base = f"https://huggingface.co/{repo}/resolve/main/"
        model_urls.append(base + model_file)
        model_urls.append(base + model_file + "?download=true")
        config_urls.append(base + config_file)
        config_urls.append(base + config_file + "?download=true")

    # Legacy rhasspy path (removed Dec 30, 2025, keep as fallback)
    rhasspy_base = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    model_urls.append(
        rhasspy_base + "tr/tr_TR/fahrettin/medium/tr_TR-fahrettin-medium.onnx"
    )
    model_urls.append(
        rhasspy_base + "tr/tr_TR/fahrettin/medium/tr_TR-fahrettin-medium.onnx?download=true"
    )
    config_urls.append(
        rhasspy_base + "tr/tr_TR/fahrettin/medium/tr_TR-fahrettin-medium.onnx.json"
    )
    config_urls.append(
        rhasspy_base + "tr/tr_TR/fahrettin/medium/tr_TR-fahrettin-medium.onnx.json?download=true"
    )

    return model_urls, config_urls

# RENKLER
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def check_venv():
    """Sanal ortamda mıyız kontrol eder."""
    return sys.prefix != sys.base_prefix

def _run(cmd, check=True):
    """Subprocess wrapper with nicer output."""
    print(f"{YELLOW}   > {cmd}{RESET}")
    return subprocess.run(cmd, check=check)

def _run_capture(cmd):
    """Subprocess wrapper capturing output (for probing)."""
    return subprocess.run(cmd, text=True, capture_output=True)

def _ensure_env_var_line(key: str, value: str):
    """Append KEY=VALUE into .env if missing. Does not overwrite existing values."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception:
            with open(env_path, "rb") as f:
                lines = f.read().decode("utf-8", errors="ignore").splitlines()
    else:
        # If .env doesn't exist, create from .env.example if present
        example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")
        if os.path.exists(example_path):
            try:
                with open(example_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except Exception:
                lines = []

    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            return

    lines.append(f"{key}={value}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def _probe_piper_espeakbridge() -> bool:
    """Returns True if current python 'piper' module has espeakbridge."""
    try:
        probe = _run_capture([sys.executable, "-c", "from piper import espeakbridge; print('ok')"])
        return probe.returncode == 0
    except Exception:
        return False

def install_piper_windows_binary_if_needed():
    """
    Windows'ta bazı pip kurulumlarında piper'in espeak fonemleme modülü (espeakbridge) gelmiyor.
    Bu durumda standalone piper.exe indirip tools/piper altına koyuyoruz ve .env'ye PIPER_BIN yazıyoruz.
    """
    if os.name != "nt":
        return

    print(f"\n{YELLOW}🔊 Piper (TTS) kontrol ediliyor...{RESET}")

    # If already present, ensure env points to it and exit.
    if os.path.exists(PIPER_EXE_PATH):
        print(f"{GREEN}✅ Piper bulundu: {PIPER_EXE_PATH}{RESET}")
        _ensure_env_var_line("PIPER_BIN", "tools/piper/piper.exe")
        return

    # If python module already has espeakbridge, we can use pip piper.
    if _probe_piper_espeakbridge():
        print(f"{GREEN}✅ Piper python modülü espeakbridge içeriyor. Standalone piper.exe gerekmiyor.{RESET}")
        return

    print(f"{YELLOW}⚠️ Piper python kurulumunda 'espeakbridge' yok. Windows'ta TTS için standalone piper.exe indirilecek...{RESET}")

    try:
        _run([sys.executable, "-m", "pip", "install", "requests"], check=True)
        import requests  # noqa: E402

        os.makedirs(PIPER_TOOLS_DIR, exist_ok=True)
        print(f"{YELLOW}⏳ Piper indiriliyor...{RESET}")

        r = requests.get(PIPER_WINDOWS_ZIP_URL, allow_redirects=True, timeout=120)
        r.raise_for_status()

        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        # Extract ALL files from ZIP (piper.exe + DLLs and other dependencies)
        print(f"{YELLOW}⏳ ZIP dosyası çıkartılıyor (piper.exe + DLL'ler)...{RESET}")
        z.extractall(PIPER_TOOLS_DIR)
        
        # Find the piper.exe location within extracted files
        exe_found = None
        for root, dirs, files in os.walk(PIPER_TOOLS_DIR):
            for file in files:
                if file.lower() == "piper.exe":
                    exe_found = os.path.join(root, file)
                    break
            if exe_found:
                break
        
        if not exe_found:
            raise RuntimeError("İndirilen zip içinde piper.exe bulunamadı.")
        
        # If piper.exe is in a subdirectory, move all files to PIPER_TOOLS_DIR root
        exe_dir = os.path.dirname(exe_found)
        if exe_dir != PIPER_TOOLS_DIR:
            print(f"{YELLOW}⏳ Dosyalar düzenleniyor...{RESET}")
            for item in os.listdir(exe_dir):
                src = os.path.join(exe_dir, item)
                dst = os.path.join(PIPER_TOOLS_DIR, item)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                shutil.move(src, dst)
            
            # Clean up empty subdirectories
            for item in os.listdir(PIPER_TOOLS_DIR):
                item_path = os.path.join(PIPER_TOOLS_DIR, item)
                if os.path.isdir(item_path) and not os.listdir(item_path):
                    os.rmdir(item_path)

        print(f"{GREEN}✅ Piper indirildi: {PIPER_EXE_PATH}{RESET}")
        _ensure_env_var_line("PIPER_BIN", "tools/piper/piper.exe")
    except Exception as e:
        print(f"{RED}❌ Piper otomatik kurulum hatası: {e}{RESET}")
        print(f"{YELLOW}Manuel çözüm: standalone Piper indirip .env içine PIPER_BIN=C:\\...\\piper.exe yazın.{RESET}")

def _download_file(url, dest_path):
    """Download a file with streaming to avoid loading into memory."""
    import requests  # noqa: E402

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

def _try_download(urls, dest_path):
    """Try multiple URLs, return True on success."""
    last_err = None
    for url in urls:
        try:
            _download_file(url, dest_path)
            return True
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return False

def install_piper_tr_model_if_needed():
    """Downloads tr_TR-fahrettin-medium model/config into ./models."""
    print(f"\n{YELLOW}🗣️ Piper Türkçe modeli kontrol ediliyor (fahrettin-medium)...{RESET}")

    os.makedirs(PIPER_MODEL_DIR, exist_ok=True)
    model_path = os.path.join(PIPER_MODEL_DIR, PIPER_TR_MODEL_NAME)
    config_path = os.path.join(PIPER_MODEL_DIR, PIPER_TR_CONFIG_NAME)

    # Allow override via env for custom mirrors
    env_model_url = os.environ.get("PIPER_TR_MODEL_URL")
    env_config_url = os.environ.get("PIPER_TR_CONFIG_URL")
    model_urls, config_urls = _build_piper_url_candidates()
    if env_model_url:
        model_urls.insert(0, env_model_url)
    if env_config_url:
        config_urls.insert(0, env_config_url)

    if os.path.exists(model_path) and os.path.exists(config_path):
        print(f"{GREEN}✅ Piper modeli zaten mevcut: {model_path}{RESET}")
        return

    try:
        if not os.path.exists(model_path):
            print(f"{YELLOW}⏳ Model indiriliyor...{RESET}")
            _try_download(model_urls, model_path)
        if not os.path.exists(config_path):
            print(f"{YELLOW}⏳ Model config indiriliyor...{RESET}")
            _try_download(config_urls, config_path)
        print(f"{GREEN}✅ Piper modeli indirildi: {model_path}{RESET}")
    except Exception as e:
        print(f"{RED}❌ Piper model indirme hatası: {e}{RESET}")
        print(f"{YELLOW}Manuel çözüm: {PIPER_TR_MODEL_NAME} ve {PIPER_TR_CONFIG_NAME} dosyalarını{RESET}")
        print(f"{YELLOW}models\\ klasörüne koyun.{RESET}")
        sys.exit(1)

def install_requirements():
    """Gerekli kütüphaneleri yükler."""
    print(f"{YELLOW}📦 Python kütüphaneleri yükleniyor (requirements.txt)...{RESET}")
    try:
        _run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=True)
        _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        
        # HuggingFace için ekstra kontrol (requirements.txt'de yoksa diye)
        _run([sys.executable, "-m", "pip", "install", "huggingface_hub", "requests"], check=True)
        print(f"{GREEN}✅ Kütüphaneler yüklendi.{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Kütüphane yükleme hatası: {e}{RESET}")
        if os.name == "nt":
            try:
                print(f"{YELLOW}🩹 Windows düzeltmesi deneniyor: pipwin ile PyAudio...{RESET}")
                _run([sys.executable, "-m", "pip", "install", "pipwin"], check=True)
                _run([sys.executable, "-m", "pipwin", "install", "pyaudio"], check=False)
                print(f"{YELLOW}🔁 requirements.txt yeniden deneniyor...{RESET}")
                _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
                print(f"{GREEN}✅ Kütüphaneler yüklendi (fallback ile).{RESET}")
                return
            except Exception as e2:
                print(f"{RED}❌ PyAudio fallback de başarısız: {e2}{RESET}")

        sys.exit(1)

def check_git():
    """Git kurulu mu kontrol eder."""
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except FileNotFoundError:
        return False

def _find_npm_cmd():
    """Return npm executable name if available."""
    return which("npm") or which("npm.cmd") or which("npm.exe")

def _find_node_cmd():
    """Return node executable name if available."""
    return which("node") or which("node.exe")

def install_frontend_deps():
    """Frontend (Vite/React) dependencies."""
    print(f"\n{YELLOW}🌐 Frontend bağımlılıkları kuruluyor (npm install)...{RESET}")

    if not _find_node_cmd() or not _find_npm_cmd():
        print(f"{RED}❌ Node.js / npm bulunamadı!{RESET}")
        print(f"{YELLOW}Lütfen Node.js LTS kurun: https://nodejs.org/{RESET}")
        print(f"{YELLOW}Kurulumdan sonra tekrar install.py çalıştırın.{RESET}")
        sys.exit(1)

    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "frontend")
    if not os.path.isdir(frontend_dir):
        print(f"{RED}❌ Frontend klasörü bulunamadı: {frontend_dir}{RESET}")
        sys.exit(1)

    try:
        subprocess.run([_find_npm_cmd(), "install"], cwd=frontend_dir, check=True)
        print(f"{GREEN}✅ Frontend bağımlılıkları kuruldu.{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Frontend bağımlılık kurulumu hatası: {e}{RESET}")
        sys.exit(1)

def install_forge():
    """Forge'u C:\Forge klasörüne indirir."""
    print(f"\n{YELLOW}🏗️ Stable Diffusion (Forge) Kurulumu Kontrol Ediliyor...{RESET}")
    
    if os.path.exists(FORGE_PATH):
        print(f"{GREEN}✅ Forge klasörü zaten var: {FORGE_PATH}{RESET}")
        return

    print(f"{YELLOW}⏳ Forge GitHub'dan indiriliyor (Bu biraz sürebilir)...{RESET}")
    
    if not check_git():
        print(f"{RED}❌ HATA: Bilgisayarınızda 'Git' kurulu değil!{RESET}")
        print("Lütfen şuradan Git indirin ve kurun: https://git-scm.com/downloads")
        sys.exit(1)

    try:
        # Git clone işlemi
        subprocess.run(["git", "clone", FORGE_REPO, FORGE_PATH], check=True)
        print(f"{GREEN}✅ Forge başarıyla {FORGE_PATH} konumuna kuruldu.{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Forge indirme hatası: {e}{RESET}")
        print("Yönetici olarak çalıştırmayı deneyin veya internetinizi kontrol edin.")
        sys.exit(1)

def install_sd_model():
    """Modeli indirir."""
    # Import here to ensure it's installed
    from huggingface_hub import hf_hub_download
    
    print(f"\n{YELLOW}🎨 Juggernaut XL v9 Modeli İndiriliyor...{RESET}")
    print(f"{YELLOW}   Model klasörü: {SD_MODEL_DIR}{RESET}")
    
    # Klasör oluştur (Eğer yoksa)
    os.makedirs(SD_MODEL_DIR, exist_ok=True)

    target_file = os.path.join(SD_MODEL_DIR, SD_MODEL_FILENAME)
    
    if os.path.exists(target_file):
        print(f"{GREEN}✅ Model zaten mevcut: {target_file}{RESET}")
        return

    # Eğer dosya adı farklıysa ama Juggernaut zaten klasördeyse, tekrar indirmeyelim.
    try:
        existing = []
        for fn in os.listdir(SD_MODEL_DIR):
            low = fn.lower()
            if low.endswith(".safetensors") and "juggernaut" in low:
                existing.append(os.path.join(SD_MODEL_DIR, fn))
        if existing:
            print(f"{GREEN}✅ Juggernaut modeli zaten mevcut (farklı isimle): {existing[0]}{RESET}")
            print(f"{YELLOW}Not: Script '{SD_MODEL_FILENAME}' dosyasını arıyordu; mevcut modeli kullanacağız.{RESET}")
            return
    except Exception:
        pass

    print(f"{YELLOW}⏳ 6-7 GB indirme başlıyor. Lütfen kapatmayın...{RESET}")
    
    try:
        hf_hub_download(
            repo_id=SD_MODEL_REPO,
            filename=SD_MODEL_FILENAME,
            local_dir=SD_MODEL_DIR,
            local_dir_use_symlinks=False
        )
        print(f"{GREEN}✅ Model indirildi.{RESET}")
    except Exception as e:
        print(f"{RED}❌ Model indirme hatası: {e}{RESET}")

def install_ollama_model():
    """Llama modelini çeker."""
    print(f"\n{YELLOW}🧠 Ollama (Llama 3.1) Hazırlanıyor...{RESET}")
    try:
        subprocess.run(["ollama", "pull", "llama3.1:8b"], check=True)
        print(f"{GREEN}✅ Ollama modeli hazır.{RESET}")
    except FileNotFoundError:
        print(f"{RED}⚠️ Ollama bulunamadı! Lütfen https://ollama.com adresinden kurun.{RESET}")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{GREEN}========================================{RESET}")
    print(f"{GREEN}   ATLAS KURULUM SİHİRBAZI (v2.0)   {RESET}")
    print(f"{GREEN}========================================{RESET}")

    if not is_admin():
        print(f"{YELLOW}⚠️ UYARI: Scripti Yönetici olarak çalıştırmadınız.{RESET}")
        print(f"{YELLOW}Eğer C:\\Forge klasörünü oluştururken hata alırsanız, lütfen Yönetici olarak tekrar deneyin.{RESET}\n")

    # 1. Sanal Ortam Kontrolü
    if not check_venv():
        print(f"{RED}❌ UYARI: Sanal ortam (venv) aktif değil!{RESET}")
        print(f"{YELLOW}Lütfen önce sanal ortamı oluşturun ve aktif edin:{RESET}")
        print("   python -m venv .venv")
        print("   .venv\\Scripts\\activate")
        print(f"{YELLOW}Sonra tekrar bu scripti çalıştırın.{RESET}")
        choice = input("Yine de devam etmek istiyor musunuz? (Sistem python'una kurar) [E/H]: ")
        if choice.lower() != 'e':
            sys.exit(0)
    
    # 2. Kütüphaneleri Yükle
    install_requirements()

    # 2.1 Piper (TTS) - Windows binary fix (espeakbridge)
    install_piper_windows_binary_if_needed()

    # 2.2 Piper Turkish model (fahrettin-medium)
    install_piper_tr_model_if_needed()

    # 3. Forge Kur
    install_forge()
    
    # 4. Modeli İndir
    install_sd_model()
    
    # 5. Ollama Hazırla
    install_ollama_model()

    # 6. Frontend bağımlılıkları
    install_frontend_deps()

    print(f"\n{GREEN}🎉 KURULUM TAMAMLANDI!{RESET}")
    print(f"{YELLOW}Başlatma (önerilen):{RESET} python run.py")
    print(f"{YELLOW}Alternatif:{RESET} (sadece backend) python web/backend/main.py")
    input("Çıkış için Enter...")

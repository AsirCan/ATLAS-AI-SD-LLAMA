import os
import subprocess
import sys
import shutil
import ctypes

# ================= AYARLAR =================
FORGE_PATH = r"C:\Forge"
FORGE_REPO = "https://github.com/lllyasviel/stable-diffusion-webui-forge.git"

SD_MODEL_DIR = os.path.join(FORGE_PATH, "webui", "models", "Stable-diffusion")
SD_MODEL_REPO = "RunDiffusion/Juggernaut-XL-v9"
SD_MODEL_FILENAME = "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"

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

def install_requirements():
    """Gerekli kütüphaneleri yükler."""
    print(f"{YELLOW}📦 Python kütüphaneleri yükleniyor (requirements.txt)...{RESET}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        # HuggingFace için ekstra kontrol (requirements.txt'de yoksa diye)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub", "requests"])
        print(f"{GREEN}✅ Kütüphaneler yüklendi.{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Kütüphane yükleme hatası: {e}{RESET}")
        sys.exit(1)

def check_git():
    """Git kurulu mu kontrol eder."""
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except FileNotFoundError:
        return False

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
    
    # Klasör oluştur (Eğer yoksa)
    os.makedirs(SD_MODEL_DIR, exist_ok=True)

    target_file = os.path.join(SD_MODEL_DIR, SD_MODEL_FILENAME)
    
    if os.path.exists(target_file):
        print(f"{GREEN}✅ Model zaten mevcut: {target_file}{RESET}")
        return

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

    # 3. Forge Kur
    install_forge()
    
    # 4. Modeli İndir
    install_sd_model()
    
    # 5. Ollama Hazırla
    install_ollama_model()

    print(f"\n{GREEN}🎉 KURULUM TAMAMLANDI!{RESET}")
    print("Artık 'Baslat_Web.bat' veya 'python web/backend/main.py' ile projeyi başlatabilirsiniz.")
    input("Çıkış için Enter...")

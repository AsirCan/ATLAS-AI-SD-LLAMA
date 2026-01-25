import subprocess
import time
import webbrowser
import os
import sys
import signal

# Renkler
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

APP_URL = "http://localhost:5173"

def check_venv():
    """Sanal ortamda mıyız kontrol eder. Değilse sanal ortam Python'u ile yeniden başlatır."""
    if sys.prefix == sys.base_prefix:
        venv_python = os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
        if os.path.exists(venv_python):
            print(f"{YELLOW}🔄 Sanal ortam (venv) aktif ediliyor...{RESET}")
            # Scripti venv python ile yeniden baslat
            subprocess.run([venv_python] + sys.argv)
            sys.exit()
        else:
            print(f"{RED}❌ Sanal ortam (.venv) bulunamadı! Lütfen önce 'python install.py' çalıştırın.{RESET}")
            sys.exit(1)

def run_app():
    # 1. Sanal Ortam Kontrolü
    check_venv()

    print(f"{GREEN}🚀 Atlas Web Başlatılıyor...{RESET}")
    print(f"{YELLOW}Çıkmak için CTRL+C yapabilirsiniz.{RESET}\n")

    processes = []

    try:
        # 2. Backend Başlat
        print(f"📦 Backend sunucusu açılıyor...")
        backend_process = subprocess.Popen(
            [sys.executable, "web/backend/main.py"],
            cwd=os.getcwd()
        )
        processes.append(backend_process)

        # 3. Frontend Başlat
        print(f"🎨 Frontend arayüzü açılıyor...")
        # npm run dev shell=True gerektirebilir (Windows'ta npm.cmd)
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=os.path.join(os.getcwd(), "web", "frontend"),
            shell=True
        )
        processes.append(frontend_process)

        # 4. Tarayıcıyı Aç
        print(f"🌍 Tarayıcı bekleniyor...")
        time.sleep(5) # Serverların kalkması için süre
        webbrowser.open(APP_URL)
        print(f"\n{GREEN}✅ Sistem Çalışıyor! {APP_URL}{RESET}")
        print("Backend loglarını burada görebilirsiniz...\n")

        # Sürekli bekle
        backend_process.wait()

    except KeyboardInterrupt:
        print(f"\n{YELLOW}🛑 Kapatılıyor...{RESET}")
    finally:
        # Hepsini temizle
        for p in processes:
            p.terminate()
            p.kill() # Garanti olsun
        
        # Windows'ta bazen subprocessler kalabiliyor, taskkill ile temizleyelim
        # Node ve Python süreçlerini temizlemek biraz agresif olabilir ama 
        # sadece bu proje ozelse sorun olmaz. Simdilik sadece processleri kill ediyoruz.
        print("Güle güle! 👋")

if __name__ == "__main__":
    # Windows ANSI renkleri icin
    os.system('color')
    run_app()

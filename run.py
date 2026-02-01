import subprocess
import time
import webbrowser
import os
import sys
import signal
import socket
from shutil import which

# Renkler
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

APP_URL = "http://127.0.0.1:5173"

def wait_for_port(host, port, timeout_sec=60):
    """Wait until a TCP port is accepting connections."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False

def find_npm_cmd():
    """Find npm executable (Windows uses npm.cmd)."""
    return which("npm") or which("npm.cmd") or which("npm.exe")

def is_port_in_use(host, port):
    """Return True if port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

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
        npm_cmd = find_npm_cmd()
        if not npm_cmd:
            print(f"{RED}❌ npm bulunamadı! Node.js LTS kurulu mu?{RESET}")
            print(f"{YELLOW}Çözüm: Node.js kurun ve yeni terminal açıp tekrar deneyin.{RESET}")
            return

        host, port = "127.0.0.1", 5173
        if is_port_in_use(host, port):
            print(f"{YELLOW}⚠️ {host}:{port} zaten kullanımda. Vite farklı port seçebilir.{RESET}")

        # Force Vite host/port for predictable URL
        frontend_process = subprocess.Popen(
            [npm_cmd, "run", "dev", "--", "--host", host, "--port", str(port)],
            cwd=os.path.join(os.getcwd(), "web", "frontend"),
            shell=True
        )
        processes.append(frontend_process)

        # 4. Tarayıcıyı Aç
        print(f"🌍 Tarayıcı bekleniyor...")
        if wait_for_port(host, port, timeout_sec=60):
            webbrowser.open(APP_URL)
            print(f"\n{GREEN}✅ Sistem Çalışıyor! {APP_URL}{RESET}")
        else:
            print(f"\n{YELLOW}⚠️ Frontend portu açılmadı: {host}:{port}{RESET}")
            print(f"{YELLOW}Lütfen terminal loglarını kontrol edin ve {APP_URL} adresini manuel açın.{RESET}")
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
    import argparse
    parser = argparse.ArgumentParser(description="Atlas Assistant Launcher")
    parser.add_argument("--agent", action="store_true", help="Run in Autonomous Agent Mode (No Web UI)")
    parser.add_argument("--live", action="store_true", help="Enable Live Uploads for Agent Mode")
    args = parser.parse_args()

    # Windows ANSI renkleri icin
    os.system('color')

    if args.agent:
        print(f"{GREEN}🤖 Starting Atlas Autonomous Agent...{RESET}")
        try:
            from core.system_check import ensure_sd_running, ensure_ollama_running
            
            # Ensure Services are Running
            ensure_ollama_running()
            ensure_sd_running()
            
            from core.orchestrator import Orchestrator
            # Dry run by default unless --live is passed
            dry_run = not args.live
            orchestrator = Orchestrator(dry_run=dry_run)
            orchestrator.run_pipeline()
        except ImportError as e:
            print(f"{RED}❌ Agent modules not found: {e}{RESET}")
    else:
        run_app()

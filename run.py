import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from shutil import which

try:
    from dotenv import dotenv_values
except Exception:
    dotenv_values = None

# Renkler
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

APP_URL = "http://127.0.0.1:5173"
ENV_FILE = Path(".env")
TUNNEL_SCRIPT = Path("tools") / "setup_tunnel.py"
IMAGE_SERVER_SCRIPT = Path("web") / "backend" / "image_server.py"
FRONTEND_ENV_FILE = Path("web") / "frontend" / ".env.local"
IMAGE_SERVER_PORT = 8010


def setup_utf8_console():
    """Force UTF-8 output on Windows terminals to avoid mojibake."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if os.name == "nt":
        try:
            os.system("chcp 65001 >nul")
        except Exception:
            pass

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


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


def read_env_file():
    if dotenv_values is None or not ENV_FILE.exists():
        return {}
    try:
        return dict(dotenv_values(str(ENV_FILE)))
    except Exception:
        return {}


def has_graph_config(env_map):
    required = ["FB_APP_ID", "FB_APP_SECRET", "FB_PAGE_ID", "IG_USER_ID", "FB_ACCESS_TOKEN"]
    return all((env_map.get(k) or "").strip() for k in required)


def wait_for_public_base_url(timeout_sec=20):
    start = time.time()
    last_val = ""
    while time.time() - start < timeout_sec:
        env_map = read_env_file()
        val = (env_map.get("PUBLIC_BASE_URL") or "").strip()
        if val and val != last_val:
            return val
        last_val = val
        time.sleep(0.5)
    return ""

def sync_frontend_token(token: str):
    """
    Backend'in bekledigi API token'ini frontend'e aktarir.

    Vite yalnizca VITE_ ile baslayan degiskenleri istemciye acar. Token her
    calistirmada .env.local'a yazilir; boylece kullanicinin elle bir sey
    kopyalamasi gerekmez.
    """
    if not token:
        return
    try:
        FRONTEND_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "# Bu dosya run.py tarafindan otomatik uretilir. Elle duzenlemeyin.\n"
            f"VITE_ATLAS_API_TOKEN={token}\n"
        )
        if FRONTEND_ENV_FILE.exists() and FRONTEND_ENV_FILE.read_text(encoding="utf-8") == content:
            return
        FRONTEND_ENV_FILE.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"{YELLOW}⚠️ Frontend token dosyasi yazilamadi: {e}{RESET}")
        print(f"{YELLOW}   Arayuz API'ye baglanamayabilir.{RESET}")


def start_image_server(processes):
    """
    Tunnel icin salt-okunur gorsel sunucusunu baslatir.

    Tunnel bu servise baglanir; ana backend (8000) disariya hic acilmaz.
    """
    if not IMAGE_SERVER_SCRIPT.exists():
        print(f"{RED}❌ {IMAGE_SERVER_SCRIPT} bulunamadi. Gorsel sunucusu baslatilamiyor.{RESET}")
        return False

    if is_port_in_use("127.0.0.1", IMAGE_SERVER_PORT):
        print(f"{YELLOW}⚠️ Port {IMAGE_SERVER_PORT} zaten kullanimda; mevcut sunucu varsayiliyor.{RESET}")
        return True

    print(f"🖼️  Gorsel sunucusu aciliyor (salt-okunur, port {IMAGE_SERVER_PORT})...")
    processes.append(subprocess.Popen([sys.executable, str(IMAGE_SERVER_SCRIPT)], cwd=os.getcwd()))
    return wait_for_port("127.0.0.1", IMAGE_SERVER_PORT, timeout_sec=20)


def start_tunnel(processes):
    """Cloudflare tunelini baslatir ve PUBLIC_BASE_URL hazir olana kadar bekler."""
    if not TUNNEL_SCRIPT.exists():
        print(f"{RED}❌ {TUNNEL_SCRIPT} bulunamadi.{RESET}")
        print(f"{YELLOW}   Graph API yuklemesi icin public URL gerekiyor.{RESET}")
        print(f"{YELLOW}   Cozum: repoyu guncelleyin veya PUBLIC_BASE_URL'i .env icine elle yazin.{RESET}")
        print(f"{YELLOW}   Tunnel olmadan devam ediliyor...{RESET}")
        return

    if not start_image_server(processes):
        print(f"{YELLOW}⚠️ Gorsel sunucusu hazir degil; tunnel yine de deneniyor.{RESET}")

    print("🌐 Graph API aktif: tunnel otomatik başlatılıyor...")
    processes.append(subprocess.Popen([sys.executable, str(TUNNEL_SCRIPT)], cwd=os.getcwd()))

    public_url = wait_for_public_base_url(timeout_sec=25)
    if public_url:
        print(f"{GREEN}✅ PUBLIC_BASE_URL hazır: {public_url}{RESET}")
    else:
        print(f"{YELLOW}⚠️ PUBLIC_BASE_URL henüz hazır değil. Tunnel terminalini kontrol edin.{RESET}")


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
        # 1. API token'i hazirla ve frontend'e aktar
        try:
            from core.runtime.api_auth import get_or_create_api_token
            api_token = get_or_create_api_token()
            sync_frontend_token(api_token)
            print(f"{GREEN}🔒 API token hazır (.env: ATLAS_API_TOKEN){RESET}")
        except Exception as e:
            print(f"{RED}⚠️ API token oluşturulamadı: {e}{RESET}")
            print(f"{YELLOW}   Backend /api/* uçları korumasız çalışacak.{RESET}")

        env_map = read_env_file()
        auto_tunnel = (env_map.get("AUTO_TUNNEL") or "1").strip() != "0"
        if auto_tunnel and has_graph_config(env_map):
            start_tunnel(processes)

        # 2. Backend Başlat
        print("📦 Backend sunucusu açılıyor...")
        backend_process = subprocess.Popen([sys.executable, "web/backend/main.py"], cwd=os.getcwd())
        processes.append(backend_process)

        # 3. Frontend Başlat
        print("🎨 Frontend arayüzü açılıyor...")
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
            shell=True,
        )
        processes.append(frontend_process)

        # 4. Tarayıcıyı Aç
        print("🌍 Tarayıcı bekleniyor...")
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
            p.kill()  # Garanti olsun

        # Windows'ta bazen subprocessler kalabiliyor, taskkill ile temizleyelim
        # Node ve Python süreçlerini temizlemek biraz agresif olabilir ama
        # sadece bu proje ozelse sorun olmaz. Simdilik sadece processleri kill ediyoruz.
        print("Güle güle! 👋")


if __name__ == "__main__":
    setup_utf8_console()

    import argparse

    parser = argparse.ArgumentParser(description="Atlas Assistant Launcher")
    parser.add_argument("--agent", action="store_true", help="Run in Autonomous Agent Mode (No Web UI)")
    parser.add_argument("--live", action="store_true", help="Enable Live Uploads for Agent Mode")
    args = parser.parse_args()

    # Windows ANSI renkleri icin
    os.system("color")

    if args.agent:
        print(f"{GREEN}🤖 Starting Atlas Autonomous Agent...{RESET}")
        try:
            from core.runtime.system_check import ensure_ollama_running, ensure_sd_running

            # Ensure Services are Running
            ensure_ollama_running()
            ensure_sd_running()

            from core.pipeline.orchestrator import Orchestrator

            # Dry run by default unless --live is passed
            dry_run = not args.live
            orchestrator = Orchestrator(dry_run=dry_run)
            orchestrator.run_pipeline()
        except ImportError as e:
            print(f"{RED}❌ Agent modules not found: {e}{RESET}")
    else:
        run_app()

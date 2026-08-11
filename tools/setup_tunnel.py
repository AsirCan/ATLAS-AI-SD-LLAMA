"""
Cloudflare quick tunnel kurulumu.

Instagram Graph API, paylasilacak gorseli internetten kendisi indirdigi icin
`generated_images/` klasorunun disaridan erisilebilir olmasi gerekiyor.

ONEMLI: Bu script tuneli ANA BACKEND'e (port 8000) DEGIL, yalnizca statik
gorsel sunan `web/backend/image_server.py`'ye (port 8010) baglar. Boylece
`/api/*` uclari disariya hic acilmaz.

Tunnel ayaga kalkinca olusan public URL `.env` icine `PUBLIC_BASE_URL`
olarak yazilir. Script, tunel acik kalsin diye calismaya devam eder.
"""

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

TUNNEL_TARGET_HOST = os.getenv("IMAGE_SERVER_HOST", "127.0.0.1")
TUNNEL_TARGET_PORT = os.getenv("IMAGE_SERVER_PORT", "8010")
TUNNEL_TARGET = f"http://{TUNNEL_TARGET_HOST}:{TUNNEL_TARGET_PORT}"

URL_PATTERN = re.compile(r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com")

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def find_cloudflared() -> str:
    """cloudflared ikilisini bul: once proje icinde, sonra PATH'te."""
    local_candidates = [
        ROOT / "tools" / "cloudflared" / "cloudflared.exe",
        ROOT / "tools" / "cloudflared" / "cloudflared",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return str(candidate)

    found = which("cloudflared") or which("cloudflared.exe")
    if found:
        return found

    raise FileNotFoundError(
        "cloudflared bulunamadi. 'python install.py' calistirin veya "
        "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ "
        "adresinden indirip tools/cloudflared/ altina koyun."
    )


def upsert_env_value(key: str, value: str) -> None:
    """`.env` icindeki tek bir anahtari gunceller, digerlerine dokunmaz."""
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()

    replaced = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        existing_key = stripped.split("=", 1)[0].strip()
        if existing_key == key:
            lines[i] = f"{key}={value}"
            replaced = True
            break

    if not replaced:
        lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def wait_for_target(timeout_sec: int = 20) -> bool:
    """Gorsel sunucusu ayaga kalkana kadar bekle."""
    import socket

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((TUNNEL_TARGET_HOST, int(TUNNEL_TARGET_PORT)), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    try:
        cloudflared = find_cloudflared()
    except FileNotFoundError as e:
        print(f"{RED}{e}{RESET}", file=sys.stderr)
        return 1

    if not wait_for_target():
        print(
            f"{YELLOW}Uyari: {TUNNEL_TARGET} henuz cevap vermiyor. "
            f"Tunnel yine de aciliyor; gorsel sunucusu sonra baslarsa duzelir.{RESET}"
        )

    print(f"{YELLOW}Cloudflare tuneli aciliyor -> {TUNNEL_TARGET}{RESET}")
    print(f"{YELLOW}(Yalnizca /images servis edilir, /api disariya acilmaz){RESET}")

    process = subprocess.Popen(
        [
            cloudflared,
            "tunnel",
            "--url",
            TUNNEL_TARGET,
            "--no-autoupdate",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    public_url = ""

    def shutdown(_signum=None, _frame=None):
        try:
            process.terminate()
        except Exception:
            pass

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        for line in process.stdout:
            line = line.rstrip()
            if not public_url:
                match = URL_PATTERN.search(line)
                if match:
                    public_url = match.group(0)
                    upsert_env_value("PUBLIC_BASE_URL", public_url)
                    print(f"{GREEN}PUBLIC_BASE_URL = {public_url}{RESET}")
                    print(f"{GREEN}.env guncellendi. Dogrulama: {public_url}/healthz{RESET}")
            # cloudflared'in kendi loglarini gorunur birak (hata ayiklama icin).
            print(line)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
        try:
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    if not public_url:
        print(f"{RED}Tunnel URL alinamadi. cloudflared ciktisini kontrol edin.{RESET}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Salt-okunur gorsel sunucusu.

Instagram Graph API, paylasilacak gorseli internet uzerinden kendisi indirir.
Bu yuzden `generated_images/` disariya acik olmak zorunda. Ancak ana backend
(`web/backend/main.py`) ayni anda `/api/*` uclarini da barindiriyor; tuneli
dogrudan ona baglamak butun API'yi internete cikarir.

Bu modul yalnizca statik gorselleri servis eder:
- Sadece GET/HEAD (StaticFiles varsayilani)
- Hicbir /api ucu yok
- Yazma, silme, konfigurasyon ucu yok

Cloudflare tuneli bu sunucuya baglanir (bkz. tools/setup_tunnel.py).
"""

import logging
import os
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Proje kokunden calistirilmayi bekler (run.py oyle baslatir).
IMAGES_DIR = Path("generated_images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.getenv("IMAGE_SERVER_HOST", "127.0.0.1")
PORT = int(os.getenv("IMAGE_SERVER_PORT", "8010"))

app = FastAPI(
    title="Atlas Image Server",
    description="Instagram Graph API icin salt-okunur gorsel sunucusu",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    # Tunnel URL'i sizsa bile arama motorlari indekslemesin.
    return "User-agent: *\nDisallow: /\n"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Atlas image server: http://%s:%s/images (salt-okunur)", HOST, PORT)
    try:
        uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
    except OSError:
        logger.exception("Image server baslatilamadi (%s:%s)", HOST, PORT)
        sys.exit(1)

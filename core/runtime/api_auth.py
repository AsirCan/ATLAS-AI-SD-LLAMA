"""
Yerel API kimlik dogrulamasi.

Backend 127.0.0.1'e baglaniyor olsa da, tek savunma hatti "portu disari acmamak"
olmamali. Bu modul basit bir paylasimli token uretir ve dogrular:

- Token `.env` icinde `ATLAS_API_TOKEN` olarak tutulur.
- `run.py` ilk calistirmada token yoksa uretir ve frontend'e aktarir.
- Backend, `/api/*` isteklerinde `X-Atlas-Token` basligini bekler.

Bu, makinede calisan baska bir programin (ornegin tarayicidaki herhangi bir
sekme) API'yi cagirmasini da engeller.
"""

import os
import secrets
from pathlib import Path

ENV_KEY = "ATLAS_API_TOKEN"
HEADER_NAME = "X-Atlas-Token"


def _env_path() -> Path:
    return Path(".env")


def _read_env_token() -> str:
    """`.env` dosyasindaki token'i okur (process env'den bagimsiz)."""
    path = _env_path()
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == ENV_KEY:
            return value.strip()
    return ""


def _write_env_token(token: str) -> None:
    path = _env_path()
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    replaced = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.split("=", 1)[0].strip() == ENV_KEY:
            lines[i] = f"{ENV_KEY}={token}"
            replaced = True
            break

    if not replaced:
        lines.append(f"{ENV_KEY}={token}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def read_api_token() -> str:
    """
    Gecerli token'i dondurur. Once process ortami, sonra `.env`.
    Token yoksa bos string doner (cagiran taraf karar verir).
    """
    from_env = (os.getenv(ENV_KEY) or "").strip()
    if from_env:
        return from_env
    return _read_env_token()


def get_or_create_api_token() -> str:
    """
    Token varsa dondurur, yoksa uretip `.env` icine yazar.
    Yalnizca launcher (run.py) tarafindan cagrilmali.
    """
    existing = read_api_token()
    if existing:
        return existing

    token = secrets.token_urlsafe(32)
    _write_env_token(token)
    os.environ[ENV_KEY] = token
    return token


def is_authorized(provided: str | None, expected: str | None = None) -> bool:
    """
    Sabit zamanli karsilastirma ile token dogrular.
    Beklenen token tanimli degilse yetkilendirme kapali sayilir (False).
    """
    expected_token = (expected if expected is not None else read_api_token()).strip()
    if not expected_token:
        return False
    if not provided:
        return False
    return secrets.compare_digest(str(provided).strip(), expected_token)

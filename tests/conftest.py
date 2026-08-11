"""
Test ortami kurulumu.

Iki isi yapar:

1. **Izolasyon.** Testler ag, GPU, Ollama, Stable Diffusion veya Instagram'a
   dokunmaz. Veritabani yollari gecici klasore yonlendirilir; boylece
   calistirmak projenin gercek `data/` klasorunu kirletmez.

2. **Agir bagimliliklari stub'lar.** `instagrapi`, `feedparser`,
   `speech_recognition` gibi paketler yalnizca import edilebilmek icin
   gerekiyor; test edilen mantik onlara bagli degil. Paket gercekten
   kuruluysa stub DEVREYE GIRMEZ (gercek paket kazanir).

ONEMLI: Ortam degiskenleri `core.runtime.config` import edilmeden ONCE
ayarlanmali; o modul degerleri import aninda okuyor.
"""

import importlib
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# core / web paketleri import edilebilsin
for path in (str(ROOT), str(ROOT / "web" / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

# ---------------------------------------------------------------------------
# 1) Ortam izolasyonu — core.runtime.config import edilmeden once
# ---------------------------------------------------------------------------
_TMP = Path(tempfile.mkdtemp(prefix="atlas_tests_"))

os.environ.setdefault("NEWS_MEMORY_BACKEND", "sqlite")
os.environ["NEWS_MEMORY_DB_PATH"] = str(_TMP / "news_memory.db")
os.environ["NEWS_MEMORY_JSON_PATH"] = str(_TMP / "news_memory.json")

# Testlerin bilinen bir token ile calismasi icin
TEST_API_TOKEN = "pytest-token-0123456789abcdef"
os.environ["ATLAS_API_TOKEN"] = TEST_API_TOKEN

# Legacy instagrapi yolu testlerde kapali baslasin (varsayilan davranis)
os.environ["ALLOW_LEGACY_INSTAGRAPI"] = "0"

# Graph API kurulumu YOK senaryosu varsayilan
for _key in ("IG_USER_ID", "FB_ACCESS_TOKEN", "PUBLIC_BASE_URL"):
    os.environ.pop(_key, None)


# ---------------------------------------------------------------------------
# 2) Agir bagimlilik stub'lari (yalnizca paket kurulu degilse)
# ---------------------------------------------------------------------------
def _is_installed(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _register(name: str, module: types.ModuleType) -> None:
    """Paket kurulu degilse stub'i kaydeder."""
    if _is_installed(name):
        return
    sys.modules[name] = module


class _StubInstagrapiClient:
    """
    Cagrilirsa testi patlatir.

    Bu bilincli: instagrapi yolunun ASLA otomatik devreye girmemesi gerekiyor
    (issue #11). Kapi bozulursa test sessizce gecmek yerine hata verir.
    """

    def __getattr__(self, item):
        def _explode(*_args, **_kwargs):
            raise AssertionError(
                f"instagrapi.{item} cagrildi — legacy upload kapisi calismiyor!"
            )

        return _explode


_instagrapi = types.ModuleType("instagrapi")
_instagrapi.Client = _StubInstagrapiClient
_register("instagrapi", _instagrapi)

_instagrapi_exc = types.ModuleType("instagrapi.exceptions")
for _name in ("TwoFactorRequired", "ChallengeRequired", "LoginRequired"):
    setattr(_instagrapi_exc, _name, type(_name, (Exception,), {}))
_register("instagrapi.exceptions", _instagrapi_exc)

_feedparser = types.ModuleType("feedparser")
_feedparser.parse = lambda *_a, **_k: types.SimpleNamespace(entries=[])
_register("feedparser", _feedparser)

_sr = types.ModuleType("speech_recognition")
_sr.Recognizer = object
_sr.AudioFile = object
_register("speech_recognition", _sr)

_keyring = types.ModuleType("keyring")
_keyring.get_password = lambda *_a, **_k: None
_keyring.set_password = lambda *_a, **_k: None
_register("keyring", _keyring)


# ---------------------------------------------------------------------------
# 3) Ortak fixture ve yardimcilar
# ---------------------------------------------------------------------------
import pytest  # noqa: E402


class FakeLLM:
    """
    LLMService yerine gecen sahte istemci.

    `responses` ile sirayla dondurulecek cevaplar verilir. Boylece testler
    Ollama'ya hic baglanmadan agent mantigini dogrular.
    """

    def __init__(self, responses=None, text_response=""):
        self.responses = list(responses or [])
        self.text_response = text_response
        self.calls = []
        self.cancel_checker = None

    def set_cancel_checker(self, checker):
        self.cancel_checker = checker

    def generate_response(self, prompt, schema=None, retries=3):
        self.calls.append(prompt)
        if not self.responses:
            raise AssertionError("FakeLLM: beklenenden fazla cagri yapildi")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def generate_json(self, prompt, schema=None, **kwargs):
        return self.generate_response(prompt, schema=schema)

    def ask(self, prompt, **kwargs):
        self.calls.append(prompt)
        return self.text_response

    def ask_english(self, prompt, **kwargs):
        return self.ask(prompt)


@pytest.fixture
def fake_llm():
    return FakeLLM


@pytest.fixture
def tmp_env(monkeypatch):
    """Ortam degiskenini test suresince degistirmek icin kisayol."""

    def _set(**values):
        for key, value in values.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(value))

    return _set


@pytest.fixture
def api_token():
    return TEST_API_TOKEN

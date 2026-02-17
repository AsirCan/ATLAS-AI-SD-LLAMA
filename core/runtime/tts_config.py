import os

# Proje kok dizini (core klasorunun bir ustu)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_model_path(env_key: str, default_rel_path: str) -> str:
    raw = os.environ.get(env_key, default_rel_path)
    if os.path.isabs(raw):
        return raw
    return os.path.join(BASE_DIR, raw)


# Default Turkish Piper model (chat/tts endpoint default)
PIPER_MODEL = _resolve_model_path("PIPER_MODEL", os.path.join("models", "tr_TR-fahrettin-medium.onnx"))
PIPER_CONFIG = _resolve_model_path("PIPER_CONFIG", os.path.join("models", "tr_TR-fahrettin-medium.onnx.json"))

# Default English Piper model for video narration
PIPER_EN_MODEL = _resolve_model_path("PIPER_EN_MODEL", os.path.join("models", "en_US-lessac-medium.onnx"))
PIPER_EN_CONFIG = _resolve_model_path("PIPER_EN_CONFIG", os.path.join("models", "en_US-lessac-medium.onnx.json"))

# Piper çalıştırılabilir dosyası
#
# Not: Windows'ta pip ile kurulan bazı `piper-tts` sürümleri (özellikle 1.4.x)
# `piper.espeakbridge` bileşenini içermeyebilir ve TTS çalışmaz.
# Bu durumda "standalone" Piper dağıtımından gelen `piper.exe` kullanmak gerekir.
#
# Kullanım:
# - .env içine: PIPER_BIN=C:\path\to\piper.exe
# - veya projeye kopyala: tools/piper/piper.exe (otomatik bulunur)
def _first_existing_path(paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                return p
        except Exception:
            pass
    return None


def _resolve_piper_bin() -> str:
    env = os.environ.get("PIPER_BIN")
    if env:
        # Relative path support: interpret relative to project root
        if not os.path.isabs(env):
            env = os.path.join(BASE_DIR, env)
        return env

    # Common local locations (absolute)
    candidates = [
        os.path.join(BASE_DIR, "tools", "piper", "piper.exe"),
        os.path.join(BASE_DIR, "tools", "piper", "piper"),
        os.path.join(BASE_DIR, "bin", "piper.exe"),
        os.path.join(BASE_DIR, "bin", "piper"),
        os.path.join(BASE_DIR, "piper", "piper.exe"),
        os.path.join(BASE_DIR, "piper", "piper"),
    ]
    found = _first_existing_path(candidates)
    return found or "piper"


PIPER_BIN = _resolve_piper_bin()


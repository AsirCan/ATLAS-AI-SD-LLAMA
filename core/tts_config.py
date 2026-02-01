import os

# Proje kök dizini (core klasörünün bir üstü)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Piper model yolları (server-side TTS için sadece dosya yolu gerekir)
PIPER_MODEL = os.path.join(BASE_DIR, "models", "tr_TR-fahrettin-medium.onnx")
PIPER_CONFIG = os.path.join(BASE_DIR, "models", "tr_TR-fahrettin-medium.onnx.json")

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


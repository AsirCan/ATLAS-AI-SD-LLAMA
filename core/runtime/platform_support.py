"""
Platform tespiti ve tasinabilir yol yardimcilari (issue #9).

Proje su an YALNIZCA WINDOWS'ta calisir: Forge sabit `C:\\Forge` yoluna
kuruluyor, piper.exe / cloudflared.exe bekleniyor, winget ve `chcp 65001`
kullaniliyor. Tam capraz platform destegi buyuk bir is.

Bu modul issue #9'un tanimladigi MINIMUM hedefi karsilar:
POSIX'te yarim kurulum birakmak yerine anlasilir bir hatayla cikmak.

Adi bilincli olarak `platform` degil: stdlib modulunu golgelememesi icin.
"""

import os
import sys
import tempfile
from pathlib import Path

WINDOWS_ONLY_MESSAGE = (
    "Atlas Assistant su an yalnizca Windows'ta calisiyor.\n"
    "\n"
    "Sebep:\n"
    "  - Stable Diffusion (Forge) kurulumu C:\\Forge yolunu varsayiyor\n"
    "  - TTS icin piper.exe, tunnel icin cloudflared.exe bekleniyor\n"
    "  - Kurulum winget kullaniyor\n"
    "\n"
    "Bkz. https://github.com/AsirCan/ATLAS-AI-SD-LLAMA/issues/9"
)


def is_windows() -> bool:
    return os.name == "nt"


def require_windows(*, exit_on_failure: bool = True) -> bool:
    """
    Windows degilse anlasilir bir mesaj basar.

    Yarim kurulum birakmamak icin varsayilan davranis programdan cikmaktir.
    Test edilebilmesi icin `exit_on_failure=False` ile sadece kontrol yapilabilir.
    """
    if is_windows():
        return True

    print(WINDOWS_ONLY_MESSAGE, file=sys.stderr)
    if exit_on_failure:
        sys.exit(1)
    return False


def temp_dir() -> Path:
    """
    Gecici klasor.

    `os.environ["TEMP"]` POSIX'te tanimsiz oldugu icin KeyError firlatiyordu;
    tempfile.gettempdir() her platformda calisir.
    """
    return Path(tempfile.gettempdir())


def executable_name(stem: str) -> str:
    """Platforma gore ikili dosya adi: 'piper' -> 'piper.exe' (Windows)."""
    return f"{stem}.exe" if is_windows() else stem

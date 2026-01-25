# TÜM ses, Piper, sounddevice burada

import sys
import os
import random
import time
import threading
import subprocess

import sounddevice as sd
import soundfile as sf
import speech_recognition as sr

from core.config import RED

import numpy as np

mic_lock = False
dur_event = threading.Event()

# 🔴 YENİ FLAG
interrupted = False

# Proje kök dizinini bul (core klasörünün bir üstü)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPER_MODEL = os.path.join(BASE_DIR, "models", "tr_TR-fahrettin-medium.onnx")
PIPER_CONFIG = os.path.join(BASE_DIR, "models", "tr_TR-fahrettin-medium.onnx.json")

def sanitize_text(text: str) -> str:
    return text.encode("utf-8", "ignore").decode("utf-8")

def speak(text: str):
    global mic_lock, interrupted
    mic_lock = True
    interrupted = False

    print(f" >> Atlas: {text}")
    wav_file = f"ses_{random.randint(0,99999)}.wav"

    try:
        subprocess.run(
            [
                "piper",
                "-m", PIPER_MODEL,
                "-c", PIPER_CONFIG,
                "-f", wav_file,
                "--length-scale", "0.95"
            ],
            input=text,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception as e:
        print(RED + f"Piper TTS hatası: {e}")
        mic_lock = False
        return False

    data, samplerate = sf.read(wav_file, dtype="float32")
    # 🔹 20 ms sessizlik ekle
    padding = int(0.02 * samplerate)
    silence = np.zeros(padding, dtype="float32")
    data = np.concatenate((silence, data))
    dur_event.clear()
    sd.play(data, samplerate)

    t = threading.Thread(target=_kesme_dinle, daemon=True)
    t.start()

    while sd.get_stream() is not None and sd.get_stream().active:
        time.sleep(0.02)

    dur_event.set()
    sd.stop()

    try:
        os.remove(wav_file)
    except:
        pass

    mic_lock = False

    # 🔴 KESİLDİ Mİ BİLGİSİNİ DÖNDÜR
    was_interrupted = interrupted
    interrupted = False
    return was_interrupted


def _kesme_dinle():
    global interrupted
    r = sr.Recognizer()
    with sr.Microphone() as source:
        while not dur_event.is_set():
            try:
                audio = r.listen(source, timeout=0.2, phrase_time_limit=0.6)
                if audio and len(audio.frame_data) > 1000:
                    interrupted = True
                    sd.stop()
                    dur_event.set()
                    return
            except:
                pass

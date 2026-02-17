import json
import subprocess
import threading
import time
from typing import Any, Dict, List, Literal, Optional, Sequence

import requests

from core.runtime.config import RED, RESET, YELLOW

# ==================================================
# Ollama Settings
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"
# ==================================================

SYSTEM_PROMPT = (
    "Senin adın Atlas. Türkçe konuş. "
    "Kısa ve net cevap ver. "
    "Gerektiğinde tek, kısa soru sor. "
    "Yanıtları 1-3 cümleyle sınırla. "
    "Bilmiyorsan açıkça söyle, uydurma."
)


def _clean_llm_text(text: str) -> str:
    return text.replace("```json", "").replace("```", "").strip()


_DEFAULT_LLM_SERVICE = None


def get_llm_service():
    global _DEFAULT_LLM_SERVICE
    if _DEFAULT_LLM_SERVICE is None:
        _DEFAULT_LLM_SERVICE = LLMService()
    return _DEFAULT_LLM_SERVICE


def llm_answer(msg: str, system_msg: str = None) -> str:
    # 3 kere deneme hakkı veriyoruz
    max_retries = 3

    # Eğer özel bir system prompt gelmediyse varsayılanı kullan
    final_system_prompt = system_msg if system_msg else SYSTEM_PROMPT

    for i in range(max_retries):
        try:
            # Timeout süresini artırdık çünkü modelin yüklenmesi uzun sürebilir
            return get_llm_service().ask(msg, system=final_system_prompt, timeout=180, retries=1)

        except Exception as e:
            print(RED + f"[OLLAMA HATASI - Deneme {i+1}/{max_retries}] {e}")
            if "Cancelled during LLM request" in str(e):
                return "İstek iptal edildi."
            if "500" in str(e) or "Connection refused" in str(e):
                print(f"{YELLOW}⏳ VRAM'in boşalması bekleniyor (5 sn)...{RESET}")
                time.sleep(5)  # 5 saniye bekle ve tekrar dene
            else:
                # Başka bir hataysa (örn: internet yok) bekleme, direkt çık
                break

    return "Şu an cevap veremiyorum (Teknik arıza)."


def ollama_warmup():
    """
    Ollama modelini Atlas başlamadan önce RAM/GPU'ya yükler.
    Offline modda 500 hatasını önler.
    """
    try:
        print("🧠 Ollama modeli ısıtılıyor (warm-up)...")
        subprocess.Popen(
            ["ollama", "run", MODEL],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2.5)
        print("✅ Ollama warm-up tamamlandı.")
    except Exception as e:
        print(f"⚠️ Ollama warm-up başarısız: {e}")


# llm.py dosyasının en altına ekle:

def unload_ollama():
    """
    Ollama modelini VRAM'den zorla boşaltır.
    Böylece Stable Diffusion için yer açılır.
    """
    try:
        get_llm_service().unload(timeout=3)
        print(f"{RED}🧹 Ollama VRAM'den temizlendi.{RESET}")
    except Exception as e:
        print(f"⚠️ VRAM temizleme hatası: {e}")


def visual_prompt_generator(user_text: str) -> str:
    """
    Kullanıcının girdiği (muhtemelen Türkçe) metni,
    Stable Diffusion için uygun İNGİLİZCE prompt haline getirir.
    """
    system_msg = (
        "You are a world-class AI Art Director and Prompt Engineer known for creating 'Sora-level' realism. "
        "Your task: Convert the user's input (in Turkish) into a BREATHTAKING, CINEMATIC, and HYPER-REALISTIC English image prompt. "
        "Rules:\n"
        "1. Translate the core concept but ELEVATE it to a blockbuster movie scene.\n"
        "2. REQUIRED KEYWORDS: 'Award-winning photography, 8k raw photo, soft cinematic lighting, extremely detailed, Unreal Engine 5 render, sharp focus, 85mm lens, f/1.8, bokeh'.\n"
        "3. STYLE: Hyper-realism, Documentary, National Geographic, IMAX quality.\n"
        "4. AVOID: 'Cartoon, illustration, 3d render looking, painting, drawing, low resolution'.\n"
        "5. Output ONLY the prompt string.\n"
        "6. Example: 'sarı araba' -> 'A hyper-realistic 8k shot of a yellow sports car drifting on a rainy asphalt road, reflection of neon city lights, cinematic lighting, dramatic atmosphere, shot on 35mm film, award-winning photography.'"
    )

    try:
        prompt_en = get_llm_service().ask(user_text, system=system_msg, timeout=60, retries=1).strip()

        # Temizlik
        if ":" in prompt_en and len(prompt_en.split(":")[0]) < 20:  # "Detailed prompt: ..." gibi şeyleri temizle
            prompt_en = prompt_en.split(":")[-1].strip()

        return prompt_en

    except Exception as e:
        print(f"Prompt Generation Error: {e}")
        # Hata olursa en azından orijinalini (veya basit çeviriyi) döndürmeye çalışalım
        # ama LLM yoksa yapacak bir şey yok, orijinali yolla.
        return user_text


# ==================================================
# UNIFIED SERVICE LAYER (For Multi-Agent System)
# ==================================================
MessageRole = Literal["system", "user", "assistant"]


class LLMService:
    def __init__(self, model: str = None, host: str = "http://localhost:11434"):
        # Use existing MODEL constant if none provided
        self.model = model or MODEL
        self.host = host
        self.api_url = f"{host}/api/chat"
        self.cancel_checker = None

    def set_cancel_checker(self, checker):
        self.cancel_checker = checker

    def _is_cancelled(self) -> bool:
        try:
            return bool(self.cancel_checker and self.cancel_checker())
        except Exception:
            return False

    def _post_with_cancel(self, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        done = threading.Event()

        def _worker():
            try:
                response = requests.post(self.api_url, json=payload, timeout=timeout)
                response.raise_for_status()
                result["json"] = response.json()
            except Exception as e:
                result["error"] = e
            finally:
                done.set()

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        while not done.wait(0.2):
            if self._is_cancelled():
                raise Exception("Cancelled during LLM request")

        if "error" in result:
            raise result["error"]
        return result["json"]

    def chat(
        self,
        messages: Sequence[Dict[str, str]],
        *,
        format: Optional[Literal["json"]] = None,
        timeout: int = 60,
        retries: int = 3,
    ) -> str:
        payload: Dict[str, Any] = {"model": self.model, "messages": list(messages), "stream": False}
        if format:
            payload["format"] = format

        last_exc: Optional[Exception] = None
        for _ in range(retries):
            if self._is_cancelled():
                raise Exception("Cancelled during LLM request")
            try:
                result = self._post_with_cancel(payload, timeout=timeout)
                return result.get("message", {}).get("content", "")
            except Exception as e:
                if "Cancelled during LLM request" in str(e):
                    raise
                last_exc = e
                time.sleep(2)
        raise Exception(f"Failed to chat with LLM after {retries} retries: {last_exc}")

    def ask(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        timeout: int = 60,
        retries: int = 3,
        format: Optional[Literal["json"]] = None,
    ) -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, format=format, timeout=timeout, retries=retries)

    def ask_english(self, prompt: str, *, timeout: int = 60, retries: int = 3) -> str:
        return self.ask(
            prompt,
            system="You are a creative AI visual director. You MUST write in ENGLISH only.",
            timeout=timeout,
            retries=retries,
        )

    def generate_json(
        self,
        prompt: str,
        *,
        schema: Dict[str, Any],
        system: Optional[str] = None,
        timeout: int = 60,
        retries: int = 3,
    ) -> Dict[str, Any]:
        schema_hint = json.dumps(schema, ensure_ascii=False)
        final_prompt = (
            f"{prompt}\n\nIMPORTANT: Return ONLY a valid JSON object matching this schema: {schema_hint}"
        )

        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            if self._is_cancelled():
                raise Exception("Cancelled during LLM request")
            try:
                response_text = self.ask(
                    final_prompt,
                    system=system,
                    timeout=timeout,
                    retries=1,
                    format="json",
                )
                return json.loads(_clean_llm_text(response_text))
            except Exception as e:
                if "Cancelled during LLM request" in str(e):
                    raise
                last_exc = e
                print(f"LLM JSON parse error (Attempt {attempt+1}/{retries}): {e}")
                time.sleep(1)
        raise Exception(f"Failed to generate valid JSON from LLM after {retries} retries: {last_exc}")

    def unload(self, *, timeout: int = 3) -> bool:
        endpoints = [f"{self.host}/api/generate", f"{self.host}/api/chat"]
        for url in endpoints:
            try:
                if url.endswith("/api/generate"):
                    payload = {"model": self.model, "keep_alive": 0, "prompt": " "}
                else:
                    payload = {
                        "model": self.model,
                        "keep_alive": 0,
                        "messages": [{"role": "user", "content": " "}],
                        "stream": False,
                    }
                requests.post(url, json=payload, timeout=timeout)
                return True
            except Exception:
                continue
        return False

    # Backwards-compat for agent code already using generate_response(prompt, schema=...)
    def generate_response(self, prompt: str, schema: Optional[Dict] = None, retries: int = 3) -> Dict[str, Any]:
        if schema:
            return self.generate_json(prompt, schema=schema, retries=retries)
        return {"response": self.ask(prompt, retries=retries)}

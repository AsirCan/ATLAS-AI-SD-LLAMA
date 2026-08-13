import json
import logging
import subprocess
import threading
import time
from collections.abc import Sequence
from typing import Any, Literal

import requests

from core.errors import CancelledError, LLMResponseError, LLMUnavailableError

logger = logging.getLogger(__name__)

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


def llm_answer(msg: str, system_msg: str | None = None) -> str:
    # 3 kere deneme hakkı veriyoruz
    max_retries = 3

    # Eğer özel bir system prompt gelmediyse varsayılanı kullan
    final_system_prompt = system_msg if system_msg else SYSTEM_PROMPT

    for i in range(max_retries):
        try:
            # Timeout süresini artırdık çünkü modelin yüklenmesi uzun sürebilir
            return get_llm_service().ask(msg, system=final_system_prompt, timeout=180, retries=1)

        except CancelledError:
            return "İstek iptal edildi."
        except LLMUnavailableError:
            logger.exception("Ollama request failed (attempt %s/%s)", i + 1, max_retries)
            if i < max_retries - 1:
                logger.info("VRAM release is being given 5 seconds before retry")
                time.sleep(5)
        except LLMResponseError:
            logger.exception("Ollama returned an unusable response")
            break

    return "Şu an cevap veremiyorum (Teknik arıza)."


def ollama_warmup():
    """
    Ollama modelini Atlas başlamadan önce RAM/GPU'ya yükler.
    Offline modda 500 hatasını önler.
    """
    try:
        logger.info("Ollama model warm-up is starting")
        subprocess.Popen(
            ["ollama", "run", MODEL],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2.5)
        logger.info("Ollama model warm-up completed")
    except OSError:
        logger.exception("Ollama warm-up could not be started")


# llm.py dosyasının en altına ekle:


def unload_ollama():
    """
    Ollama modelini VRAM'den zorla boşaltır.
    Böylece Stable Diffusion için yer açılır.
    """
    unloaded = get_llm_service().unload(timeout=3)
    if unloaded:
        logger.info("Ollama model unloaded from memory")
    else:
        logger.warning("Ollama model could not be unloaded from memory")
    return unloaded


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

    except (LLMUnavailableError, LLMResponseError):
        logger.exception("Visual prompt generation failed; using the original prompt")
        return user_text


# ==================================================
# UNIFIED SERVICE LAYER (For Multi-Agent System)
# ==================================================
MessageRole = Literal["system", "user", "assistant"]


class LLMService:
    def __init__(self, model: str | None = None, host: str = "http://localhost:11434"):
        # Use existing MODEL constant if none provided
        self.model = model or MODEL
        self.host = host
        self.api_url = f"{host}/api/chat"
        self.cancel_checker = None

    def set_cancel_checker(self, checker):
        self.cancel_checker = checker

    def _is_cancelled(self) -> bool:
        return bool(self.cancel_checker and self.cancel_checker())

    def _post_with_cancel(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        done = threading.Event()

        def _worker():
            try:
                response = requests.post(self.api_url, json=payload, timeout=timeout)
                response.raise_for_status()
                result["json"] = response.json()
            except Exception as exc:  # Thread boundary: re-raised on the caller thread.
                result["error"] = exc
            finally:
                done.set()

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        while not done.wait(0.2):
            if self._is_cancelled():
                raise CancelledError("Cancelled during LLM request")

        if "error" in result:
            raise result["error"]
        return result["json"]

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        format: Literal["json"] | None = None,
        timeout: int = 60,
        retries: int = 3,
    ) -> str:
        payload: dict[str, Any] = {"model": self.model, "messages": list(messages), "stream": False}
        if format:
            payload["format"] = format

        last_exc: requests.RequestException | None = None
        for attempt in range(retries):
            if self._is_cancelled():
                raise CancelledError("Cancelled during LLM request")
            try:
                result = self._post_with_cancel(payload, timeout=timeout)
                content = result.get("message", {}).get("content", "")
                if not isinstance(content, str):
                    raise LLMResponseError("Ollama response content is not text")
                return content
            except CancelledError:
                raise
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                logger.warning(
                    "Ollama connection attempt %s/%s failed",
                    attempt + 1,
                    retries,
                    exc_info=True,
                )
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status is not None and status < 500:
                    raise LLMResponseError(f"Ollama HTTP {status}") from exc
                last_exc = exc
                logger.warning(
                    "Ollama HTTP request attempt %s/%s failed",
                    attempt + 1,
                    retries,
                    exc_info=True,
                )
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "Ollama request attempt %s/%s failed",
                    attempt + 1,
                    retries,
                    exc_info=True,
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise LLMResponseError(str(exc)) from exc

            if attempt < retries - 1:
                time.sleep(2)

        raise LLMUnavailableError(str(last_exc)) from last_exc

    def ask(
        self,
        prompt: str,
        *,
        system: str | None = None,
        timeout: int = 60,
        retries: int = 3,
        format: Literal["json"] | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
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
        schema: dict[str, Any],
        system: str | None = None,
        timeout: int = 60,
        retries: int = 3,
    ) -> dict[str, Any]:
        schema_hint = json.dumps(schema, ensure_ascii=False)
        final_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY a valid JSON object matching this schema: {schema_hint}"

        last_exc: json.JSONDecodeError | None = None
        for attempt in range(retries):
            if self._is_cancelled():
                raise CancelledError("Cancelled during LLM request")
            response_text = self.ask(
                final_prompt,
                system=system,
                timeout=timeout,
                retries=1,
                format="json",
            )
            try:
                result = json.loads(_clean_llm_text(response_text))
                if not isinstance(result, dict):
                    raise LLMResponseError("Ollama JSON response is not an object")
                return result
            except json.JSONDecodeError as exc:
                last_exc = exc
                logger.warning(
                    "Ollama JSON parse attempt %s/%s failed",
                    attempt + 1,
                    retries,
                    exc_info=True,
                )
                if attempt < retries - 1:
                    time.sleep(1)
        raise LLMResponseError(f"Valid JSON was not produced after {retries} attempts") from last_exc

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
                response = requests.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                return True
            except requests.RequestException:
                logger.warning("Ollama unload endpoint failed: %s", url, exc_info=True)
                continue
        return False

    # Backwards-compat for agent code already using generate_response(prompt, schema=...)
    def generate_response(self, prompt: str, schema: dict | None = None, retries: int = 3) -> dict[str, Any]:
        if schema:
            return self.generate_json(prompt, schema=schema, retries=retries)
        return {"response": self.ask(prompt, retries=retries)}

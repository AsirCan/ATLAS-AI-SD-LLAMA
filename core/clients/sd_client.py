import base64
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import requests

from core.runtime.config import (
    GREEN,
    RED,
    RESET,
    SD_ADDETAILER_CONFIDENCE,
    SD_ADDETAILER_ENABLE_HANDS,
    SD_ADDETAILER_HUMAN_ONLY,
    SD_ADDETAILER_SKIP_ON_CROWD,
    SD_AUTO_BEST_HR_UPSCALER,
    SD_CFG_SCALE,
    SD_CONTROLNET_GUIDANCE_END,
    SD_CONTROLNET_GUIDANCE_START,
    SD_CONTROLNET_WEIGHT,
    SD_ENABLE_ADDETAILER,
    SD_ENABLE_CONTROLNET,
    SD_ENABLE_HIRES_FIX,
    SD_ENABLE_POST_UPSCALE,
    SD_FACE_RESTORATION_MODEL,
    SD_HEIGHT,
    SD_HIRES_DENOISE,
    SD_HIRES_SCALE,
    SD_HIRES_UPSCALER,
    SD_MAX_PROMPT_CHARS,
    SD_POST_UPSCALE_FACTOR,
    SD_POST_UPSCALER,
    SD_PREFERRED_HR_UPSCALERS,
    SD_RESTORE_FACES,
    SD_SAMPLER,
    SD_STEPS,
    SD_WIDTH,
    YELLOW,
)

# ==================================================
# Forge (Stable Diffusion) API
URL = "http://127.0.0.1:7860"

DEFAULT_NEGATIVE_PROMPT = (
    "cartoon, anime, illustration, painting, drawing, text, watermark, signature, logo, "
    "split image, double exposure, grid, collage, bad anatomy, bad proportions, deformed, blurry, "
    "low quality, pixelated, worst quality, low resolution, ugly, malformed limbs, extra fingers, "
    "missing fingers, fused fingers, disfigured hands, poorly drawn face, asymmetrical eyes, cloned face, "
    "distorted face, unnatural skin, fake, 3d render, cgi look, plastic looking, overexposed, underexposed"
)

PHOTOREAL_QUALITY_ANCHOR = (
    "photorealistic documentary photo, single coherent scene, physically plausible geometry, "
    "correct human anatomy, natural face symmetry, realistic hands, natural skin texture, "
    "balanced exposure, clean background continuity"
)

HUMAN_PROMPT_KEYWORDS = (
    "person",
    "people",
    "human",
    "man",
    "woman",
    "face",
    "portrait",
    "child",
    "doctor",
    "worker",
    "crowd",
    "soldier",
)

CROWD_PROMPT_KEYWORDS = (
    "crowd",
    "protest",
    "demonstration",
    "rally",
    "audience",
    "festival",
    "stadium",
    "parade",
    "many people",
    "group of people",
    "street scene",
)

_CAPABILITY_CACHE: Dict[str, Any] = {
    "upscalers": None,
    "scripts_txt2img": None,
    "face_restorers": None,
    "controlnet_models": None,
    "checked_at": 0.0,
}


def get_image_folder():
    """Create date-based output folder."""
    base_folder = "generated_images"
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(base_folder, today)
    os.makedirs(path, exist_ok=True)
    return path


def save_image_base64(img_base64):
    """Save base64 image output as PNG."""
    folder = get_image_folder()
    existing_files = [f for f in os.listdir(folder) if f.endswith(".png")]

    # Pick next max index, do not rely on file count.
    max_num = 0
    for f in existing_files:
        try:
            num = int(f.split("_")[1].split(".")[0])
            if num > max_num:
                max_num = num
        except Exception:
            pass

    file_number = max_num + 1
    filename = f"atlas_{file_number:03d}.png"
    file_path = os.path.join(folder, filename)
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(img_base64))
    return file_path


def _sanitize_prompt(prompt_en: str) -> str:
    prompt_en = (prompt_en or "").strip()
    if "Note:" in prompt_en:
        prompt_en = prompt_en.split("Note:")[0].strip()
    if "(Note" in prompt_en:
        prompt_en = prompt_en.split("(Note")[0].strip()
    if "Here is" in prompt_en and ":" in prompt_en:
        prompt_en = prompt_en.split(":", 1)[-1].strip()
    return prompt_en


def _apply_quality_anchor(prompt_en: str) -> str:
    prompt = (prompt_en or "").strip()
    if not prompt:
        return prompt
    if PHOTOREAL_QUALITY_ANCHOR.lower() not in prompt.lower():
        prompt = f"{prompt}, {PHOTOREAL_QUALITY_ANCHOR}"
    if len(prompt) > SD_MAX_PROMPT_CHARS:
        prompt = prompt[:SD_MAX_PROMPT_CHARS].rstrip(", ")
    return prompt


def _safe_get_json(endpoint: str, timeout: int = 3) -> Optional[Any]:
    try:
        r = requests.get(endpoint, timeout=timeout)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None


def _refresh_capabilities_if_needed(force: bool = False) -> None:
    now = time.time()
    if not force and (now - float(_CAPABILITY_CACHE.get("checked_at") or 0.0) < 120):
        return

    upscalers_data = _safe_get_json(f"{URL}/sdapi/v1/upscalers")
    scripts_data = _safe_get_json(f"{URL}/sdapi/v1/scripts")
    face_restorers_data = _safe_get_json(f"{URL}/sdapi/v1/face-restorers")
    controlnet_models_data = _safe_get_json(f"{URL}/controlnet/model_list")

    upscalers: List[str] = []
    if isinstance(upscalers_data, list):
        for item in upscalers_data:
            if isinstance(item, dict) and item.get("name"):
                upscalers.append(str(item["name"]))

    scripts_txt2img: List[str] = []
    if scripts_data and isinstance(scripts_data.get("txt2img"), list):
        scripts_txt2img = [str(x) for x in scripts_data["txt2img"] if x]

    face_restorers: List[str] = []
    if isinstance(face_restorers_data, list):
        for item in face_restorers_data:
            if isinstance(item, dict) and item.get("name"):
                face_restorers.append(str(item["name"]))

    controlnet_models: List[str] = []
    if controlnet_models_data and isinstance(controlnet_models_data.get("model_list"), list):
        controlnet_models = [str(x) for x in controlnet_models_data["model_list"] if x]

    _CAPABILITY_CACHE["upscalers"] = upscalers
    _CAPABILITY_CACHE["scripts_txt2img"] = scripts_txt2img
    _CAPABILITY_CACHE["face_restorers"] = face_restorers
    _CAPABILITY_CACHE["controlnet_models"] = controlnet_models
    _CAPABILITY_CACHE["checked_at"] = now


def _list_upscalers() -> List[str]:
    _refresh_capabilities_if_needed()
    return list(_CAPABILITY_CACHE.get("upscalers") or [])


def _list_txt2img_scripts() -> List[str]:
    _refresh_capabilities_if_needed()
    return list(_CAPABILITY_CACHE.get("scripts_txt2img") or [])


def _list_face_restorers() -> List[str]:
    _refresh_capabilities_if_needed()
    return list(_CAPABILITY_CACHE.get("face_restorers") or [])


def _list_controlnet_models() -> List[str]:
    _refresh_capabilities_if_needed()
    return list(_CAPABILITY_CACHE.get("controlnet_models") or [])


def _prompt_has_human_subject(prompt: str) -> bool:
    text = (prompt or "").lower()
    return any(keyword in text for keyword in HUMAN_PROMPT_KEYWORDS)


def _prompt_is_crowd_scene(prompt: str) -> bool:
    text = (prompt or "").lower()
    return any(keyword in text for keyword in CROWD_PROMPT_KEYWORDS)


def _pick_best_from_available(preferred_csv: str, available: List[str], fallback: str) -> str:
    if not available:
        return fallback

    preferred = [p.strip() for p in (preferred_csv or "").split(",") if p.strip()]
    candidates = preferred + ([fallback] if fallback else [])
    available_map = {x.lower(): x for x in available}

    for candidate in candidates:
        exact = available_map.get(candidate.lower())
        if exact:
            return exact
        for avail in available:
            if candidate.lower() in avail.lower():
                return avail

    return available[0]


def _pick_face_restorer() -> Optional[str]:
    if not SD_RESTORE_FACES:
        return None
    available = _list_face_restorers()
    if not available:
        return SD_FACE_RESTORATION_MODEL or None

    requested = (SD_FACE_RESTORATION_MODEL or "").strip()
    if requested:
        picked = _pick_best_from_available(requested, available, requested)
        if picked:
            return picked

    for preferred in ("GFPGAN", "CodeFormer"):
        picked = _pick_best_from_available(preferred, available, "")
        if picked:
            return picked

    return available[0] if available else None


def _pick_hr_upscaler(default_upscaler: str) -> str:
    if not SD_AUTO_BEST_HR_UPSCALER:
        return default_upscaler
    available = _list_upscalers()
    return _pick_best_from_available(SD_PREFERRED_HR_UPSCALERS, available, default_upscaler)


def _pick_post_upscaler() -> str:
    available = _list_upscalers()
    preferred = f"{SD_POST_UPSCALER},{SD_PREFERRED_HR_UPSCALERS}"
    return _pick_best_from_available(preferred, available, SD_POST_UPSCALER)


def _build_adetailer_alwayson(
    *,
    prompt_en: str,
    negative_prompt: str,
) -> Optional[Dict[str, Any]]:
    if not SD_ENABLE_ADDETAILER:
        return None
    if SD_ADDETAILER_HUMAN_ONLY and not _prompt_has_human_subject(prompt_en):
        return None
    if SD_ADDETAILER_SKIP_ON_CROWD and _prompt_is_crowd_scene(prompt_en):
        print(f"{YELLOW}ADetailer skipped for crowd scene to avoid long rerender loops.{RESET}")
        return None

    scripts = [x.lower() for x in _list_txt2img_scripts()]
    if "adetailer" not in scripts:
        return None

    face_args = {
        "ad_model": "face_yolov8n.pt",
        "ad_prompt": "",
        "ad_negative_prompt": negative_prompt,
        "ad_confidence": SD_ADDETAILER_CONFIDENCE,
        "ad_denoising_strength": 0.35,
        "ad_inpaint_only_masked": True,
        "ad_mask_blur": 4,
    }

    hand_args = {
        "ad_model": "hand_yolov8n.pt",
        "ad_prompt": "",
        "ad_negative_prompt": negative_prompt,
        "ad_confidence": max(0.2, SD_ADDETAILER_CONFIDENCE - 0.05),
        "ad_denoising_strength": 0.3,
        "ad_inpaint_only_masked": True,
        "ad_mask_blur": 4,
    }

    args: List[Any] = [True, False, face_args]
    if SD_ADDETAILER_ENABLE_HANDS:
        args.append(hand_args)

    return {"ADetailer": {"args": args}}


def _pick_controlnet_model_hint(keyword: str) -> str:
    models = _list_controlnet_models()
    for item in models:
        if keyword.lower() in item.lower():
            return item
    return ""


def _read_image_b64(image_path: str) -> Optional[str]:
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _build_controlnet_alwayson(control_image_path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not SD_ENABLE_CONTROLNET:
        return None
    if not control_image_path or not os.path.exists(control_image_path):
        return None

    scripts = [x.lower() for x in _list_txt2img_scripts()]
    if "controlnet" not in scripts:
        return None

    image_b64 = _read_image_b64(control_image_path)
    if not image_b64:
        return None

    canny_model = _pick_controlnet_model_hint("canny")
    depth_model = _pick_controlnet_model_hint("depth")
    if not canny_model and not depth_model:
        return None

    units: List[Dict[str, Any]] = []
    if canny_model:
        units.append(
            {
                "enabled": True,
                "module": "canny",
                "model": canny_model,
                "input_image": image_b64,
                "weight": SD_CONTROLNET_WEIGHT,
                "guidance_start": SD_CONTROLNET_GUIDANCE_START,
                "guidance_end": SD_CONTROLNET_GUIDANCE_END,
                "pixel_perfect": True,
                "resize_mode": "Crop and Resize",
            }
        )
    if depth_model:
        units.append(
            {
                "enabled": True,
                "module": "depth",
                "model": depth_model,
                "input_image": image_b64,
                "weight": max(0.35, SD_CONTROLNET_WEIGHT - 0.1),
                "guidance_start": SD_CONTROLNET_GUIDANCE_START,
                "guidance_end": SD_CONTROLNET_GUIDANCE_END,
                "pixel_perfect": True,
                "resize_mode": "Crop and Resize",
            }
        )

    if not units:
        return None
    return {"ControlNet": {"args": units}}


def _upscale_image_base64(img_base64: str, *, cancel_checker: Optional[Callable[[], bool]]) -> str:
    if not SD_ENABLE_POST_UPSCALE or SD_POST_UPSCALE_FACTOR <= 1.0:
        return img_base64

    if _is_cancelled(cancel_checker):
        return img_base64

    upscaler = _pick_post_upscaler()
    payload = {
        "image": img_base64,
        "resize_mode": 0,
        "upscaling_resize": SD_POST_UPSCALE_FACTOR,
        "upscaler_1": upscaler,
        "gfpgan_visibility": 0,
        "codeformer_visibility": 0,
        "codeformer_weight": 0,
    }
    try:
        response = _post_with_cancel(
            endpoint=f"{URL}/sdapi/v1/extra-single-image",
            payload=payload,
            timeout=120,
            cancel_checker=cancel_checker,
        )
        result = response.json()
        maybe_image = result.get("image") if isinstance(result, dict) else None
        if isinstance(maybe_image, str) and maybe_image.strip():
            return maybe_image
    except Exception as e:
        print(f"{YELLOW}Post-upscale skipped: {e}{RESET}")
    return img_base64


def _is_cancelled(cancel_checker: Optional[Callable[[], bool]]) -> bool:
    try:
        return bool(cancel_checker and cancel_checker())
    except Exception:
        return False


def _interrupt_sd_generation() -> None:
    try:
        requests.post(f"{URL}/sdapi/v1/interrupt", timeout=2)
    except Exception:
        pass


def _post_with_cancel(
    *,
    endpoint: str,
    payload: dict,
    timeout: int,
    cancel_checker: Optional[Callable[[], bool]],
):
    result = {}
    done = threading.Event()

    def _worker():
        try:
            response = requests.post(
                url=endpoint,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            result["response"] = response
        except Exception as e:
            result["error"] = e
        finally:
            done.set()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    while not done.wait(0.2):
        if _is_cancelled(cancel_checker):
            _interrupt_sd_generation()
            raise Exception("Cancelled during SD generation")

    if "error" in result:
        raise result["error"]
    return result["response"]


def resim_ciz(
    prompt_en: str,
    negative_prompt: Optional[str] = None,
    model_checkpoint: Optional[str] = None,
    control_image_path: Optional[str] = None,
    cancel_checker: Optional[Callable[[], bool]] = None,
    request_timeout: int = 300,
):
    """
    Send prompt directly to Stable Diffusion.
    Backward-compatible: old callers can still pass only prompt.
    """
    print(f"{GREEN}Prompt to draw:{RESET}")
    print(f"{GREEN}{prompt_en}{RESET}")

    prompt_en = _sanitize_prompt(prompt_en)
    prompt_en = _apply_quality_anchor(prompt_en)
    if not prompt_en:
        print(f"{RED}Generation Error: empty prompt.{RESET}")
        return False, None, None

    effective_negative = (negative_prompt or "").strip() or DEFAULT_NEGATIVE_PROMPT
    effective_checkpoint = (model_checkpoint or "").strip()

    print(f"SD RESOLUTION: {SD_WIDTH} x {SD_HEIGHT}")

    base_payload: Dict[str, Any] = {
        "prompt": prompt_en,
        "negative_prompt": effective_negative,
        "steps": SD_STEPS,
        "sampler_name": SD_SAMPLER,
        "width": SD_WIDTH,
        "height": SD_HEIGHT,
        "cfg_scale": SD_CFG_SCALE,
        "restore_faces": bool(SD_RESTORE_FACES),
        "tiling": False,
    }

    hr_upscaler = _pick_hr_upscaler(SD_HIRES_UPSCALER)
    if SD_ENABLE_HIRES_FIX:
        base_payload.update(
            {
                "enable_hr": True,
                "hr_scale": SD_HIRES_SCALE,
                "denoising_strength": SD_HIRES_DENOISE,
                "hr_second_pass_steps": max(8, SD_STEPS // 2),
                "hr_upscaler": hr_upscaler,
            }
        )
        print(f"{YELLOW}Using hires upscaler: {hr_upscaler}{RESET}")

    override_settings: Dict[str, Any] = {}
    if effective_checkpoint:
        override_settings["sd_model_checkpoint"] = effective_checkpoint
        print(f"{YELLOW}Using SD checkpoint override: {effective_checkpoint}{RESET}")

    face_restorer = _pick_face_restorer()
    if face_restorer:
        override_settings["face_restoration_model"] = face_restorer

    if override_settings:
        base_payload["override_settings"] = override_settings
        base_payload["override_settings_restore_afterwards"] = True

    enhanced_payload: Dict[str, Any] = dict(base_payload)
    alwayson_scripts: Dict[str, Any] = {}

    adetailer_script = _build_adetailer_alwayson(
        prompt_en=prompt_en,
        negative_prompt=effective_negative,
    )
    if adetailer_script:
        alwayson_scripts.update(adetailer_script)
        print(f"{YELLOW}ADetailer enabled for this prompt.{RESET}")

    controlnet_script = _build_controlnet_alwayson(control_image_path)
    if controlnet_script:
        alwayson_scripts.update(controlnet_script)
        print(f"{YELLOW}ControlNet enabled with control image.{RESET}")

    if alwayson_scripts:
        enhanced_payload["alwayson_scripts"] = alwayson_scripts

    try:
        print(f"{YELLOW}Starting generation...{RESET}")
        start_time = time.time()
        payloads_to_try: List[Dict[str, Any]] = [enhanced_payload]
        if enhanced_payload != base_payload:
            payloads_to_try.append(base_payload)

        last_error_text: Optional[str] = None
        for idx, payload in enumerate(payloads_to_try, start=1):
            enhanced_try = idx == 1 and enhanced_payload != base_payload
            try:
                response = _post_with_cancel(
                    endpoint=f"{URL}/sdapi/v1/txt2img",
                    payload=payload,
                    timeout=request_timeout,
                    cancel_checker=cancel_checker,
                )
                result = response.json()
            except Exception as e:
                last_error_text = str(e)
                if enhanced_try:
                    print(f"{YELLOW}Enhanced pass failed, retrying base payload: {e}{RESET}")
                    continue
                raise

            if "images" in result and len(result["images"]) > 0:
                image_base64 = result["images"][0]
                image_base64 = _upscale_image_base64(
                    image_base64,
                    cancel_checker=cancel_checker,
                )
                file_path = save_image_base64(image_base64)
                elapsed = time.time() - start_time
                print(f"{GREEN}Image saved: {file_path}{RESET}")
                print(f"{YELLOW}Duration: {elapsed:.2f} sec{RESET}")
                return True, file_path, prompt_en

            err_text = result.get("error") if isinstance(result, dict) else None
            if err_text:
                last_error_text = str(err_text)
                if enhanced_try:
                    print(f"{YELLOW}Enhanced payload error, retrying base payload: {err_text}{RESET}")
                    continue
                print(f"{RED}SD returned error: {err_text}{RESET}")

        if last_error_text:
            print(f"{RED}Generation failed: {last_error_text}{RESET}")
        return False, None, None

    except Exception as e:
        if "Cancelled during SD generation" in str(e):
            print(f"{YELLOW}Generation cancelled by user.{RESET}")
            return False, None, None
        print(f"{RED}Generation Error: {e}{RESET}")
        return False, None, None

import time
from typing import Any, Dict, List

from core.clients.llm import get_llm_service, unload_ollama
from core.clients.sd_client import resim_ciz
from core.content.caption_format import format_caption_hashtags_bottom
from core.content.daily_visual_agent import dunya_gundemini_getir

CAROUSEL_COUNT = 10

# Quality anchor for carousel prompts. Do not force camera/color sameness here.
CAROUSEL_QUALITY_ANCHOR = (
    "ultra-detailed photoreal image, clean rendering, cinematic clarity, natural material realism"
)

# Shared composition anchor: keeps subject identity consistent while allowing style variation.
CAROUSEL_COMPOSITION_ANCHOR = (
    "same exact subject identity, coherent visual continuity, no redesign"
)

# Data-driven subject profiles.
# New domains should be added here instead of writing new if/else branches.
SUBJECT_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "marine_animal",
        "keywords": [
            "sea turtle", "turtle", "ocean", "marine", "coast", "plastic", "pollution",
            "fish", "whale", "reef", "shore",
        ],
        "environment_anchor": "marine shoreline or ocean environment, visible pollution cues such as floating plastic debris",
        "subject_lock": "same species, same body proportions, same defining physical traits",
    },
    {
        "id": "space_rover",
        "keywords": ["mars", "rover", "space", "planet", "nasa", "lunar"],
        "environment_anchor": "martian or extra-planetary rocky terrain, realistic planetary atmosphere",
        "subject_lock": "same vehicle identity, same body silhouette, same instrument layout and mobility structure",
    },
    {
        "id": "automotive",
        "keywords": ["car", "tesla", "vehicle", "sedan", "automobile", "truck", "bike"],
        "environment_anchor": "real-world roadway or controlled automotive set aligned with topic context",
        "subject_lock": "same model identity, same body silhouette, same wheel count and key design lines",
    },
    {
        "id": "robot",
        "keywords": ["robot", "android", "humanoid", "machine", "ai-powered robot"],
        "environment_anchor": "urban city environment with streets, sidewalks, and realistic metropolitan context",
        "subject_lock": "same robot design identity, same head and torso form, same limb structure and proportions",
    },
    {
        "id": "human",
        "keywords": ["person", "human", "woman", "man", "child", "portrait", "face"],
        "environment_anchor": "environment directly relevant to the person's story context",
        "subject_lock": "same person identity, same facial structure, same recognizable appearance",
    },
]

DEFAULT_SUBJECT_PROFILE: Dict[str, str] = {
    "environment_anchor": "environment directly relevant to the topic and the subject",
    "subject_lock": "same defining identity traits and consistent recognizable form",
}

STYLE_PRESETS: List[Dict[str, str]] = [
    {
        "name": "Documentary",
        "signature": "documentary realism, natural daylight, true-to-life textures, candid field photography",
        "shot": "medium-wide eye-level shot, grounded perspective",
        "scene": "real-world native environment, natural imperfections, practical atmosphere",
        "palette": "earthy neutral tones",
    },
    {
        "name": "Noir",
        "signature": "noir cinematic look, monochrome high contrast, hard shadows, dramatic rim light",
        "shot": "low-angle hero shot with long shadow geometry",
        "scene": "nighttime environment relevant to the topic, sparse practical lights, optional wet reflections",
        "palette": "black, silver, desaturated highlights",
    },
    {
        "name": "Cyberpunk",
        "signature": "cyberpunk neon palette, cyan-magenta accents, wet reflective surface, atmospheric haze",
        "shot": "three-quarter perspective, dynamic leading lines",
        "scene": "futuristic reinterpretation of the same native environment, neon glow, reflective surfaces",
        "palette": "cyan, magenta, deep violet",
    },
    {
        "name": "Vintage Film",
        "signature": "1970s analog film aesthetic, warm grain, halation, slight lens softness",
        "shot": "nostalgic handheld framing, intimate distance",
        "scene": "period-correct version of the same environment, practical old-world details",
        "palette": "warm amber and muted olive",
    },
    {
        "name": "Editorial",
        "signature": "clean editorial photography, controlled lighting, premium product-story composition",
        "shot": "center-weighted composition, polished hero framing",
        "scene": "clean set inspired by the same environment, controlled reflections",
        "palette": "neutral gray with selective accent color",
    },
    {
        "name": "National Geographic",
        "signature": "epic environmental storytelling, expansive landscape detail, authentic expedition mood",
        "shot": "ultra-wide establishing shot, subject integrated with terrain scale",
        "scene": "wide environmental storytelling in the same native environment with strong sense of scale",
        "palette": "natural landscape color harmony",
    },
    {
        "name": "Minimalist",
        "signature": "minimalist visual language, restrained palette, strong negative space, geometric balance",
        "shot": "simple frontal framing with generous empty space",
        "scene": "same environment simplified to minimal visual elements and negative space",
        "palette": "two-tone restrained palette",
    },
    {
        "name": "Surreal Realism",
        "signature": "surreal realism, dreamlike atmosphere yet physically plausible materials and lighting",
        "shot": "poetic off-center framing with atmospheric depth",
        "scene": "unusual but believable reinterpretation of the same environment, cinematic fog and layered depth",
        "palette": "soft contrast, muted cinematic tones",
    },
    {
        "name": "Futurist",
        "signature": "futurist industrial aesthetic, sleek surfaces, precision geometry, advanced tech mood",
        "shot": "crisp angular composition, forward-driving perspective",
        "scene": "advanced high-tech reinterpretation of the same environment with structured light",
        "palette": "cool metallic tones with electric accents",
    },
    {
        "name": "Fine Art",
        "signature": "fine-art photography, museum-grade composition, expressive tonal contrast, elegant mood",
        "shot": "carefully balanced master shot with sculptural light",
        "scene": "timeless cinematic treatment of the same environment with painterly atmosphere",
        "palette": "controlled low-saturation art palette",
    },
]

CAROUSEL_NEGATIVE_PROMPT = (
    "cartoon, anime, illustration, painting, drawing, text, letters, typography, "
    "watermark, signature, logo, collage, split-screen, grid layout, meme, infographic, "
    "bad anatomy, deformed, low quality, blurry, noisy, overprocessed, plastic skin, "
    "multiple different subjects, subject identity drift, redesign, broken geometry, anatomy mutation"
)


def _clean_text(value: Any, max_len: int = 220) -> str:
    text = str(value or "").replace("\n", " ").strip().strip('"\'')
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def _fallback_topic(news: List[str]) -> str:
    if news:
        base = _clean_text(news[0], max_len=120)
        return f"Visual story inspired by: {base}"
    return "Future of Human Technology"


def _build_plan_prompt(news_lines: str) -> str:
    return (
        "You are a senior visual strategist for an Instagram carousel.\n"
        "Here are today's headlines:\n"
        f"{news_lines}\n\n"
        "TASK:\n"
        "Pick ONE topic and define ONE main subject that can be rendered in 10 different visual styles.\n"
        "The subject must stay recognizable across all slides.\n\n"
        "Constraints:\n"
        "- Topic must be visual and concrete.\n"
        "- Main subject must remain constant across all 10 slides.\n"
        "- Define one narrative curve (e.g. calm->intense->resolved).\n"
        "- Avoid politics, war, sexual content, explicit violence.\n"
    )


def _style_guide_text() -> str:
    lines = []
    for idx, item in enumerate(STYLE_PRESETS, start=1):
        lines.append(
            f"{idx}. {item['name']}: {item['signature']} | shot: {item['shot']} | "
            f"scene: {item['scene']} | palette: {item['palette']}"
        )
    return "\n".join(lines)


def _build_slides_prompt(topic: str, subject_anchor: str, narrative_curve: str) -> str:
    return (
        f"TOPIC: {topic}\n"
        f"MAIN SUBJECT (must stay constant): {subject_anchor}\n"
        f"NARRATIVE CURVE: {narrative_curve}\n"
        f"COMPOSITION ANCHOR (must stay constant): {CAROUSEL_COMPOSITION_ANCHOR}\n"
        f"GLOBAL QUALITY ANCHOR: {CAROUSEL_QUALITY_ANCHOR}\n\n"
        "You must create EXACTLY 10 slides.\n"
        "Use this fixed style order, one style per slide:\n"
        f"{_style_guide_text()}\n\n"
        "Rules:\n"
        "1. Keep the same main subject in every slide.\n"
        "2. Keep composition anchor consistent across slides.\n"
        "3. Change visual style strongly (per ordered list) while preserving same subject identity.\n"
        "4. No text overlays, no logos, no typography.\n"
        "5. Prompts must be photoreal scene prompts, not abstract buzzwords.\n"
    )


def _resolve_subject_profile(topic: str, subject_anchor: str) -> Dict[str, str]:
    text = f"{topic} {subject_anchor}".lower()
    best_profile: Dict[str, Any] | None = None
    best_score = 0

    for profile in SUBJECT_PROFILES:
        keywords = profile.get("keywords", [])
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_profile = profile
            best_score = score

    if best_profile:
        return {
            "environment_anchor": best_profile["environment_anchor"],
            "subject_lock": best_profile["subject_lock"],
        }
    return DEFAULT_SUBJECT_PROFILE


def _compose_slide_prompt(
    *,
    idx: int,
    topic: str,
    subject_anchor: str,
    llm_hint: str = "",
) -> str:
    stage = idx + 1
    style = STYLE_PRESETS[idx]
    profile = _resolve_subject_profile(topic, subject_anchor)
    env_anchor = profile["environment_anchor"]
    subject_lock = profile["subject_lock"]
    hint = _clean_text(llm_hint, max_len=240)
    hint_part = f", scene detail: {hint}" if hint else ""

    return (
        f"stage {stage}/{CAROUSEL_COUNT}, "
        f"same exact main subject: {subject_anchor}, "
        f"{CAROUSEL_COMPOSITION_ANCHOR}, "
        f"subject lock: {subject_lock}, "
        f"environment anchor: {env_anchor}, "
        f"style: {style['signature']}, "
        f"camera: {style['shot']}, "
        f"scene lock: {style['scene']}, "
        f"color palette lock: {style['palette']}, "
        f"topic context: {topic}, "
        f"{CAROUSEL_QUALITY_ANCHOR}, "
        "single subject focus, "
        "high-detail photoreal render, physically coherent scene, avoid repeating previous slide composition"
        f"{hint_part}, no text, no watermark, no logo"
    )


def _fallback_slide(topic: str, subject_anchor: str, idx: int) -> Dict[str, str]:
    stage = idx + 1
    style_name = STYLE_PRESETS[idx]["name"]
    prompt = _compose_slide_prompt(
        idx=idx,
        topic=topic,
        subject_anchor=subject_anchor,
    )
    return {"title": f"{stage}. {style_name}", "prompt": prompt}


def _normalize_slides(
    raw_slides: List[Any],
    *,
    topic: str,
    subject_anchor: str,
) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []

    for i in range(CAROUSEL_COUNT):
        style_name = STYLE_PRESETS[i]["name"]
        item = raw_slides[i] if i < len(raw_slides) else {}

        if isinstance(item, dict):
            title = _clean_text(item.get("title") or f"{i+1}. {style_name}", max_len=48)
        else:
            title = f"{i+1}. {style_name}"

        prompt = _compose_slide_prompt(
            idx=i,
            topic=topic,
            subject_anchor=subject_anchor,
            llm_hint="",
        )

        normalized.append({"title": title or f"{i+1}. {style_name}", "prompt": prompt})

    return normalized


def generate_carousel_content(log_callback=print):
    """
    1. Haberleri tarar.
    2. Tek konu + tek sabit ana ozne secer.
    3. Ayni ozneyi 10 farkli tarzda promptlar.
    4. 10 gorseli sirayla cizer.
    """

    log_callback("Global gundem taraniyor (Carousel)...")
    raw_news = dunya_gundemini_getir(limit=100)

    if not raw_news:
        return False, None, "Haber bulunamadi"

    if not isinstance(raw_news, list):
        try:
            raw_news = list(raw_news)
        except Exception:
            return False, None, f"Veri hatasi: {type(raw_news)}"

    news_slice = [f"- {_clean_text(x, max_len=220)}" for x in raw_news[:50] if _clean_text(x)]
    news_lines = "\n".join(news_slice)

    llm = get_llm_service()

    log_callback("Carousel icin konu ve ana ozne seciliyor...")
    plan_schema = {
        "topic": "string",
        "subject_anchor": "string",
        "narrative_curve": "string",
    }

    try:
        plan = llm.generate_response(_build_plan_prompt(news_lines), schema=plan_schema)
    except Exception as e:
        log_callback(f"Plan uretimi fallback: {e}")
        plan = {}

    topic = _clean_text(plan.get("topic") or _fallback_topic(raw_news), max_len=140)
    subject_anchor = _clean_text(
        plan.get("subject_anchor") or f"one consistent scene representing {topic}",
        max_len=180,
    )
    narrative_curve = _clean_text(plan.get("narrative_curve") or "calm to intense to resolved", max_len=120)

    log_callback(f"Secilen konu: {topic}")
    log_callback(f"Sabit ozne: {subject_anchor}")
    log_callback("Tarz listesi: " + ", ".join([s["name"] for s in STYLE_PRESETS]))

    log_callback("10 farkli tarz icin promptlar uretiliyor...")
    slides_schema = {
        "caption": "string",
        "hashtags": "string",
        "slides": [
            {
                "style_name": "string",
                "title": "string",
                "prompt": "string",
            }
        ],
    }

    try:
        slide_data = llm.generate_response(
            _build_slides_prompt(topic, subject_anchor, narrative_curve),
            schema=slides_schema,
        )
    except Exception as e:
        log_callback(f"Prompt uretimi fallback: {e}")
        slide_data = {}

    raw_slides = slide_data.get("slides", []) if isinstance(slide_data, dict) else []
    parsed_slides = _normalize_slides(
        raw_slides,
        topic=topic,
        subject_anchor=subject_anchor,
    )

    caption = format_caption_hashtags_bottom(
        _clean_text(slide_data.get("caption", ""), max_len=800),
        _clean_text(slide_data.get("hashtags", ""), max_len=400),
    )
    if not caption:
        caption = format_caption_hashtags_bottom(
            f"Ayni konu, 10 farkli tarz. Sence en iyi slide hangisi?",
            "#ai #carousel #digitalart #visualstory #stablediffusion",
        )

    unload_ollama()
    time.sleep(1.5)

    generated_images = []
    log_callback(f"Toplam {CAROUSEL_COUNT} gorsel cizilecek. Baslaniyor...")

    for i, slide in enumerate(parsed_slides):
        current_num = i + 1
        prompt = slide["prompt"]
        slide_title = slide["title"]

        log_callback(f"LAYER_UPDATE:[{slide_title}] Gorsel {current_num}/{CAROUSEL_COUNT} ciziliyor...")

        success = False
        retry_count = 0
        file_path = None

        while not success and retry_count < 2:
            s, path, _ = resim_ciz(
                prompt,
                negative_prompt=CAROUSEL_NEGATIVE_PROMPT,
            )
            if s:
                success = True
                file_path = path
            else:
                retry_count += 1
                log_callback(f"Cizim hatasi, tekrar deneniyor ({retry_count})...")
                time.sleep(1)

        if success and file_path:
            generated_images.append(
                {
                    "path": file_path,
                    "prompt": prompt,
                    "title": slide_title,
                    "style_index": current_num,
                }
            )
            log_callback(f"{current_num}. gorsel hazir. ({slide_title})")
        else:
            log_callback(f"{current_num}. gorsel cizilemedi.")

        if current_num < CAROUSEL_COUNT:
            log_callback("Sistem sogutuluyor (5 sn)...")
            time.sleep(5)

    if not generated_images:
        return False, None, "Hicbir gorsel olusturulamadi"

    return True, generated_images, caption

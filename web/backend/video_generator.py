import datetime
import os
import re
import subprocess
import textwrap
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

from core.clients.llm import get_llm_service, unload_ollama
from core.clients.sd_client import resim_ciz
from core.content.news_fetcher import get_top_3_separate_news
from core.content.news_memory import mark_used_titles
from core.runtime.config import SD_HEIGHT, SD_WIDTH
from core.runtime.tts_config import (
    PIPER_BIN,
    PIPER_CONFIG,
    PIPER_EN_CONFIG,
    PIPER_EN_MODEL,
    PIPER_MODEL,
)

TARGET_NEWS_COUNT = 3
SCRIPT_WORD_MIN = 24
SCRIPT_WORD_MAX = 34
TARGET_TOTAL_SECONDS = 36
VIDEO_TTS_LENGTH_SCALE = "1.02"

VIDEO_NEGATIVE_PROMPT = (
    "text, letters, logo, watermark, signature, collage, split image, split screen, multi-panel, "
    "phone screen, ui overlay, subtitles, cartoon, anime, illustration, painting, 3d render, "
    "close-up portrait, extreme close-up face, distorted face, asymmetrical eyes, bad anatomy, "
    "deformed hands, extra fingers, fused fingers, low quality, blurry, pixelated"
)


def _report(progress_callback, task: str, percent: int) -> None:
    payload = {
        "task": task,
        "percent": max(0, min(100, int(percent))),
    }
    try:
        progress_callback(payload)
    except TypeError:
        # Backward compatibility for legacy callback signatures.
        progress_callback(task)


def _resolve_video_tts_paths() -> Tuple[str, str, str]:
    """
    Resolve TTS model for video narration.
    Priority:
    1) VIDEO_PIPER_MODEL/VIDEO_PIPER_CONFIG env overrides
    2) English Piper model
    3) Turkish model fallback (last resort)
    """
    model_override = os.environ.get("VIDEO_PIPER_MODEL", "").strip()
    config_override = os.environ.get("VIDEO_PIPER_CONFIG", "").strip()
    if model_override and config_override and os.path.exists(model_override) and os.path.exists(config_override):
        return model_override, config_override, "override"

    if os.path.exists(PIPER_EN_MODEL) and os.path.exists(PIPER_EN_CONFIG):
        return PIPER_EN_MODEL, PIPER_EN_CONFIG, "english"

    if os.path.exists(PIPER_MODEL) and os.path.exists(PIPER_CONFIG):
        return PIPER_MODEL, PIPER_CONFIG, "fallback_turkish"

    return PIPER_EN_MODEL, PIPER_EN_CONFIG, "missing"


def _enforce_word_window(text: str, min_words: int, max_words: int, fallback_headline: str) -> str:
    cleaned = sanitize_text(text)
    words = cleaned.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]).rstrip(" ,.")
    if len(words) >= min_words:
        return cleaned

    fallback = (
        f"Breaking update: {fallback_headline}. Officials are sharing new details, "
        "and analysts say the next few hours will shape the global response."
    )
    fallback_words = sanitize_text(fallback).split()
    return " ".join(fallback_words[:max_words])


def generate_news_script(news_title: str) -> str:
    prompt = (
        "You are a TV news anchor writing narration for a short 3-part news video.\n"
        f"Headline: '{news_title}'\n\n"
        "Rules:\n"
        "- Language: English only.\n"
        f"- Length: {SCRIPT_WORD_MIN}-{SCRIPT_WORD_MAX} words.\n"
        "- Keep it factual and clear.\n"
        "- Mention what happened and why it matters.\n"
        "- Maximum 2 short sentences.\n"
        "- No hashtags, no emojis, no list markers.\n"
        "Output only the narration text."
    )

    try:
        text = get_llm_service().ask(
            prompt,
            system="You are an English TV news anchor. Write concise spoken narration.",
            timeout=60,
            retries=1,
        )
        return _enforce_word_window(text, SCRIPT_WORD_MIN, SCRIPT_WORD_MAX, news_title)
    except Exception as e:
        print(f"Script generation error: {e}")
        return _enforce_word_window("", SCRIPT_WORD_MIN, SCRIPT_WORD_MAX, news_title)


def generate_visual_prompt(news_title: str) -> str:
    prompt = (
        "Create a high-end cinematic photorealistic image prompt for this news headline:\n"
        f"'{news_title}'\n\n"
        "Style: documentary realism, award-winning photography, detailed, dramatic but natural lighting.\n"
        "Rules:\n"
        "- Keep a single coherent scene.\n"
        "- Prefer medium or wide shot.\n"
        "- Avoid close-up faces and avoid crowded foreground people.\n"
        "- Avoid any phone screen, UI overlays, text in-frame, or split composition.\n"
        "- No logos or watermarks.\n"
        "Output only one English prompt."
    )
    try:
        raw = get_llm_service().ask_english(prompt, timeout=60, retries=1)
        cleaned = sanitize_text(raw)
        if len(cleaned) < 40:
            raise ValueError("Prompt too short")
        banned_terms = ("phone", "smartphone", "screen", "selfie", "close-up", "close up")
        if any(term in cleaned.lower() for term in banned_terms):
            raise ValueError("Prompt contains banned composition terms")
        if "single coherent scene" not in cleaned.lower():
            cleaned += ", single coherent scene, medium-wide shot, documentary realism"
        if "no text" not in cleaned.lower():
            cleaned += ", no text, no watermark, no logo"
        return cleaned
    except Exception as e:
        print(f"Visual prompt generation error: {e}")
        return (
            f"A cinematic documentary scene inspired by '{news_title}', single coherent composition, "
            "medium-wide shot, natural lighting, realistic materials, balanced exposure, "
            "no text, no watermark, no logo"
        )


def sanitize_text(text: str) -> str:
    # Keep printable chars and normalize whitespace.
    text = "".join(ch for ch in str(text or "") if ch.isprintable())
    text = text.replace("\n", " ").replace("\r", " ")
    # English-safe whitelist for Piper narration.
    text = re.sub(r"[^a-zA-Z0-9\s\.,!\?'\-:]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _format_subtitle_text(text: str, line_chars: int = 42) -> str:
    clean = sanitize_text(text)
    if not clean:
        return ""
    return textwrap.fill(clean, width=line_chars)


def _ffmpeg_escape_path(path: Path) -> str:
    # drawtext parser expects escaped ':' on Windows paths.
    raw = path.resolve().as_posix()
    raw = raw.replace(":", r"\:")
    raw = raw.replace("'", r"\'")
    return raw


def _resolve_subtitle_font_path() -> Optional[Path]:
    candidates = [
        Path(os.environ.get("VIDEO_SUBTITLE_FONT", "")).expanduser() if os.environ.get("VIDEO_SUBTITLE_FONT") else None,
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    for cand in candidates:
        if cand and cand.exists():
            return cand
    return None


def _write_subtitle_text_file(text: str, temp_dir: Path) -> Optional[Path]:
    wrapped = _format_subtitle_text(text)
    if not wrapped:
        return None
    path = temp_dir / f"subtitle_{uuid.uuid4()}.txt"
    path.write_text(wrapped, encoding="utf-8")
    return path


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000.0)))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _split_subtitle_chunks(text: str, words_per_chunk: int = 6):
    words = sanitize_text(text).split()
    if not words:
        return []
    chunk_size = max(2, min(6, int(words_per_chunk)))
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


def _write_timed_subtitle_srt(text: str, duration_seconds: float, temp_dir: Path) -> Optional[Path]:
    chunks = _split_subtitle_chunks(text, words_per_chunk=6)
    if not chunks:
        return None

    # Evenly spread subtitle chunks across clip audio duration.
    duration = max(float(duration_seconds or 0.0), len(chunks) * 0.9)
    step = duration / max(1, len(chunks))

    lines = []
    for i, chunk in enumerate(chunks, start=1):
        start_s = (i - 1) * step
        end_s = duration if i == len(chunks) else i * step
        if (end_s - start_s) < 0.35:
            end_s = start_s + 0.35
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(start_s)} --> {_format_srt_timestamp(end_s)}")
        lines.append(chunk)
        lines.append("")

    path = temp_dir / f"subtitle_{uuid.uuid4()}.srt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _build_ass_subtitle_filter(subtitle_file: Optional[Path], frame_height: int) -> str:
    if not subtitle_file or not subtitle_file.exists():
        return ""
    file_esc = _ffmpeg_escape_path(subtitle_file)
    fontsize = max(26, int(frame_height * 0.055))
    margin_v = max(28, int(frame_height * 0.045))
    style = (
        f"FontName=Arial,FontSize={fontsize},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BackColour=&H00000000,BorderStyle=1,"
        f"Outline=2,Shadow=1,Alignment=2,MarginV={margin_v},WrapStyle=2"
    )
    style = style.replace("'", r"\'")
    return f"subtitles='{file_esc}':force_style='{style}'"


def _build_subtitle_drawtext_filter(subtitle_file: Optional[Path], frame_height: int) -> str:
    if not subtitle_file or not subtitle_file.exists():
        return ""
    textfile_esc = _ffmpeg_escape_path(subtitle_file)
    font_file = _resolve_subtitle_font_path()
    font_part = ""
    if font_file:
        font_part = f"fontfile='{_ffmpeg_escape_path(font_file)}':"

    return (
        f"drawtext={font_part}textfile='{textfile_esc}':"
        "x=(w-text_w)/2:y=h-text_h-42:"
        "fontsize=36:fontcolor=white:"
        "line_spacing=8:borderw=2:bordercolor=black:"
        "box=0"
    )


def generate_audio(text: str, output_path: Path, *, model_path: str, config_path: str) -> bool:
    text = sanitize_text(text)
    if not text:
        return False

    # Soft clamp to keep each segment around 10-14 seconds.
    words = text.split()
    if len(words) > SCRIPT_WORD_MAX:
        text = " ".join(words[:SCRIPT_WORD_MAX])

    cmd = [
        PIPER_BIN,
        "-m",
        model_path,
        "-c",
        config_path,
        "-f",
        str(output_path),
        "--length-scale",
        VIDEO_TTS_LENGTH_SCALE,
    ]

    try:
        result = subprocess.run(
            cmd,
            input=text,
            text=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            print(f"Piper error (code {result.returncode}): {result.stderr}")
            return False
        return os.path.exists(output_path)
    except Exception as e:
        print(f"Audio generation error: {e}")
        return False


def get_media_duration_seconds(media_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return 0.0
        return float((result.stdout or "0").strip())
    except Exception:
        return 0.0


def create_video_clip_ffmpeg(
    image_path: str,
    audio_path: Path,
    output_path: Path,
    temp_dir: Path,
    subtitle_text: Optional[str] = None,
) -> bool:
    side = min(int(SD_WIDTH), int(SD_HEIGHT))
    width = side
    height = side
    base_vf_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )

    subtitle_files = []
    subtitle_mode = "none"
    audio_seconds = get_media_duration_seconds(audio_path)

    timed_subtitle_file = _write_timed_subtitle_srt(subtitle_text or "", audio_seconds, temp_dir)
    if timed_subtitle_file:
        subtitle_files.append(timed_subtitle_file)
    subtitle_filter = _build_ass_subtitle_filter(timed_subtitle_file, height)
    if subtitle_filter:
        subtitle_mode = "ass"
    else:
        static_subtitle_file = _write_subtitle_text_file(subtitle_text or "", temp_dir)
        if static_subtitle_file:
            subtitle_files.append(static_subtitle_file)
        subtitle_filter = _build_subtitle_drawtext_filter(static_subtitle_file, height)
        if subtitle_filter:
            subtitle_mode = "drawtext"

    vf_filter = f"{base_vf_filter},{subtitle_filter}" if subtitle_filter else base_vf_filter

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-vf",
        vf_filter,
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(output_path):
        for sf in subtitle_files:
            if sf and sf.exists():
                try:
                    sf.unlink()
                except Exception:
                    pass
        return True

    # If timed subtitles fail, retry with static drawtext subtitles.
    if subtitle_mode == "ass":
        static_subtitle_file = _write_subtitle_text_file(subtitle_text or "", temp_dir)
        static_filter = _build_subtitle_drawtext_filter(static_subtitle_file, height)
        if static_subtitle_file:
            subtitle_files.append(static_subtitle_file)
        if static_filter:
            static_cmd = cmd[:]
            vf_idx = static_cmd.index("-vf") + 1
            static_cmd[vf_idx] = f"{base_vf_filter},{static_filter}"
            static_result = subprocess.run(static_cmd, capture_output=True, text=True)
            if static_result.returncode == 0 and os.path.exists(output_path):
                for sf in subtitle_files:
                    if sf and sf.exists():
                        try:
                            sf.unlink()
                        except Exception:
                            pass
                print(
                    f"Timed subtitles failed, static subtitles used. Error: {result.stderr}"
                )
                return True

    # If subtitles fail, retry once without subtitle filter.
    if subtitle_filter:
        fallback_cmd = cmd[:]
        vf_idx = fallback_cmd.index("-vf") + 1
        fallback_cmd[vf_idx] = base_vf_filter
        fallback_result = subprocess.run(fallback_cmd, capture_output=True, text=True)
        for sf in subtitle_files:
            if sf and sf.exists():
                try:
                    sf.unlink()
                except Exception:
                    pass
        if fallback_result.returncode == 0 and os.path.exists(output_path):
            print(
                f"Subtitle render failed, fallback clip generated without subtitles. Error: {result.stderr}"
            )
            return True

        print(f"FFmpeg clip error: {fallback_result.stderr or result.stderr}")
        return False

    print(f"FFmpeg clip error: {result.stderr}")
    return False


def concat_videos_ffmpeg(video_paths, output_path: Path) -> bool:
    list_file = output_path.parent / "list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for path in video_paths:
            abs_path = path.resolve().as_posix()
            f.write(f"file '{abs_path}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg concat error: {result.stderr}")
    try:
        os.remove(list_file)
    except Exception:
        pass
    return os.path.exists(output_path)


def process_daily_news_video(progress_callback=print):
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)

    today_str = datetime.date.today().isoformat()
    videos_dir = Path("generated_videos") / today_str
    videos_dir.mkdir(parents=True, exist_ok=True)

    _report(progress_callback, "Collecting top headlines...", 4)
    news_items = get_top_3_separate_news()
    if not news_items:
        return False, "No news found."

    news_items = list(news_items)[:TARGET_NEWS_COUNT]
    mark_used_titles(news_items, source="video")

    tts_model_path, tts_config_path, tts_mode = _resolve_video_tts_paths()
    if tts_mode in {"missing", "fallback_turkish"}:
        return (
            False,
            "English Piper model not found. Install en_US-lessac-medium model first.",
        )
    _report(progress_callback, "Using English voice model for narration.", 8)

    scripts = []
    prompts = []
    for i, news in enumerate(news_items):
        idx = i + 1
        prep_percent = 10 + int((idx / max(1, len(news_items))) * 18)
        _report(progress_callback, f"Writing script and prompt {idx}/{len(news_items)}...", prep_percent)
        scripts.append(generate_news_script(news))
        prompts.append(generate_visual_prompt(news))

    _report(progress_callback, "Releasing LLM memory...", 30)
    unload_ollama()
    time.sleep(1.5)

    clip_paths = []
    total_audio_seconds = 0.0

    for i, news in enumerate(news_items):
        idx = i + 1
        base = 32 + (i * 20)

        _report(progress_callback, f"Generating audio {idx}/{len(news_items)}...", base + 2)
        audio_path = temp_dir / f"news_audio_{uuid.uuid4()}.wav"
        audio_ok = generate_audio(
            scripts[i],
            audio_path,
            model_path=tts_model_path,
            config_path=tts_config_path,
        )
        if not audio_ok:
            _report(progress_callback, f"Audio failed for item {idx}. Skipping.", base + 6)
            continue

        audio_seconds = get_media_duration_seconds(audio_path)
        total_audio_seconds += audio_seconds

        _report(progress_callback, f"Generating image {idx}/{len(news_items)}...", base + 8)
        success, image_path, _ = resim_ciz(
            prompts[i],
            negative_prompt=VIDEO_NEGATIVE_PROMPT,
        )
        if not success or not image_path:
            _report(progress_callback, f"Image failed for item {idx}.", base + 12)
            continue

        _report(progress_callback, f"Building clip {idx}/{len(news_items)}...", base + 15)
        clip_path = temp_dir / f"clip_{uuid.uuid4()}.mp4"
        if create_video_clip_ffmpeg(
            image_path,
            audio_path,
            clip_path,
            temp_dir=temp_dir,
            subtitle_text=scripts[i],
        ):
            clip_paths.append(clip_path)
            _report(progress_callback, f"Clip {idx}/{len(news_items)} ready.", base + 19)

    if not clip_paths:
        return False, "No clips generated."

    _report(progress_callback, "Merging clips...", 92)
    final_filename = f"news_video_{uuid.uuid4()}.mp4"
    final_path = videos_dir / final_filename
    ok = concat_videos_ffmpeg(clip_paths, final_path)

    if not ok:
        return False, "Video merge failed."

    final_seconds = get_media_duration_seconds(final_path)
    if final_seconds <= 0:
        final_seconds = total_audio_seconds
    _report(
        progress_callback,
        f"Video complete. Duration: {final_seconds:.1f}s (target ~{TARGET_TOTAL_SECONDS}s).",
        100,
    )
    return True, str(final_path)

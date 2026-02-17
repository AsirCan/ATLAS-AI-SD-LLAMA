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
    "bad proportions, deformed, ugly, malformed limbs, disfigured hands, poorly drawn face, "
    "cloned face, unnatural skin, fake, cgi look, plastic looking, "
    "deformed hands, extra fingers, missing fingers, fused fingers, extra limbs, "
    "low quality, blurry, pixelated, worst quality, low resolution, overexposed, underexposed"
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
        "- STRONGLY prefer wide-angle or medium-wide environmental shots.\n"
        "- Do NOT include any human faces, people portraits, or close-up of any person.\n"
        "- Show locations, objects, architecture, landscapes, or symbolic elements instead of people.\n"
        "- If people must appear, show them from behind, far away, or as silhouettes only.\n"
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


def _format_ass_timestamp(seconds: float) -> str:
    """Format seconds to ASS timestamp: H:MM:SS.cc (centiseconds)."""
    total_cs = max(0, int(round(float(seconds) * 100.0)))
    hours = total_cs // 360_000
    minutes = (total_cs % 360_000) // 6_000
    secs = (total_cs % 6_000) // 100
    cs = total_cs % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _split_subtitle_chunks(text: str, words_per_chunk: int = 4):
    words = sanitize_text(text).split()
    if not words:
        return []
    chunk_size = max(2, min(6, int(words_per_chunk)))
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


# ---------------------------------------------------------------------------
# Whisper forced-alignment for accurate word-level subtitle timing
# ---------------------------------------------------------------------------

_whisper_model = None


def _get_whisper_model():
    """Lazy-load the faster_whisper tiny model (39 MB, very fast)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    try:
        from faster_whisper import WhisperModel  # noqa: E402

        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[Subtitle] Whisper tiny model loaded for subtitle alignment.")
        return _whisper_model
    except Exception as e:
        print(f"[Subtitle] Whisper model load failed: {e}")
        return None


def _get_word_timestamps(audio_path: Path):
    """
    Use faster_whisper to extract word-level timestamps from a WAV file.
    Returns list of (start, end, word) tuples, or None on failure.
    """
    model = _get_whisper_model()
    if model is None:
        return None
    try:
        segments, _ = model.transcribe(
            str(audio_path),
            language="en",
            word_timestamps=True,
            vad_filter=False,
        )
        words = []
        for segment in segments:
            if segment.words:
                for w in segment.words:
                    words.append((w.start, w.end, w.word.strip()))
        if not words:
            return None
        return words
    except Exception as e:
        print(f"[Subtitle] Whisper transcription failed: {e}")
        return None


def _group_words_into_chunks(word_timestamps, words_per_chunk: int = 4):
    """
    Group word-level timestamps into subtitle chunks using smart phrase
    boundaries rather than a fixed word count.  Prefers to split after
    punctuation (comma, period, colon, semicolon) and before conjunctions
    or clause-starting prepositions.  Target chunk size is 3-6 words.
    """
    if not word_timestamps:
        return []

    MIN_CHUNK = 3
    MAX_CHUNK = 6

    # Tokens that signal a natural break *before* them
    BREAK_BEFORE = {
        "and", "but", "or", "so", "yet", "while", "as", "that", "which",
        "where", "when", "who", "because", "although", "however",
        "in", "on", "at", "for", "with", "from", "to", "by",
        "about", "after", "before", "during", "over", "under",
    }

    chunks = []
    buf = []  # accumulate (start, end, word)
    for ts in word_timestamps:
        word = ts[2]
        # Should we break *before* this word?
        if len(buf) >= MIN_CHUNK:
            prev_word = buf[-1][2] if buf else ""
            # Break after punctuation at end of previous word
            if prev_word and prev_word[-1] in ".,;:!?":
                chunks.append(_flush_chunk(buf))
                buf = []
            # Break before a conjunction / clause-starting preposition
            elif word.lower().rstrip(".,;:!?") in BREAK_BEFORE:
                chunks.append(_flush_chunk(buf))
                buf = []
        # Hard cutoff at MAX_CHUNK
        if len(buf) >= MAX_CHUNK:
            chunks.append(_flush_chunk(buf))
            buf = []
        buf.append(ts)

    if buf:
        # Merge tiny remainder into previous chunk if it makes sense
        if chunks and len(buf) < MIN_CHUNK:
            prev_start, _, prev_text = chunks[-1]
            merged_text = prev_text + " " + " ".join(w[2] for w in buf)
            chunks[-1] = (prev_start, buf[-1][1], merged_text)
        else:
            chunks.append(_flush_chunk(buf))

    return chunks


def _flush_chunk(buf):
    """Helper: convert a word-timestamp buffer into a (start, end, text) tuple."""
    start = buf[0][0]
    end = buf[-1][1]
    text = " ".join(w[2] for w in buf)
    return (start, end, text)


def _build_ass_header(frame_width: int, frame_height: int) -> str:
    """Build ASS file header with embedded styling."""
    fontsize = max(18, int(frame_height * 0.042))
    margin_v = max(20, int(frame_height * 0.04))
    margin_h = max(20, int(frame_width * 0.06))
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {frame_width}\n"
        f"PlayResY: {frame_height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{fontsize},"
        "&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,2,1,2,{margin_h},{margin_h},{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _write_timed_subtitle_ass(
    text: str,
    duration_seconds: float,
    frame_width: int,
    frame_height: int,
    temp_dir: Path,
    audio_path: Optional[Path] = None,
) -> Optional[Path]:
    """
    Generate a native ASS subtitle file.
    Strategy:
      1) If audio_path is given, use Whisper forced-alignment for exact timing.
      2) Fallback to proportional math timing if Whisper fails.
    """
    clean_text = sanitize_text(text)
    if not clean_text:
        return None

    header = _build_ass_header(frame_width, frame_height)
    events = []

    # --- Strategy 1: Whisper forced-alignment (professional) ---
    whisper_ok = False
    if audio_path and audio_path.exists():
        word_ts = _get_word_timestamps(audio_path)
        if word_ts:
            chunks = _group_words_into_chunks(word_ts, words_per_chunk=4)
            if chunks:
                # Professional padding: show subtitle slightly before speech
                # starts and keep it slightly after speech ends.
                PRE_PAD = 0.08   # seconds before first word
                POST_PAD = 0.12  # seconds after last word
                duration = max(float(duration_seconds or 0.0), 1.0)
                padded = []
                for start_s, end_s, chunk_text in chunks:
                    s = max(0.0, start_s - PRE_PAD)
                    e = min(duration, end_s + POST_PAD)
                    padded.append((s, e, chunk_text))
                
                # Clamp overlaps: PRIORITIZE NEXT START.
                # If current chunk ends after next chunk starts, trim current chunk.
                # Do NOT delay the start of the next chunk.
                for idx in range(len(padded) - 1):
                    curr_end = padded[idx][1]
                    next_start = padded[idx + 1][0]
                    if curr_end > next_start:
                        # Overlap! Trim current end to match next start
                        padded[idx] = (padded[idx][0], next_start, padded[idx][2])
                for start_s, end_s, chunk_text in padded:
                    t_start = _format_ass_timestamp(start_s)
                    t_end = _format_ass_timestamp(end_s)
                    events.append(
                        f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{chunk_text}"
                    )
                whisper_ok = True
                print(f"[Subtitle] Whisper alignment OK: {len(padded)} chunks.")

    # --- Strategy 2: Proportional math fallback ---
    if not whisper_ok:
        print("[Subtitle] Using proportional timing fallback.")
        chunks = _split_subtitle_chunks(text, words_per_chunk=4)
        if not chunks:
            return None
        duration = max(float(duration_seconds or 0.0), len(chunks) * 0.8)
        gap = 0.05
        usable = duration - gap * max(0, len(chunks) - 1)
        usable = max(usable, len(chunks) * 0.5)
        word_counts = [len(ch.split()) for ch in chunks]
        total_words = max(1, sum(word_counts))
        cursor = 0.0
        for i, chunk in enumerate(chunks):
            proportion = word_counts[i] / total_words
            chunk_dur = max(0.6, usable * proportion)
            start_s = cursor
            end_s = start_s + chunk_dur
            if i == len(chunks) - 1:
                end_s = duration
            t_start = _format_ass_timestamp(start_s)
            t_end = _format_ass_timestamp(end_s)
            events.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{chunk}")
            cursor = end_s + gap

    if not events:
        return None

    content = header + "\n".join(events) + "\n"
    path = temp_dir / f"subtitle_{uuid.uuid4()}.ass"
    path.write_text(content, encoding="utf-8-sig")
    return path


def _build_ass_subtitle_filter(subtitle_file: Optional[Path], frame_height: int) -> str:
    """Build FFmpeg subtitles filter for a native ASS file (no force_style needed)."""
    if not subtitle_file or not subtitle_file.exists():
        return ""
    file_esc = _ffmpeg_escape_path(subtitle_file)
    return f"subtitles='{file_esc}'"


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

    timed_subtitle_file = _write_timed_subtitle_ass(subtitle_text or "", audio_seconds, width, height, temp_dir, audio_path=audio_path)
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


import os
import uuid
import subprocess
import time
import datetime
from pathlib import Path
from core.llm import get_llm_service, unload_ollama
from core.sd_client import resim_ciz
from core.news_fetcher import get_top_3_separate_news
from core.tts_config import PIPER_MODEL, PIPER_CONFIG
from core.config import SD_WIDTH, SD_HEIGHT
from core.news_memory import mark_used_titles

def generate_news_script(news_title):
    prompt = (
        f"You are a professional News Anchor. Write a very short, engaging 10-second script "
        f"summarizing this headline:\n\n"
        f"Headline: '{news_title}'\n\n"
        f"Rules:\n"
        f"- Language: TURKISH (Türkçe) ONLY.\n"
        f"- Tone: Professional, fast-paced news anchor.\n"
        f"- Length: EXACTLY 10-15 words. NO MORE.\n"
        f"- No Intro/Outro. No subtitles. Just the spoken text.\n"
        f"Output ONLY the script text."
    )
    
    try:
        text = get_llm_service().ask(
            prompt,
            system="You are a Turkish News Anchor. Speak Turkish.",
            timeout=60,
            retries=1,
        )
        return text.strip().replace('"', '')
    except Exception as e:
        print(f"Script Gen Error: {e}")
        return f"Gündemdeki gelişme: {news_title}."

def generate_visual_prompt(news_title):
    prompt = (
        f"Create a high-end cinematic photorealistic AI image prompt for this news headline:\n"
        f"'{news_title}'\n\n"
        f"Style: National Geographic, Award-winning photography, 8k, highly detailed, dramatic lighting.\n"
        f"Output ONLY the English prompt."
    )
    try:
        return get_llm_service().ask_english(prompt, timeout=60, retries=1)
    except Exception as e:
        print(f"LLM Error: {e}")
        return "A cinematic news image."

import re

def sanitize_text(text: str) -> str:
    # 1. Remove invisible characters/control codes
    text = "".join(ch for ch in text if ch.isprintable())
    
    # 2. Strict whitelist: ONLY Turkish letters, numbers, space, and basic sentence punctuation (. , ! ?)
    # Removed: - (dash), " (quote), ' (apostrophe), : (colon), ; (semicolon) to prevent "minus/quote" reading
    text = re.sub(r'[^a-zA-Z0-9\s\.,!\?çÇğĞıİöÖşŞüÜ]', ' ', text)
    
    # 3. Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def generate_audio(text, output_path):
    # Clean text
    text = sanitize_text(text)
    
    print(f"🎤 TTS Final Clean Text: {text}")
    
    # Safety clamp
    if len(text.split()) > 40:
        print("⚠️ Text too long, truncating...")
        text = " ".join(text.split()[:40])
        
    print(f"🎤 TTS Sending to Piper: {text}...")
    
    cmd = [
        "piper",
        "-m", PIPER_MODEL,
        "-c", PIPER_CONFIG,
        "-f", str(output_path),
        "--length-scale", "1.0"
    ]
    print(f"   Command: {cmd}")
    
    try:
        # EXACT Match to core/tts.py (removed explicit encoding='utf-8')
        # Rely on system default which works for the Chat module
        result = subprocess.run(
            cmd, 
            input=text, 
            text=True, 
            capture_output=True, # core uses check=True but we want to see errors, capture should be fine
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode != 0:
            print(f"❌ Piper Error (Code {result.returncode}):")
            print(f"   Stderr: {result.stderr}")
            print(f"   Stdout: {result.stdout}")
        else:
             print(f"✅ Audio created at {output_path}")
             
    except Exception as e:
        print(f"❌ Subprocess Exception: {e}")
        
    return os.path.exists(output_path)

def create_video_clip_ffmpeg(image_path, audio_path, output_path):
    # User requested 1024x1024 if config is set to that.
    # We will use SD_WIDTH:SD_HEIGHT from config.
    width = SD_WIDTH
    height = SD_HEIGHT
    
    # FFmpeg filter to scale/crop to target resolution
    # setsar=1 ensures square pixels
    vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", vf_filter,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(output_path)

def concat_videos_ffmpeg(video_paths, output_path):
    list_file = output_path.parent / "list.txt"
    with open(list_file, "w", encoding='utf-8') as f:
        for path in video_paths:
            # FFmpeg concat demuxer needs absolute paths to find files in 'temp' 
            # when list.txt is in 'generated_videos'
            # Also, Windows paths need to be escaped or use forward slashes.
            abs_path = path.resolve().as_posix() # as_posix() uses forward slashes
            f.write(f"file '{abs_path}'\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path)
    ]
    # Capture stderr to verify errors if it fails again
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg Concat Error: {result.stderr}")
        
    try:
        os.remove(list_file)
    except:
        pass
    return os.path.exists(output_path)

def process_daily_news_video(progress_callback=print):
    TEMP_DIR = Path("temp")
    TEMP_DIR.mkdir(exist_ok=True)
    
    # Save folder: generated_videos/YYYY-MM-DD/
    today_str = datetime.date.today().isoformat()
    VIDEOS_DIR = Path("generated_videos") / today_str
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch
    progress_callback("Haberler toplanıyor...")
    news_items = get_top_3_separate_news()
    if not news_items:
        return False, "Haber bulunamadı."
    
    # Mark selected news as used for TTL memory
    mark_used_titles(news_items, source="video")
        
    # 2. Sequential Generation (Memory Optimized)
    # Step A: Text & Prompts (LLM)
    scripts = []
    prompts = []
    
    for i, news in enumerate(news_items):
        idx = i + 1
        progress_callback(f"Senaryo & Prompt {idx}/{len(news_items)} yazılıyor...")
        scripts.append(generate_news_script(news))
        prompts.append(generate_visual_prompt(news))
    
    # UNLOAD LLM NOW
    progress_callback("🧹 VRAM Temizleniyor (LLM Kapatılıyor)...")
    unload_ollama()
    time.sleep(2)
    
    clip_paths = []
    
    for i, news in enumerate(news_items):
        idx = i + 1
        
        # Step B: Audio (CPU)
        progress_callback(f"Ses {idx} üretiliyor...")
        audio_path = TEMP_DIR / f"news_audio_{uuid.uuid4()}.wav"
        generate_audio(scripts[i], audio_path)
        
        # Step C: Image (GPU - SD)
        progress_callback(f"Görsel {idx} çiziliyor...")
        success, image_path, _ = resim_ciz(prompts[i])
        
        if not success:
            progress_callback(f"⚠️ Görsel {idx} üretilemedi!")
            continue
            
        # Step D: Clip (CPU)
        progress_callback(f"Klip {idx} montajlanıyor...")
        clip_path = TEMP_DIR / f"clip_{uuid.uuid4()}.mp4"
        create_video_clip_ffmpeg(image_path, audio_path, clip_path)
        
        if os.path.exists(clip_path):
            clip_paths.append(clip_path)
            
    if not clip_paths:
        return False, "Klip oluşturulamadı."
        
    # 3. Final Merge
    progress_callback("Tüm sahneler birleştiriliyor...")
    final_filename = f"news_video_{uuid.uuid4()}.mp4"
    final_path = VIDEOS_DIR / final_filename
    
    concat_videos_ffmpeg(clip_paths, final_path)
    
    if os.path.exists(final_path):
        progress_callback("Video tamamlandı!")
        return True, str(final_path)
    else:
        return False, "Birleştirme hatası."

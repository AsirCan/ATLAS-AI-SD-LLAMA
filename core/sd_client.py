import requests
import base64
import os
from datetime import datetime
import time
from core.config import (
    RED, RESET, GREEN, YELLOW,
    SD_WIDTH, SD_HEIGHT,
    SD_STEPS, SD_CFG_SCALE,
    SD_SAMPLER
)

# ==================================================
# Forge (Stable Diffusion) API
URL = "http://127.0.0.1:7860"

def get_image_folder():
    """Bugünün tarihine göre klasör oluşturur."""
    base_folder = "generated_images"
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(base_folder, today)
    os.makedirs(path, exist_ok=True)
    return path

def save_image_base64(img_base64):
    """Base64 gelen resmi kaydeder."""
    folder = get_image_folder()
    existing_files = [f for f in os.listdir(folder) if f.endswith(".png")]
    
    # Düzeltme: Dosya sayısına değil, en son numaraya bakmalıyız (silinen varsa karışmasın)
    max_num = 0
    for f in existing_files:
        try:
            # atlas_001.png -> 001 -> 1
            num = int(f.split("_")[1].split(".")[0])
            if num > max_num:
                max_num = num
        except:
            pass
            
    file_number = max_num + 1
    filename = f"atlas_{file_number:03d}.png"
    file_path = os.path.join(folder, filename)
    with open(file_path, "wb") as f:
        f.write(base64.b64decode(img_base64))
    return file_path

def resim_ciz(prompt_en):
    """
    Gelen İngilizce prompt'u DOĞRUDAN Stable Diffusion'a gönderir.
    Ara katman (LLM çevirisi/özeti) İPTAL EDİLDİ.
    """

    # --- DEĞİŞİKLİK BURADA ---
    # Artık promptun tamamını alt satıra tam olarak yazıyor.
    print(f"{GREEN}🎨 Çizilecek Final Prompt:{RESET}")
    print(f"{GREEN}{prompt_en}{RESET}")
    # -------------------------

    # Temizlik Robotu (Note: vs. temizliği)
    if "Note:" in prompt_en:
        prompt_en = prompt_en.split("Note:")[0].strip()
    if "(Note" in prompt_en:
        prompt_en = prompt_en.split("(Note")[0].strip()
    if "Here is" in prompt_en:
         prompt_en = prompt_en.split(":")[-1].strip()

    print("📐 SD RESOLUTION:", SD_WIDTH, "x", SD_HEIGHT)

    # Stable Diffusion Payload
    payload = {
        # ARTIK EKLEME YOK! LLM ne dediyse saf haliyle o gidiyor.
        "prompt": prompt_en, 
        
        # Ama Negatif Prompt (İstenmeyenler) kalmalı, bu kaliteyi korur.
        "negative_prompt": (
            "cartoon, anime, illustration, painting, drawing, text, watermark, signature, logo, "
            "split image, double exposure, grid, collage, bad anatomy, deformed, blurry, low quality, "
            "pixelated, worst quality, low resolution, ugly, extra fingers, missing limbs, distorted face, "
            "fake, 3d render, plastic looking, overexposed, underexposed"
        ),
        "steps": SD_STEPS,
        "sampler_name": SD_SAMPLER,
        "width": SD_WIDTH,
        "height": SD_HEIGHT,
        "cfg_scale": SD_CFG_SCALE
    }

    try:
        print(f"{YELLOW}⏳ Çizim başlatılıyor...{RESET}")
        baslangic_zamani = time.time()

        response = requests.post(
            url=f"{URL}/sdapi/v1/txt2img",
            json=payload,
            timeout=300
        )
        result = response.json()

        bitis_zamani = time.time()
        gecen_sure = bitis_zamani - baslangic_zamani

        if "images" in result and len(result["images"]) > 0:
            image_base64 = result["images"][0]
            file_path = save_image_base64(image_base64)
            
            print(f"{GREEN}✅ Resim kaydedildi: {file_path}{RESET}")
            print(f"{YELLOW}🚀 Süre: {gecen_sure:.2f} saniye{RESET}")
            
            return True, file_path, prompt_en 
        else:
            return False, None, None

    except Exception as e:
        print(f"{RED}❌ Çizim Hatası: {e}{RESET}")
        return False, None, None
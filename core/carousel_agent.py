import time
import requests
import json
from core.daily_visual_agent import dunya_gundemini_getir, ask_ollama_english, free_ollama_vram
from core.sd_client import resim_ciz
from core.config import RED, GREEN, YELLOW, RESET
from core.llm import MODEL

def generate_carousel_content(log_callback=print):
    """
    1. Haberleri tarar.
    2. Tek bir konu seçer.
    3. 10 farklı görsel promptu hazırlar.
    4. 10 Görseli sırayla çizer.
    """
    
    # 1. Haberleri Çek
    log_callback("🌍 Global gündem taranıyor (Carousel)...")
    ham_liste = dunya_gundemini_getir(limit=100)
    
    if not ham_liste:
        return False, None, "Haber bulunamadı"

    # Defensive Coding: ham_liste'nin list olduğundan emin ol
    if not isinstance(ham_liste, list):
        log_callback(f"⚠️ Uyarı: Haber listesi {type(ham_liste)} tipinde geldi. Listeye çevriliyor.")
        try:
             ham_liste = list(ham_liste)
        except:
             return False, None, f"Veri hatası: {type(ham_liste)}"

    taze_liste_str = "\n".join(ham_liste[:50]) # İlk 50 haberi al

    # 2. Tek Bir Konu Seç
    log_callback("🤔 Carousel için en iyi konu seçiliyor...")
    
    topic_selection_prompt = (
        "Here is a list of today's news:\n"
        f"{taze_liste_str}\n\n"
        "TASK: Select ONE single most visually captivating topic for an Instagram Carousel.\n"
        "The topic must be broad enough to have 10 different visual interpretations (e.g. Space, AI, Future City, Ocean).\n"
        "OUTPUT ONLY the topic name (e.g. 'Future of Space Stations')."
    )
    
    topic = ask_ollama_english(topic_selection_prompt)
    log_callback(f"🎯 Seçilen Konu: {topic}")
    
    # 3. 10 Farklı Prompt Üret
    log_callback("🧠 10 Farklı görsel promptu yazılıyor...")
    
    carousel_prompt = (
        f"TOPIC: {topic}\n\n"
        "TASK:\n"
        "Create an Instagram Carousel with EXACTLY 10 slides that form a COHERENT VISUAL NARRATIVE.\n\n"
        "STEP 1:\n"
        "Analyze the topic and choose ONE SINGLE, LOGICAL VARIATION AXIS that best fits the subject.\n"
        "The variation axis must be naturally related to the topic.\n\n"
        "Examples of variation axes (choose only ONE):\n"
        "- Evolution / versions / iterations\n"
        "- Emotional intensity\n"
        "- Cause → impact → aftermath\n"
        "- Scale or magnitude\n"
        "- Stability → collapse → recovery\n"
        "- Human impact over time\n"
        "- Technological progression\n"
        "- Time of day / Weather progression\n\n"
        "STEP 2:\n"
        "Select ONE clear subject or scene derived from the topic.\n"
        "This subject must remain visually consistent across all slides.\n\n"
        "STEP 3:\n"
        "Create 10 prompts that show the SAME subject evolving ONLY along the chosen variation axis.\n\n"
        "STRICT RULES:\n"
        "1. Do NOT change art style.\n"
        "2. Do NOT change the main subject.\n"
        "3. Keep camera framing consistent.\n"
        "4. Each slide must feel like the next moment or stage of the same story.\n"
        "5. Prompts must be high-quality Stable Diffusion prompts in English.\n\n"
        "OUTPUT FORMAT (STRICT JSON ONLY):\n"
        "{\n"
        '  "caption": "Write a short Instagram caption that invites users to swipe and comment. END THE CAPTION with 10-15 relevant hashtags mixing popular ones (#ai, #art, #viral) and niche ones (#stablediffusion, #aiart). Example: Great caption text! 🔥\\n\\n#ai #digitalart #technology...",\n'
        '  "slides": [\n'
        '    {"title": "Short Label (e.g. 1920s)", "prompt": "Slide 1 description..."},\n'
        '    {"title": "Short Label (e.g. 1950s)", "prompt": "Slide 2 description..."},\n'
        '    ...\n'
        '    {"title": "Short Label (e.g. 2090s)", "prompt": "Slide 10 description..."}\n'
        '  ]\n'
        "}\n"
        "Do NOT include explanations. Ensure valid JSON."
    )
    
    json_response_str = ask_ollama_english(carousel_prompt)
    
    # JSON Temizliği
    parsed_slides = []
    caption = ""

    try:
        start_idx = json_response_str.find('{')
        end_idx = json_response_str.rfind('}') + 1
        clean_json = json_response_str[start_idx:end_idx]
        data = json.loads(clean_json)
        
        raw_slides = data.get("slides", [])
        caption = data.get("caption", "")
        
        # Validate slides
        for item in raw_slides:
            if isinstance(item, dict):
                p_title = item.get("title", "Variation")
                p_text = item.get("prompt", "")
                if p_text:
                    parsed_slides.append({"title": p_title, "prompt": p_text})
            elif isinstance(item, str):
                parsed_slides.append({"title": "Scene", "prompt": item})

        if len(parsed_slides) < 10:
             # Eksikleri tamamla
            while len(parsed_slides) < 10:
                parsed_slides.append(parsed_slides[0] if parsed_slides else {"title": "Extra", "prompt": f"A creative shot of {topic}"})

    except Exception as e:
        log_callback(f"❌ JSON Parse Hatası: {e}")
        # Fallback
        parsed_slides = [{"title": f"Variation {i+1}", "prompt": f"Artistic interpretation of {topic}, variation {i+1}"} for i in range(10)]

    # 4. SD Öncesi VRAM Temizliği 

    # 4. SD Öncesi VRAM Temizliği
    free_ollama_vram(log_callback)
    time.sleep(2)
    
    # 5. Görselleri Çiz (Döngü)
    generated_images = []
    
    log_callback(f"🎨 Toplam 10 görsel çizilecek. Başlanıyor...")
    
    for i, slide in enumerate(parsed_slides):
        current_num = i + 1
        prompt = slide["prompt"]
        slide_title = slide["title"]
        
        log_callback(f"LAYER_UPDATE:[{slide_title}] Görsel {current_num}/10 çiziliyor...")
        
        # Retry mekanizması (basit)
        success = False
        retry_count = 0
        file_path = None
        
        while not success and retry_count < 2:
            s, path, _ = resim_ciz(prompt)
            if s:
                success = True
                file_path = path
            else:
                retry_count += 1
                log_callback(f"⚠️ Çizim hatası, tekrar deneniyor ({retry_count})...")
                time.sleep(1)
        
        if success:
            generated_images.append({
                "path": file_path,
                "prompt": prompt,
                "title": slide_title, # UI için başlık
                "style_index": current_num
            })
            log_callback(f"✅ {current_num}. görsel hazır. ({slide_title})")
        else:
            log_callback(f"❌ {current_num}. görsel çizilemedi.")
            # Boş da olsa devam et, carousel bozulmasın diye placeholder koyabiliriz ama şimdilik atlıyoruz
        
        # --- SOĞUTMA MOLASI ---
        if current_num < 10: # Sonuncudan sonra beklemeye gerek yok
            log_callback(f"❄️ Sistem soğutuluyor (5 sn)...")
            time.sleep(5)

    return True, generated_images, caption

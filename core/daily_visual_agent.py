import time
import feedparser
import difflib
import random

from core.llm import get_llm_service, unload_ollama
from core.sd_client import resim_ciz
from core.news_fetcher import RSS_SOURCES
from core.news_memory import get_used_title_set, mark_used_titles, normalize_title, prune_expired
from core.config import USED_NEWS_TTL_DAYS

def dunya_gundemini_getir(limit=100):
    tum_basliklar = []
    
    # Tüm kaynakları gez
    for url in RSS_SOURCES:
        try:
            print(f"📡 Taranıyor: {url}...")
            feed = feedparser.parse(url)
            for entry in feed.entries:
                tum_basliklar.append(entry.title.strip())
        except Exception as e:
            print(f"⚠️ RSS Hatası ({url}): {e}")
            continue

    if not tum_basliklar:
        return None

    # Listeyi karıştır ki hep aynı kaynaktan gelmesin
    random.shuffle(tum_basliklar)
    
    # Limiti uygula
    return tum_basliklar[:limit]

# 👇 1. AŞAMA: HABER SEÇME 👇
def en_iyi_uc_haberi_sec(haber_listesi_string):
    prompt = (
        "Here is a long list of today's world news headlines:\n"
        f"{haber_listesi_string}\n\n"
        "TASK: Select the TOP 3 most visually interesting headlines to merge into ONE image.\n"
        "CRITERIA:\n"
        "- The headlines MUST be from the provided list.\n"
        "- Prioritize: Technology, Space, Urban Events, Future, Culture, Mystery.\n"
        "- Avoid: War, Politics, excessive Tragedy.\n"
        "- Don't get stuck on 'Nature' unless it's a major event.\n"
        "- They must be distinct concepts.\n\n"
        "OUTPUT FORMAT:\n"
        "Reply ONLY with the 3 selected headlines, one per line, starting with a hyphen (-)."
    )
    try:
        return get_llm_service().ask_english(prompt, timeout=60, retries=1)
    except Exception as e:
        print(f"LLM Error: {e}")
        return "- A conceptual global tech breakthrough\n- A mysterious space discovery\n- A futuristic city innovation"

# 👇 2. AŞAMA: GÖRSEL PROMPT HAZIRLAMA 👇
def sahneyi_birlestir(secilen_3_haber):
    prompt = (
        "Your task is to create a creative Art Direction for an image based on these 3 news headlines:\n"
        f"{secilen_3_haber}\n\n"
        "INSTRUCTIONS:\n"
        "1. DO NOT try to draw specific people, politicians, or exact numbers.\n"
        "2. Create a HIGH-END CINEMATIC SHOT representing the core themes metaphorically.\n"
        "3. STYLE: 'Sora-level realism', 8k resolution, 35mm film grain, establishing shot, atmospheric lighting, moody, incredibly detailed textures.\n"
        "4. ADAPTIVE STYLE: Choose the style that fits the news topics:\n"
        "   - Tech/Science -> Futuristic, Clean, High-tech.\n"
        "   - Nature/Climate -> National Geographic, Cinematic, Epic.\n"
        "   - Urban/Society -> Street Photography, Gritty, Moody.\n"
        "   - Politics/Strategy -> Mural style, Abstract, Symbolic.\n"
        "5. AVOID: Surrealism, cartoons, illustrations, abstract art, floating objects, text, collage.\n"
        "6. Start with: 'A comprehensive cinematic shot of...'\n"
        "7. Output ONLY the visual description prompt."
    )
    try:
        return get_llm_service().ask_english(prompt, timeout=60, retries=1)
    except Exception as e:
        print(f"LLM Error: {e}")
        return "A conceptual image showing diverse global events merging together."

# 👇 ANA FONKSİYON 👇
def gunluk_instagram_gorseli_uret(log_callback=print):
    
    # 1. Haberleri Çek
    log_callback(f"🌍 Global gündem taranıyor...") 
    ham_liste = dunya_gundemini_getir(limit=100)
    
    if not ham_liste:
        log_callback("⚠️ Haber kaynağına ulaşılamadı.")
        return False, None, "No news"

    # --- FİLTRELEME (TTL tabanlı SQLite hafıza) ---
    ttl_seconds = USED_NEWS_TTL_DAYS * 24 * 60 * 60
    prune_expired(ttl_seconds)
    kullanilmis_set = get_used_title_set(ttl_seconds)
    
    taze_liste = []
    for haber in ham_liste:
        clean_haber = haber.strip()
        # Eğer haber daha önce kullanılmamışsa ekle
        if normalize_title(clean_haber) not in kullanilmis_set:
            taze_liste.append(f"- {clean_haber}")
    
    log_callback(f"📉 Filtreleme Sonucu: {len(ham_liste)} haberden {len(taze_liste)} tanesi geriye kaldı.")

    # EĞER YENİ HABER YOKSA İŞLEMİ DURDUR (Eskiden burası siliyordu, artık silmiyor)
    if len(taze_liste) < 3:
        log_callback("🚫 YETERLİ YENİ HABER YOK! Aynılarını yapmamak için duruyorum.")
        return False, None, "Not enough new news"

    # Listeyi stringe çevirip LLM'e ver
    taze_liste_str = "\n".join(taze_liste)

    # 2. Üç Haberi Seç
    log_callback(f"🤔 3 Haber seçiliyor...")
    secilen_uc_str = en_iyi_uc_haberi_sec(taze_liste_str)
    log_callback(f"📰 Seçilen 3 Haber:\n{secilen_uc_str}")

    # --- SEÇİLENLERİ KAYDET ---
    # --- SEÇİLENLERİ KAYDET (DÜZELTME: Orijinal başlığı bul) ---
    secilenler_liste = secilen_uc_str.split("\n")
    final_save_list = []
    
    for item in secilenler_liste:
        clean_item = item.replace("-", "").strip()
        # Orijinal listeden (ham_liste) en benzerini bul
        # cutoff=0.5: %50 benzerlik yeterli (LLM bazen kelime değiştirir)
        matches = difflib.get_close_matches(clean_item, ham_liste, n=1, cutoff=0.5)
        
        if matches:
            # Eşleşme bulunduysa ORİJİNALİNİ kaydet (Böylece filtre bir dahakine çalışır)
            final_save_list.append(matches[0])
            log_callback(f"d_match: '{clean_item}' -> '{matches[0]}'")
        else:
            # Bulamazsa mecburen LLM'in dediğini kaydet
            final_save_list.append(clean_item)

    mark_used_titles(final_save_list, source="daily_visual")
    # --------------------------

    # 3. Sahneyi Birleştir
    log_callback(f"🧠 Hikaye kurgulanıyor...")
    birlesik_sahne_promptu = sahneyi_birlestir(secilen_uc_str)
    
    if len(birlesik_sahne_promptu) < 20:
        birlesik_sahne_promptu = "A complex, cinematic photograph showing a juxtaposition of advanced technology, nature, and society, detailed, 8k."
    else:
        log_callback(f"🇬🇧 Prompt: {birlesik_sahne_promptu[:100]}...") 

    # 4. VRAM Temizliği
    unload_ollama()
    time.sleep(1.5) 

    # 5. Çizim
    log_callback("🎨 Görsel oluşturuluyor...")
    
    success, file_path, used_prompt = resim_ciz(birlesik_sahne_promptu)
    
    extra_data = {
        "prompt": used_prompt,
        "news": secilen_uc_str
    }
    
    return success, file_path, extra_data

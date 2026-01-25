import requests
import time
import feedparser
import os
import difflib
import random

# core.llm'den sadece ayarları alıyoruz
from core.llm import MODEL, OLLAMA_URL 
from core.sd_client import resim_ciz

# ==========================================
# 🌍 GLOBAL AYARLAR
# ==========================================
RSS_SOURCES = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",           # BBC World
    "https://www.sciencedaily.com/rss/top/science.xml",     # Science Daily
    "https://www.wired.com/feed/category/science/latest/rss", # Wired Science
    "https://futurism.com/feed"                             # Futurism
]
HISTORY_FILE = "used_news_log.txt" 

def ask_ollama_english(msg):
    """İngilizce konuşan özel LLM fonksiyonu."""
    try:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "You are a creative AI visual director. You MUST write in ENGLISH only."},
                {"role": "user", "content": msg}
            ],
            "stream": False
        }
        r = requests.post(OLLAMA_URL, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return "A conceptual image showing diverse global events merging together."

def free_ollama_vram(log_callback=print):
    """LLM'i VRAM'den temizle."""
    try:
        payload = {"model": MODEL, "keep_alive": 0}
        requests.post(OLLAMA_URL, json=payload, timeout=3)
        log_callback(f"🧹 VRAM Temizliği: {MODEL} bellekten atıldı.")
    except Exception as e:
        log_callback(f"⚠️ VRAM temizleme hatası: {e}")

# 👇 HAFIZA SİSTEMİ 👇
def get_used_news():
    """Daha önce kullanılan haberleri dosyadan okur."""
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def save_used_news(news_list):
    """Seçilen haberleri dosyaya kaydeder."""
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for news in news_list:
            clean = news.replace("- ", "").replace("-", "").strip()
            if clean:
                f.write(clean + "\n")

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
    return ask_ollama_english(prompt)

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
    return ask_ollama_english(prompt)

# 👇 ANA FONKSİYON 👇
def gunluk_instagram_gorseli_uret(log_callback=print):
    
    # 1. Haberleri Çek
    log_callback(f"🌍 Global gündem taranıyor...") 
    ham_liste = dunya_gundemini_getir(limit=100)
    
    if not ham_liste:
        log_callback("⚠️ Haber kaynağına ulaşılamadı.")
        return False, None, "No news"

    # --- FİLTRELEME (DÜZELTİLEN KISIM) ---
    kullanilmislar = get_used_news()
    # Hızlı kontrol için kümeye (set) çeviriyoruz
    kullanilmis_set = set(kullanilmislar)
    
    taze_liste = []
    for haber in ham_liste:
        clean_haber = haber.strip()
        # Eğer haber daha önce kullanılmışlar listesinde YOKSA ekle
        if clean_haber not in kullanilmis_set:
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

    save_used_news(final_save_list)
    # --------------------------

    # 3. Sahneyi Birleştir
    log_callback(f"🧠 Hikaye kurgulanıyor...")
    birlesik_sahne_promptu = sahneyi_birlestir(secilen_uc_str)
    
    if len(birlesik_sahne_promptu) < 20:
        birlesik_sahne_promptu = "A complex, cinematic photograph showing a juxtaposition of advanced technology, nature, and society, detailed, 8k."
    else:
        log_callback(f"🇬🇧 Prompt: {birlesik_sahne_promptu[:100]}...") 

    # 4. VRAM Temizliği
    free_ollama_vram(log_callback)
    time.sleep(1.5) 

    # 5. Çizim
    log_callback("🎨 Görsel oluşturuluyor...")
    
    success, file_path, used_prompt = resim_ciz(birlesik_sahne_promptu)
    
    extra_data = {
        "prompt": used_prompt,
        "news": secilen_uc_str
    }
    
    return success, file_path, extra_data
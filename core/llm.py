import requests
import subprocess
import time

from core.config import RED, YELLOW, RESET

# ==================================================
# Ollama Ayarları
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"
# ==================================================

SYSTEM_PROMPT = (
    "Senin adın Atlas. "
    "Bir yapay zeka asistanısın. "
    "Sadece TÜRKÇE konuş. "
    "Kısa, net ve mantıklı cevaplar ver. "
    "Gereksiz detay, hikâye veya yorum ekleme. "
    "Emin olmadığın konularda uydurma, bilmiyorsan açıkça söyle. "
    "Cevapların günlük ve doğal Türkçe olsun. "
    "Maksimum 3-4 kısa cümle kullan."
)

def llm_answer(msg: str, system_msg: str = None) -> str:
    # 3 kere deneme hakkı veriyoruz
    max_retries = 3
    
    # Eğer özel bir system prompt gelmediyse varsayılanı kullan
    final_system_prompt = system_msg if system_msg else SYSTEM_PROMPT

    for i in range(max_retries):
        try:
            payload = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": msg}
                ],
                "stream": False
            }

            # Timeout süresini artırdık çünkü modelin yüklenmesi uzun sürebilir
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()

            data = r.json()
            return data["message"]["content"]

        except Exception as e:
            print(RED + f"[OLLAMA HATASI - Deneme {i+1}/{max_retries}] {e}")
            if "500" in str(e) or "Connection refused" in str(e):
                print(f"{YELLOW}⏳ VRAM'in boşalması bekleniyor (5 sn)...{RESET}")
                time.sleep(5)  # 5 saniye bekle ve tekrar dene
            else:
                # Başka bir hataysa (örn: internet yok) bekleme, direkt çık
                break
    
    return "Şu an cevap veremiyorum (Teknik arıza)."


def ollama_warmup():
    """
    Ollama modelini Atlas başlamadan önce RAM/GPU'ya yükler.
    Offline modda 500 hatasını önler.
    """
    try:
        print("🧠 Ollama modeli ısıtılıyor (warm-up)...")
        subprocess.Popen(
            ["ollama", "run", MODEL],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2.5)
        print("✅ Ollama warm-up tamamlandı.")
    except Exception as e:
        print(f"⚠️ Ollama warm-up başarısız: {e}")


# llm.py dosyasının en altına ekle:

def unload_ollama():
    """
    Ollama modelini VRAM'den zorla boşaltır.
    Böylece Stable Diffusion için yer açılır.
    """
    try:
        # keep_alive: 0 parametresini gönderince model hemen unload olur
        payload = {"model": MODEL, "keep_alive": 0}
        requests.post(OLLAMA_URL, json=payload, timeout=3)
        print(f"{RED}🧹 Ollama VRAM'den temizlendi.{RESET}")
    except Exception as e:
        print(f"⚠️ VRAM temizleme hatası: {e}")

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
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_text}
            ],
            "stream": False
        }
        r = requests.post(OLLAMA_URL, json=payload, timeout=60)
        r.raise_for_status()
        
        prompt_en = r.json()["message"]["content"].strip()
        
        # Temizlik
        if ":" in prompt_en and len(prompt_en.split(":")[0]) < 20: # "Detailed prompt: ..." gibi şeyleri temizle
            prompt_en = prompt_en.split(":")[-1].strip()
            
        return prompt_en
        
    except Exception as e:
        print(f"Prompt Generation Error: {e}")
        # Hata olursa en azından orijinalini (veya basit çeviriyi) döndürmeye çalışalım 
        # ama LLM yoksa yapacak bir şey yok, orijinali yolla.
        return user_text
import os
import time
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, ChallengeRequired, LoginRequired
from core.llm import llm_answer
from core.config import RED, GREEN, YELLOW, RESET, INSTA_USERNAME

try:
    import keyring
except Exception:
    keyring = None

SESSION_FILE = "insta_session.json"
KEYRING_SERVICE = "atlas-instagram"
KEYRING_ACTIVE_USER = "__active_username__"

def set_instagram_credentials(username: str, password: str) -> bool:
    """
    Stores Instagram credentials in OS credential store (Windows Credential Manager via keyring).
    Does not write password to .env.
    """
    if not username or not password:
        raise ValueError("Username/password required")
    if keyring is None:
        raise RuntimeError("keyring is not available on this system")

    keyring.set_password(KEYRING_SERVICE, KEYRING_ACTIVE_USER, username)
    keyring.set_password(KEYRING_SERVICE, username, password)
    return True

def get_instagram_credentials():
    """
    Returns (username, password) using this priority:
    - username: .env INSTA_USERNAME, else keyring active username
    - password: keyring password for username
    """
    username = INSTA_USERNAME
    password = None

    if (not username) and keyring is not None:
        try:
            username = keyring.get_password(KEYRING_SERVICE, KEYRING_ACTIVE_USER)
        except Exception:
            username = None

    if username and keyring is not None:
        try:
            password = keyring.get_password(KEYRING_SERVICE, username)
        except Exception:
            password = None

    return username, password

def generate_caption_with_llama(prompt_text):
    print(f"{YELLOW}📝 Llama Instagram için açıklama yazıyor...{RESET}")
    
    # Eğer prompt_text bir listeyse (3 haber başlığı gibi), string'e çevirip birleştir
    if isinstance(prompt_text, list):
        prompt_text = "\n".join(prompt_text)

    system_instruction = (
    "You are a minimal and aesthetic Instagram Curator. "
    "TASK: Write a short, punchy caption for this image.\n\n"
    
    f"INPUT NEWS: '{prompt_text}'\n\n"
    
    "RULES:\n"
    "1. MAX 20 WORDS. Be mysterious and cool.\n"
    "2. No questions. Just a powerful statement.\n"
    "3. Add 10-15 popular hashtags mixed with niche ones (e.g. #art, #ai, #future, #cyberpunk, #digitalart).\n"
    "4. Usage of emojis is encouraged but keep it minimal (1-2).\n"
    "5. Language: ENGLISH."
    )
    
    user_input = f"INPUT NEWS:\n{prompt_text}\n\nOUTPUT CAPTION:"
    
    # SYSTEM_PROMPT yerine özel İngilizce prompt gönderiyoruz
    caption = llm_answer(user_input, system_msg=system_instruction)
    
    # ============================================================
    # 🧹TEMİZLİK ROBOTU
    # ============================================================
    
    # 1. "Here is..." ile başlıyorsa iki noktadan sonrasını al (Örnek: "Here is the caption: ...")
    if "Here is" in caption and ":" in caption:
        caption = caption.split(":")[-1]

    # 2. YASAKLI KELİMELER LİSTESİ 
    # AI'ın cümle sonuna ekleyebileceği tüm "Ben yaptım, ekledim" kalıpları
    yasakli_ifadeler = [
        "(Note:",       # Klasik "Note:"
        "Note:",        # Parantezsiz not
        "(Added",       # "Added relevant hashtags..."
        "(I have",      # "I have created..."
        "(This",        # "This caption is..."
        "(Here",        # "Here are..."
        "(Please",      # "Please check..."
        "**Note",       # Kalın yazılmış not
        "---"           # Ayırıcı çizgi
    ]

    # Bu ifadelerden hangisini görürse görsün, oradan itibaren cümleyi KESİP ATIYORUZ.
    for yasak in yasakli_ifadeler:
        if yasak in caption:
            # Bulduğu anda metni oradan böler ve sol tarafı (temiz kısmı) alır
            caption = caption.split(yasak)[0]

    # 3. Son rötüşlar (Boşlukları ve tırnakları temizle)
    return caption.strip().strip('"').strip("'")

def login_to_instagram():
    cl = Client()

    username, password = get_instagram_credentials()
    if not username or not password:
        print(f"{RED}❌ Instagram kimlik bilgileri bulunamadı.{RESET}")
        print(f"{YELLOW}UI üzerinden 'Instagram Giriş (Kaydet)' yapın veya .env içine INSTA_USERNAME yazın.{RESET}")
        return None
    
    # 1. Kayıtlı oturum varsa yükle ve TEST ET
    if os.path.exists(SESSION_FILE):
        print(f"{YELLOW}🍪 Kayıtlı oturum dosyası bulundu, deneniyor...{RESET}")
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            print(f"{GREEN}✅ Eski oturum ile giriş başarılı.{RESET}")
            return cl
        except (LoginRequired, Exception) as e:
            print(f"{RED}⚠️ Oturum geçersiz (Hata: {e}), dosya siliniyor...{RESET}")
            try:
                os.remove(SESSION_FILE)
            except:
                pass 
            print(f"{YELLOW}🔄 Sıfırdan giriş moduna geçiliyor...{RESET}")

    # 2. Sıfırdan Giriş
    print(f"{YELLOW}🔐 Şifre ile sıfırdan giriş yapılıyor...{RESET}")
    
    def code_handler(username, choice):
        return input(f"{YELLOW}👉 Instagram KOD istiyor! Telefona bak ve kodu yaz: {RESET}")

    try:
        cl.challenge_code_handler = code_handler
        cl.login(username, password)
    
    except TwoFactorRequired:
        print(f"{RED}⚠️ 2FA Kodu Gerekli!{RESET}")
        code = input(f"{YELLOW}👉 Google Authenticator uygulamasındaki 6 haneli kodu gir: {RESET}")
        cl.two_factor_login(code)
    
    except ChallengeRequired:
        print(f"{RED}⚠️ Doğrulama Gerekli!{RESET}")
        code = input(f"{YELLOW}👉 SMS/Mail kodunu gir: {RESET}")
        cl.challenge_resolve(cl.last_json, code)

    except Exception as e:
        print(f"{RED}❌ Giriş hatası: {e}{RESET}")
        return None

    # Başarılı olursa kaydet
    cl.dump_settings(SESSION_FILE)
    print(f"{GREEN}✅ Giriş başarılı ve yeni oturum kaydedildi.{RESET}")
    return cl

def reset_instagram_session() -> bool:
    """Deletes local session file to force re-login."""
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        return True
    except Exception:
        return False

def prepare_insta_caption(prompt_text):
    """
    Sadece caption oluşturur ve döndürür. Yükleme yapmaz.
    UI'da onay göstermek için kullanılır.
    """
    print(f"{YELLOW}⏳ GPU soğuması ve VRAM takası için bekleniyor...{RESET}")
    time.sleep(4) 
    
    caption = generate_caption_with_llama(prompt_text)
    
    # Ekrana da basalım (log için)
    print(f"\n{YELLOW}" + "="*50)
    print(f"📢 OLUŞTURULAN METİN:")
    print(f"{RESET}{caption}")
    print(f"{YELLOW}" + "="*50 + f"{RESET}\n")
    
    return caption

def login_and_upload(image_path, caption):
    """
    Doğrudan verilen caption ile yükleme yapar.
    Kullanıcı onayı ARTITK buranın dışındadır (UI veya main.py içinde).
    """
    if not image_path or not os.path.exists(image_path):
        return False, "Hata: Resim dosyası bulunamadı."

    try:
        # Giriş Yap
        cl = login_to_instagram()
        if not cl:
            return False, "Instagram'a giriş yapılamadı."
        
        print("⏳ Instagram'ın sakinleşmesi için 5 saniye bekleniyor...")
        time.sleep(5) 

        print(f"{YELLOW}📸 Fotoğraf yükleniyor...{RESET}")
        media = cl.photo_upload(
            path=image_path,
            caption=caption
        )
        
        success_msg = "Fotoğraf başarıyla Instagram'a yüklendi! 🎉"
        print(f"{GREEN}{success_msg} PK: {media.pk}{RESET}")
        return True, success_msg

    except Exception as e:
        error_msg = f"Instagram yükleme hatası: {e}"
        print(f"{RED}{error_msg}{RESET}")
        return False, error_msg

import traceback
from PIL import Image

def login_and_upload_album(image_paths, caption):
    """
    Birden fazla resmi (Carousel/Album) olarak yükler.
    image_paths: List of file paths (absolutes)
    Otomatik olarak JPG formatına çevirir (Instagram için).
    """
    if not image_paths or len(image_paths) == 0:
        return False, "Hata: Yüklenecek resim listesi boş."

    # Temp klasör
    temp_dir = "temp_insta_upload"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Validate and Convert to JPG
    ready_paths = []
    converted_files = [] # Silmek için tutuyoruz

    try:
        for p in image_paths:
            if os.path.exists(p):
                # Convert to JPG
                try:
                    img = Image.open(p)
                    rgb_im = img.convert('RGB')
                    
                    # Orijinal ismine _insta.jpg ekle
                    base_name = os.path.basename(p)
                    new_name = os.path.splitext(base_name)[0] + "_insta.jpg"
                    save_path = os.path.join(temp_dir, new_name)
                    
                    rgb_im.save(save_path, quality=95)
                    ready_paths.append(save_path)
                    converted_files.append(save_path)
                except Exception as e:
                    print(f"{RED}⚠️ Resim dönüştürme hatası ({p}): {e}{RESET}")
    
        if len(ready_paths) == 0:
            return False, "Hata: Hiçbir resim işlenemedi."

        # Giriş Yap
        cl = login_to_instagram()
        if not cl:
            return False, "Instagram'a giriş yapılamadı."
        
        print("⏳ Instagram'ın sakinleşmesi için 5 saniye bekleniyor...")
        time.sleep(5) 

        print(f"{YELLOW}📸 Albüm (Carousel) yükleniyor ({len(ready_paths)} resim)...{RESET}")
        
        media = cl.album_upload(
            paths=ready_paths,
            caption=caption
        )
        
        success_msg = "Albüm başarıyla Instagram'a yüklendi! 🎉"
        print(f"{GREEN}{success_msg} PK: {media.pk}{RESET}")
        
        return True, success_msg

    except Exception as e:
        # Detaylı Hata Loglama
        err_msg = str(e)
        trace = traceback.format_exc()
        print(f"{RED}❌ Instagram Albüm yükleme hatası detaylı: {err_msg}{RESET}")
        print(f"{RED}{trace}{RESET}")
        
        if "Unknown" in err_msg:
             return False, f"Bilinmeyen hata (Format sorunu olabilir). Loglara bakınız."
        
        return False, f"Yükleme hatası: {err_msg}"
        
    finally:
        # Temizlik: Dönüştürülen dosyaları sil
        for f in converted_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
        # Temp klasörü boşsa sil
        try:
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass
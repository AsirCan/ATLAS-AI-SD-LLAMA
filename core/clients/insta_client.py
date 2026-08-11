import os
import time
import requests
import base64
from pathlib import Path
from urllib.parse import urlparse
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, ChallengeRequired, LoginRequired
from core.clients.llm import llm_answer
from core.content.caption_format import format_caption_hashtags_bottom
from core.runtime.config import RED, GREEN, YELLOW, RESET, INSTA_USERNAME, INSTA_SESSIONID

try:
    import keyring
except Exception:
    keyring = None

try:
    from dotenv import dotenv_values
except Exception:
    dotenv_values = None

SESSION_FILE = "insta_session.json"
KEYRING_SERVICE = "atlas-instagram"
KEYRING_ACTIVE_USER = "__active_username__"
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "").strip()


class GraphAPIError(RuntimeError):
    def __init__(self, body: dict):
        self.body = body if isinstance(body, dict) else {"raw": str(body)}
        err = self.body.get("error", {}) if isinstance(self.body, dict) else {}
        msg = err.get("message") or str(self.body)
        super().__init__(f"Graph API error: {msg}")

    @property
    def code(self):
        return (self.body.get("error") or {}).get("code")

    @property
    def subcode(self):
        return (self.body.get("error") or {}).get("error_subcode")


def _read_runtime_env() -> dict:
    """
    Read config from current process env and latest .env file.
    .env wins so UI-saved values work without a full process restart.
    """
    values = dict(os.environ)
    env_path = Path(".env")
    if dotenv_values and env_path.exists():
        try:
            file_vals = dotenv_values(str(env_path))
            for k, v in file_vals.items():
                if v is not None:
                    values[k] = str(v)
        except Exception:
            pass
    return values


def _cfg(name: str, default: str = "") -> str:
    v = (_read_runtime_env().get(name) or default or "").strip()
    if name == "PUBLIC_BASE_URL":
        return v.rstrip("/")
    return v


def _imgbb_api_key() -> str:
    # Keep module constant as fallback for compatibility with existing imports/tests.
    return _cfg("IMGBB_API_KEY", IMGBB_API_KEY)

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

def _is_graph_api_enabled() -> bool:
    return bool(_cfg("IG_USER_ID") and _cfg("FB_ACCESS_TOKEN"))


# ==================================================
# LEGACY (instagrapi) YOLU
#
# instagrapi, Instagram'in resmi olmayan mobil API'sini taklit eder. Bu
# Instagram kullanim sartlarina aykiridir ve hesap kisitlama/kapatma riski
# tasir. Bu yuzden yedek yol ARTIK OTOMATIK DEVREYE GIRMEZ; kullanicinin
# .env icinde ALLOW_LEGACY_INSTAGRAPI=1 diyerek riski acikca kabul etmesi gerekir.
# ==================================================

GRAPH_REQUIRED_FIELDS = ["IG_USER_ID", "FB_ACCESS_TOKEN", "PUBLIC_BASE_URL"]

LEGACY_WARNING = (
    "UYARI: instagrapi resmi olmayan bir arayuzdur. Instagram kullanim "
    "sartlarina aykiridir ve hesabinizin kisitlanmasina veya kapatilmasina "
    "yol acabilir. Onerilen yol Graph API'dir."
)


def _missing_graph_fields() -> list:
    """Graph API icin eksik olan .env alanlarini listeler."""
    return [name for name in GRAPH_REQUIRED_FIELDS if not _cfg(name)]


def is_legacy_upload_allowed() -> bool:
    return _cfg("ALLOW_LEGACY_INSTAGRAPI").lower() in {"1", "true", "yes"}


def _legacy_blocked_message() -> str:
    """
    Graph API kurulu degilken kullaniciya ne eksik oldugunu soyler.
    Sessizce legacy yola dusmek yerine bu mesajla duruyoruz.
    """
    missing = ", ".join(_missing_graph_fields()) or "-"
    return (
        "Instagram yukleme yapilamadi: Graph API kurulumu tamamlanmamis. "
        f"Eksik alan(lar): {missing}. "
        "Studio > Instagram Baglanti Ayarlari > Graph API sekmesinden doldurun. "
        "Eski instagrapi yolunu bilerek kullanmak istiyorsaniz .env icine "
        "ALLOW_LEGACY_INSTAGRAPI=1 ekleyin. " + LEGACY_WARNING
    )

def _as_public_image_url(image_path_or_url: str) -> str:
    """
    Instagram Graph API needs a publicly reachable URL.
    - If a URL is already given, use it as-is.
    - If a local file is given, convert it using PUBLIC_BASE_URL + /images/... mapping.
    """
    src = (image_path_or_url or "").strip()
    if src.startswith("http://") or src.startswith("https://"):
        # If frontend sent localhost URL, rewrite it to tunnel URL for Graph API.
        parsed = urlparse(src)
        if parsed.hostname in {"127.0.0.1", "localhost"}:
            public_base = _cfg("PUBLIC_BASE_URL")
            if not public_base:
                raise ValueError("Local image URL verildi ama PUBLIC_BASE_URL yok.")
            path = parsed.path or ""
            if path.startswith("/images/"):
                suffix = path[len("/images/"):]
                return f"{public_base}/images/{suffix}"
        return src

    public_base = _cfg("PUBLIC_BASE_URL")
    if not public_base:
        raise ValueError(
            "Graph API upload icin PUBLIC_BASE_URL gerekli (or: https://your-domain.com)."
        )

    img_root = Path("generated_images").resolve()
    src_path = Path(src).resolve()

    try:
        rel = src_path.relative_to(img_root).as_posix()
    except ValueError as e:
        raise ValueError(
            "Graph API local dosya yolu sadece generated_images altindan destekleniyor."
        ) from e

    return f"{public_base}/images/{rel}"

def _ensure_graph_image_ready(image_path_or_url: str) -> str:
    """
    Instagram Graph API is strict with media fetching and accepts JPEG reliably.
    If local media is not jpg/jpeg, convert to jpg before building public URL.
    """
    src = (image_path_or_url or "").strip()
    if src.startswith("http://") or src.startswith("https://"):
        return src

    src_path = Path(src)
    ext = src_path.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return src

    # Convert unsupported/fragile formats (png/webp/etc.) to jpg in same folder
    try:
        from PIL import Image
        converted = src_path.with_name(f"{src_path.stem}_graph.jpg")
        img = Image.open(src_path).convert("RGB")
        img.save(converted, format="JPEG", quality=95)
        return str(converted)
    except Exception as e:
        raise RuntimeError(f"Graph image conversion failed: {e}")

def _graph_post(endpoint: str, payload: dict) -> dict:
    ig_graph_version = _cfg("IG_GRAPH_VERSION", "v24.0")
    fb_access_token = _cfg("FB_ACCESS_TOKEN")
    url = f"https://graph.facebook.com/{ig_graph_version}/{endpoint.lstrip('/')}"
    data = dict(payload)
    data["access_token"] = fb_access_token
    data["access_token"] = fb_access_token
    
    # Retry mechanism for timeouts
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = requests.post(url, data=data, timeout=120) # Increased timeout to 120s
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text}

            if not r.ok or "error" in body:
                # If it's a timeout error from FB side, maybe retry? 
                # For now, just raise if it's an API error
                raise GraphAPIError(body)
            return body

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"{YELLOW}⚠️ Graph API Timeout/Connection ({attempt+1}/{max_retries}): {e}{RESET}")
            if attempt == max_retries - 1:
                raise GraphAPIError({"error": {"message": f"Timeout after {max_retries} attempts", "details": str(e)}})
            time.sleep(3)
        except GraphAPIError:
            raise
        except Exception as e:
             raise GraphAPIError({"error": {"message": f"Unexpected error: {str(e)}"}})
    
    return {} # Should not reach here


def _discover_ig_user_id() -> str:
    """
    Fallback discovery when IG_USER_ID is missing/wrong.
    Uses FB_PAGE_ID first, then /me/accounts list.
    """
    fb_access_token = _cfg("FB_ACCESS_TOKEN")
    if not fb_access_token:
        return ""

    ig_graph_version = _cfg("IG_GRAPH_VERSION", "v24.0")
    fb_page_id = _cfg("FB_PAGE_ID")
    if fb_page_id:
        try:
            page_resp = requests.get(
                f"https://graph.facebook.com/{ig_graph_version}/{fb_page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": fb_access_token,
                },
                timeout=30,
            )
            page_body = page_resp.json()
            ig_obj = (page_body or {}).get("instagram_business_account") or {}
            ig_id = str(ig_obj.get("id") or "").strip()
            if ig_id:
                return ig_id
        except Exception:
            pass

    try:
        accounts_resp = requests.get(
            f"https://graph.facebook.com/{ig_graph_version}/me/accounts",
            params={
                "fields": "id,name,instagram_business_account",
                "access_token": fb_access_token,
            },
            timeout=30,
        )
        accounts_body = accounts_resp.json() if accounts_resp.ok else {}
        for page in (accounts_body or {}).get("data", []):
            ig_obj = page.get("instagram_business_account") or {}
            ig_id = str(ig_obj.get("id") or "").strip()
            if ig_id:
                return ig_id
    except Exception:
        pass

    return ""


def _is_invalid_object_id_error(e: Exception) -> bool:
    return isinstance(e, GraphAPIError) and e.code == 100 and e.subcode == 33


def _is_media_fetch_error(e: Exception) -> bool:
    if not isinstance(e, GraphAPIError):
        return False
    err = (e.body.get("error") or {}) if isinstance(e.body, dict) else {}
    code = err.get("code")
    sub = err.get("error_subcode")
    msg = str(err.get("message") or "").lower()
    user_msg = str(err.get("error_user_msg") or "").lower()
    return (
        (code == 9004 and sub == 2207052)
        or ("only photo or video can be accepted as media type" in msg)
        or ("medya uri" in user_msg)
        or ("media uri" in user_msg)
    )


def _upload_temp_public_image(local_image_path: str) -> str:
    """
    Upload local image to a temporary public host as a fallback when tunnel URL
    is not accepted by Instagram fetchers.
    """
    p = Path(local_image_path)
    if not p.exists():
        raise RuntimeError(f"Fallback upload file not found: {local_image_path}")

    # 0) ImgBB (Varsa en garantisi)
    imgbb_key = _imgbb_api_key()
    if imgbb_key:
        try:
            print(f"{YELLOW}☁️ ImgBB'ye yükleniyor...{RESET}")
            with p.open("rb") as f:
                r = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": imgbb_key, "expiration": 600}, # 10dk ömürlü link (Graph API çekene kadar yeter)
                    files={"image": f},
                    timeout=60
                )
            if r.ok:
                data = r.json().get("data", {})
                url = data.get("url")
                if url:
                    print(f"{GREEN}✅ ImgBB URL: {url}{RESET}")
                    return url
            else:
                print(f"{YELLOW}⚠️ ImgBB Hata: {r.text}{RESET}")
        except Exception as e:
            print(f"{YELLOW}⚠️ ImgBB Exception: {e}{RESET}")

    # 1) 0x0.st (simple, no key)
    try:
        print(f"{YELLOW}☁️ 0x0.st deneniyor...{RESET}")
        with p.open("rb") as f:
            r = requests.post(
                "https://0x0.st",
                files={"file": (p.name, f, "image/jpeg")},
                timeout=60,
            )
        if r.ok:
            url = (r.text or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                print(f"{GREEN}✅ 0x0.st URL: {url}{RESET}")
                return url
        else:
            print(f"{YELLOW}⚠️ 0x0.st Hata Kod: {r.status_code}, Body: {r.text[:200]}{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠️ 0x0.st Exception: {e}{RESET}")
        pass

    # 2) catbox.moe fallback
    try:
        print(f"{YELLOW}☁️ catbox.moe deneniyor...{RESET}")
        with p.open("rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (p.name, f, "image/jpeg")},
                timeout=60,
            )
        if r.ok:
            url = (r.text or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                print(f"{GREEN}✅ catbox.moe URL: {url}{RESET}")
                return url
        else:
            print(f"{YELLOW}⚠️ catbox.moe Hata Kod: {r.status_code}, Body: {r.text[:200]}{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠️ catbox.moe Exception: {e}{RESET}")
        pass

    raise RuntimeError("Gorsel icin gecici public URL olusturulamadi (Tum servisler denendi).")

def _publish_single_with_graph(image_path_or_url: str, caption: str):
    ig_user_id = _cfg("IG_USER_ID")
    if not ig_user_id:
        ig_user_id = _discover_ig_user_id()
    if not ig_user_id:
        raise RuntimeError("IG_USER_ID bulunamadi. UI'dan kaydet veya Graph Explorer ile tekrar al.")

    ready_path = _ensure_graph_image_ready(image_path_or_url)
    image_url = _as_public_image_url(ready_path)
    try:
        container = _graph_post(
            f"{ig_user_id}/media",
            {"image_url": image_url, "caption": caption or ""},
        )
    except Exception as e:
        if _is_invalid_object_id_error(e):
            discovered = _discover_ig_user_id()
            if discovered and discovered != ig_user_id:
                container = _graph_post(
                    f"{discovered}/media",
                    {"image_url": image_url, "caption": caption or ""},
                )
                ig_user_id = discovered
            else:
                raise
        elif _is_media_fetch_error(e):
            # Tunnel URL bazen Meta botlari tarafindan fetch edilemeyebiliyor.
            # Local dosyayi gecici public hosta yukleyip bir kez daha deniyoruz.
            src = (ready_path or "").strip()
            if not (src.startswith("http://") or src.startswith("https://")):
                fallback_public = _upload_temp_public_image(src)
                container = _graph_post(
                    f"{ig_user_id}/media",
                    {"image_url": fallback_public, "caption": caption or ""},
                )
            else:
                raise
        else:
            raise
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Graph API container id missing: {container}")

    time.sleep(2)
    published = _graph_post(
        f"{ig_user_id}/media_publish",
        {"creation_id": creation_id},
    )
    return published

def _publish_album_with_graph(image_paths: list[str], caption: str):
    ig_user_id = _cfg("IG_USER_ID")
    if not ig_user_id:
        ig_user_id = _discover_ig_user_id()
    if not ig_user_id:
        raise RuntimeError("IG_USER_ID bulunamadi. UI'dan kaydet veya Graph Explorer ile tekrar al.")

    children = []
    for path in image_paths:
        ready_path = _ensure_graph_image_ready(path)
        image_url = _as_public_image_url(ready_path)
        child = _graph_post(
            f"{ig_user_id}/media",
            {"image_url": image_url, "is_carousel_item": "true"},
        )
        cid = child.get("id")
        if not cid:
            raise RuntimeError(f"Graph API carousel child id missing: {child}")
        children.append(cid)

    parent = _graph_post(
        f"{ig_user_id}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption or "",
        },
    )
    parent_id = parent.get("id")
    if not parent_id:
        raise RuntimeError(f"Graph API carousel parent id missing: {parent}")

    time.sleep(3)
    published = _graph_post(
        f"{ig_user_id}/media_publish",
        {"creation_id": parent_id},
    )
    return published

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
    # Optional: Login with sessionid cookie (bypasses blocked password login)
    if INSTA_SESSIONID:
        try:
            print(f"{YELLOW}SessionID ile giriş deneniyor...{RESET}")
            cl.login_by_sessionid(INSTA_SESSIONID)
            cl.dump_settings(SESSION_FILE)
            print(f"{GREEN}SessionID ile giriş başarılı.{RESET}")
            return cl
        except Exception as e:
            print(f"{YELLOW}SessionID ile giriş başarısız: {e}{RESET}")


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
    caption = format_caption_hashtags_bottom(caption)
    
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
    caption = format_caption_hashtags_bottom(caption or "")

    if not image_path or not os.path.exists(image_path):
        if not ((image_path or "").startswith("http://") or (image_path or "").startswith("https://")):
            return False, "Hata: Resim dosyasi bulunamadi."

    try:
        if _is_graph_api_enabled():
            print(f"{YELLOW}[InstagramPublisher] Graph API ile tekli gorsel yukleniyor...{RESET}")
            published = _publish_single_with_graph(image_path, caption)
            media_id = published.get("id", "")
            success_msg = f"Fotograf Graph API ile yuklendi. ID: {media_id}"
            print(f"{GREEN}{success_msg}{RESET}")
            return True, success_msg

        # Graph API kurulu degil. Legacy yola sessizce dusme.
        if not is_legacy_upload_allowed():
            msg = _legacy_blocked_message()
            print(f"{RED}{msg}{RESET}")
            return False, msg

        print(f"{YELLOW}{LEGACY_WARNING}{RESET}")

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
    caption = format_caption_hashtags_bottom(caption or "")

    if not image_paths or len(image_paths) == 0:
        return False, "Hata: Yüklenecek resim listesi boş."

    if _is_graph_api_enabled():
        try:
            print(f"{YELLOW}[InstagramPublisher] Graph API ile carousel yukleniyor...{RESET}")
            published = _publish_album_with_graph(image_paths, caption)
            media_id = published.get("id", "")
            success_msg = f"Album Graph API ile yuklendi. ID: {media_id}"
            print(f"{GREEN}{success_msg}{RESET}")
            return True, success_msg
        except Exception as e:
            error_msg = f"Graph API album yukleme hatasi: {e}"
            print(f"{RED}{error_msg}{RESET}")
            return False, error_msg

    # Graph API kurulu degil. Legacy yola sessizce dusme.
    if not is_legacy_upload_allowed():
        msg = _legacy_blocked_message()
        print(f"{RED}{msg}{RESET}")
        return False, msg

    print(f"{YELLOW}{LEGACY_WARNING}{RESET}")

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


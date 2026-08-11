"""core/content/caption_format.py — hashtag'leri caption'in altina toplama."""

from core.content.caption_format import format_caption_hashtags_bottom


def test_hashtagler_alta_tasinir():
    out = format_caption_hashtags_bottom("Bugun #AI hakkinda konusalim")

    body, _, tags = out.partition("\n\n")
    assert body == "Bugun hakkinda konusalim"
    assert tags == "#AI"


def test_hashtag_yoksa_govde_degismez():
    assert format_caption_hashtags_bottom("Duz bir metin") == "Duz bir metin"


def test_tekrar_eden_hashtagler_teklenir():
    out = format_caption_hashtags_bottom("#ai bir #AI iki #Ai uc")

    assert out.split("\n\n")[-1] == "#ai"


def test_sira_korunur():
    out = format_caption_hashtags_bottom("#bir #iki #uc")

    assert out == "#bir #iki #uc"


def test_ekstra_hashtagler_eklenir():
    out = format_caption_hashtags_bottom("Govde #bir", extra_hashtags="#iki #uc")

    assert out.split("\n\n")[-1] == "#bir #iki #uc"


def test_sadece_hashtaglerden_olusan_girdi():
    assert format_caption_hashtags_bottom("#tek") == "#tek"


def test_noktalama_oncesi_bosluk_temizlenir():
    out = format_caption_hashtags_bottom("Merhaba #dunya , nasilsin")

    assert ", nasilsin" in out
    assert " ," not in out


def test_fazla_bos_satirlar_sadelestirilir():
    out = format_caption_hashtags_bottom("bir\n\n\n\n\niki")

    assert "\n\n\n" not in out


def test_bos_ve_none_girdi():
    assert format_caption_hashtags_bottom("") == ""
    assert format_caption_hashtags_bottom(None) == ""


def test_alt_cizgili_hashtag_tanınır():
    out = format_caption_hashtags_bottom("deniz #marine_bio calismasi")

    assert out.split("\n\n")[-1] == "#marine_bio"


def test_email_icindeki_diyez_hashtag_sayilmaz():
    # "#" bir kelimenin ortasindaysa hashtag degil.
    out = format_caption_hashtags_bottom("kod C#0 degil")

    assert "\n\n" not in out

"""
core/content/news_memory.py — TTL tabanli "kullanilmis haber" deposu.

Ayni haberin tekrar tekrar paylasilmasini engelleyen katman. Testler sqlite
ve json backend'lerini gecici dosyalar uzerinde calistirir; Mongo'ya
dokunulmaz.
"""

import time

import pytest

from core.content import news_memory


@pytest.fixture(autouse=True)
def temiz_depo(tmp_path, monkeypatch):
    """Her test kendi bos veritabaniyla baslasin."""
    monkeypatch.setattr(news_memory, "NEWS_MEMORY_DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(news_memory, "NEWS_MEMORY_JSON", str(tmp_path / "test.json"))
    monkeypatch.setattr(news_memory, "NEWS_MEMORY_BACKEND", "sqlite")


GUN = 24 * 60 * 60


class TestNormalizeTitle:
    def test_kucuk_harfe_cevirir(self):
        assert news_memory.normalize_title("Büyük HABER") == "büyük haber"

    def test_fazla_bosluklari_teker(self):
        assert news_memory.normalize_title("bir    iki\tuc") == "bir iki uc"

    def test_bas_son_bosluk_kirpilir(self):
        assert news_memory.normalize_title("  haber  ") == "haber"

    def test_bos_girdi(self):
        assert news_memory.normalize_title("") == ""
        assert news_memory.normalize_title(None) == ""


class TestSqliteBackend:
    def test_isaretlenen_baslik_geri_okunur(self):
        news_memory.mark_used_titles(["Mars'ta su bulundu"], source="test")

        assert "mars'ta su bulundu" in news_memory.get_used_title_set(7 * GUN)

    def test_isaretlenmemis_baslik_yok(self):
        news_memory.mark_used_titles(["Haber A"])

        assert "haber b" not in news_memory.get_used_title_set(7 * GUN)

    def test_normalizasyon_tekrarlari_engeller(self):
        news_memory.mark_used_titles(["  AYNI   Haber  "])

        used = news_memory.get_used_title_set(7 * GUN)
        assert news_memory.normalize_title("Ayni Haber") in used

    def test_ayni_baslik_iki_kez_yazilabilir(self):
        news_memory.mark_used_titles(["Tekrar"])
        news_memory.mark_used_titles(["Tekrar"])

        assert len(news_memory.get_used_title_set(7 * GUN)) == 1

    def test_coklu_baslik(self):
        news_memory.mark_used_titles(["Bir", "Iki", "Uc"])

        assert len(news_memory.get_used_title_set(7 * GUN)) == 3

    def test_bos_basliklar_atlanir(self):
        news_memory.mark_used_titles(["", "   ", None, "Gecerli"])

        assert news_memory.get_used_title_set(7 * GUN) == {"gecerli"}

    def test_bos_liste_cokmez(self):
        news_memory.mark_used_titles([])
        assert news_memory.get_used_title_set(7 * GUN) == set()


def mark_at(monkeypatch, titles, seconds_ago):
    """
    Basliklari gecmiste isaretlenmis gibi kaydeder.

    `monkeypatch.context()` sart: duz `monkeypatch.undo()` ayni fixture'i
    paylastigi icin `temiz_depo`'nun veritabani izolasyonunu da geri alir ve
    testler paylasilan bir DB uzerinden birbirini kirletir.
    """
    # Hedef zaman yamadan ONCE hesaplanmali: lambda icinde time.time()
    # cagirmak yamanin kendisini cagirip sonsuz donguye girer.
    target = int(time.time()) - seconds_ago
    with monkeypatch.context() as m:
        m.setattr(news_memory.time, "time", lambda: target)
        news_memory.mark_used_titles(titles)


class TestTTL:
    def test_ttl_disindaki_kayit_dondurulmez(self, monkeypatch):
        mark_at(monkeypatch, ["Eski haber"], 10 * GUN)

        assert news_memory.get_used_title_set(7 * GUN) == set()

    def test_ttl_icindeki_kayit_dondurulur(self, monkeypatch):
        mark_at(monkeypatch, ["Yeni haber"], 2 * GUN)

        assert "yeni haber" in news_memory.get_used_title_set(7 * GUN)

    def test_ttl_siniri_dahil(self, monkeypatch):
        mark_at(monkeypatch, ["Tam sinirda"], 7 * GUN - 60)

        assert "tam sinirda" in news_memory.get_used_title_set(7 * GUN)

    def test_prune_eski_kayitlari_siler(self, monkeypatch):
        mark_at(monkeypatch, ["Cok eski"], 10 * GUN)
        news_memory.mark_used_titles(["Guncel"])

        news_memory.prune_expired(7 * GUN)

        assert news_memory.get_used_title_set(365 * GUN) == {"guncel"}


class TestJsonBackend:
    @pytest.fixture(autouse=True)
    def json_modu(self, monkeypatch):
        monkeypatch.setattr(news_memory, "NEWS_MEMORY_BACKEND", "json")

    def test_yazma_ve_okuma(self):
        news_memory.mark_used_titles(["Json haberi"], source="test")

        assert "json haberi" in news_memory.get_used_title_set(7 * GUN)

    def test_bozuk_dosya_cokmez(self, tmp_path):
        import os

        with open(news_memory.NEWS_MEMORY_JSON, "w", encoding="utf-8") as f:
            f.write("{bu gecerli json degil")

        assert news_memory.get_used_title_set(7 * GUN) == set()
        assert os.path.exists(news_memory.NEWS_MEMORY_JSON)

    def test_prune_json_uzerinde_calisir(self, monkeypatch):
        mark_at(monkeypatch, ["Eski"], 10 * GUN)
        news_memory.mark_used_titles(["Yeni"])

        news_memory.prune_expired(7 * GUN)

        assert news_memory.get_used_title_set(365 * GUN) == {"yeni"}


class TestBackendSecimi:
    def test_bilinmeyen_backend_sqlite_e_duser(self, monkeypatch):
        monkeypatch.setattr(news_memory, "NEWS_MEMORY_BACKEND", "kasetcalar")
        assert news_memory._backend() == "sqlite"

    def test_mongo_takma_adi_normalize_edilir(self, monkeypatch):
        monkeypatch.setattr(news_memory, "NEWS_MEMORY_BACKEND", "mongo")
        assert news_memory._backend() == "mongodb"

    def test_buyuk_harf_kabul_edilir(self, monkeypatch):
        monkeypatch.setattr(news_memory, "NEWS_MEMORY_BACKEND", "JSON")
        assert news_memory._backend() == "json"

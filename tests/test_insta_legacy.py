"""
core/clients/insta_client.py — legacy (instagrapi) yolunun kapali olmasi.

conftest.py'deki instagrapi stub'i cagrilirsa AssertionError firlatir; yani
kapi bozulursa test sessizce gecmez.
"""

import pytest

from core.clients import insta_client as insta


@pytest.fixture
def graph_kapali(tmp_env):
    """Graph API kurulumu eksik senaryosu."""
    tmp_env(IG_USER_ID=None, FB_ACCESS_TOKEN=None, PUBLIC_BASE_URL=None)


@pytest.fixture
def sahte_gorsel(tmp_path):
    path = tmp_path / "gorsel.jpg"
    path.write_bytes(b"sahte-jpeg-verisi")
    return str(path)


class TestVarsayilanDavranis:
    def test_legacy_varsayilan_kapali(self, graph_kapali, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI=None)
        assert insta.is_legacy_upload_allowed() is False

    def test_sifir_degeri_kapali(self, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI="0")
        assert insta.is_legacy_upload_allowed() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
    def test_acik_onay_kapiyi_acar(self, tmp_env, value):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI=value)
        assert insta.is_legacy_upload_allowed() is True

    def test_gecersiz_deger_kapali_sayilir(self, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI="belki")
        assert insta.is_legacy_upload_allowed() is False


class TestEksikAlanTespiti:
    def test_hepsi_eksikse_listelenir(self, graph_kapali):
        assert set(insta._missing_graph_fields()) == {
            "IG_USER_ID",
            "FB_ACCESS_TOKEN",
            "PUBLIC_BASE_URL",
        }

    def test_kismi_kurulumda_sadece_eksikler(self, tmp_env):
        tmp_env(IG_USER_ID="123", FB_ACCESS_TOKEN=None, PUBLIC_BASE_URL=None)
        assert "IG_USER_ID" not in insta._missing_graph_fields()
        assert "FB_ACCESS_TOKEN" in insta._missing_graph_fields()


class TestTekliUpload:
    def test_graph_eksikken_legacy_ye_dusmez(self, graph_kapali, sahte_gorsel, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI="0")

        ok, mesaj = insta.login_and_upload(sahte_gorsel, "caption")

        assert ok is False
        assert "Graph API kurulumu tamamlanmamis" in mesaj

    def test_hata_mesaji_eksik_alanlari_soyler(self, graph_kapali, sahte_gorsel, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI="0")

        _, mesaj = insta.login_and_upload(sahte_gorsel, "caption")

        assert "IG_USER_ID" in mesaj
        assert "FB_ACCESS_TOKEN" in mesaj

    def test_hata_mesaji_cikis_yolunu_gosterir(self, graph_kapali, sahte_gorsel, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI="0")

        _, mesaj = insta.login_and_upload(sahte_gorsel, "caption")

        assert "ALLOW_LEGACY_INSTAGRAPI" in mesaj
        assert "kullanim sartlarina" in mesaj.lower()


class TestCarouselUpload:
    def test_graph_eksikken_legacy_ye_dusmez(self, graph_kapali, sahte_gorsel, tmp_env):
        tmp_env(ALLOW_LEGACY_INSTAGRAPI="0")

        ok, mesaj = insta.login_and_upload_album([sahte_gorsel], "caption")

        assert ok is False
        assert "ALLOW_LEGACY_INSTAGRAPI" in mesaj

    def test_bos_liste_erken_doner(self, graph_kapali):
        ok, mesaj = insta.login_and_upload_album([], "caption")

        assert ok is False
        assert "bo" in mesaj.lower()


class TestUyariMetni:
    def test_tos_riski_aciklanir(self):
        assert "kullanim sartlarina aykiridir" in insta.LEGACY_WARNING.lower()
        assert "instagrapi" in insta.LEGACY_WARNING.lower()

    def test_gerekli_graph_alanlari_tanimli(self):
        assert insta.GRAPH_REQUIRED_FIELDS == [
            "IG_USER_ID",
            "FB_ACCESS_TOKEN",
            "PUBLIC_BASE_URL",
        ]


class TestGraphAktifken:
    def test_graph_alanlari_doluysa_etkin(self, tmp_env):
        tmp_env(IG_USER_ID="123", FB_ACCESS_TOKEN="abc")
        assert insta._is_graph_api_enabled() is True

    def test_tek_alan_eksikse_etkin_degil(self, tmp_env):
        tmp_env(IG_USER_ID="123", FB_ACCESS_TOKEN=None)
        assert insta._is_graph_api_enabled() is False

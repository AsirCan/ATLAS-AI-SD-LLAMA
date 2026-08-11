"""core/runtime/api_auth.py — API token uretimi ve dogrulamasi."""

import os

import pytest

from core.runtime import api_auth


def test_header_adi_sabit():
    assert api_auth.HEADER_NAME == "X-Atlas-Token"


class TestIsAuthorized:
    def test_dogru_token_kabul_edilir(self):
        assert api_auth.is_authorized("gizli", "gizli") is True

    def test_yanlis_token_reddedilir(self):
        assert api_auth.is_authorized("yanlis", "gizli") is False

    @pytest.mark.parametrize("provided", ["", None])
    def test_bos_token_reddedilir(self, provided):
        assert api_auth.is_authorized(provided, "gizli") is False

    def test_beklenen_token_yoksa_reddedilir(self):
        # Token kurulu degilse hicbir sey yetkili sayilmaz.
        assert api_auth.is_authorized("herhangi", "") is False

    def test_bosluklar_kirpilir(self):
        assert api_auth.is_authorized("  gizli  ", "gizli") is True

    def test_kismi_eslesme_yetmez(self):
        assert api_auth.is_authorized("gizli", "gizlidir") is False
        assert api_auth.is_authorized("giz", "gizli") is False


class TestTokenUretimi:
    def test_token_yoksa_uretilir_ve_env_dosyasina_yazilir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ATLAS_API_TOKEN", raising=False)

        token = api_auth.get_or_create_api_token()

        assert len(token) >= 32
        env_content = (tmp_path / ".env").read_text(encoding="utf-8")
        assert f"ATLAS_API_TOKEN={token}" in env_content

    def test_mevcut_token_korunur(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ATLAS_API_TOKEN", raising=False)
        (tmp_path / ".env").write_text("ATLAS_API_TOKEN=zaten-vardi\n", encoding="utf-8")

        assert api_auth.get_or_create_api_token() == "zaten-vardi"

    def test_uretim_diger_env_satirlarini_bozmaz(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ATLAS_API_TOKEN", raising=False)
        (tmp_path / ".env").write_text(
            "# yorum\nFB_APP_ID=123\nIG_USER_ID=456\n", encoding="utf-8"
        )

        api_auth.get_or_create_api_token()

        content = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "FB_APP_ID=123" in content
        assert "IG_USER_ID=456" in content
        assert "# yorum" in content

    def test_uretilen_tokenlar_benzersiz(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ATLAS_API_TOKEN", raising=False)
        tokens = set()
        for i in range(5):
            sub = tmp_path / str(i)
            sub.mkdir()
            monkeypatch.chdir(sub)
            os.environ.pop("ATLAS_API_TOKEN", None)
            tokens.add(api_auth.get_or_create_api_token())
        assert len(tokens) == 5


class TestTokenOkuma:
    def test_process_ortami_env_dosyasindan_once_gelir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("ATLAS_API_TOKEN=dosyadan\n", encoding="utf-8")
        monkeypatch.setenv("ATLAS_API_TOKEN", "ortamdan")

        assert api_auth.read_api_token() == "ortamdan"

    def test_env_dosyasindan_okur(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ATLAS_API_TOKEN", raising=False)
        (tmp_path / ".env").write_text("ATLAS_API_TOKEN=dosyadan\n", encoding="utf-8")

        assert api_auth.read_api_token() == "dosyadan"

    def test_hicbir_kaynak_yoksa_bos_doner(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("ATLAS_API_TOKEN", raising=False)

        assert api_auth.read_api_token() == ""

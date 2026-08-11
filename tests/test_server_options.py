"""
web/backend/main.py — sunucu calisma secenekleri (issue #8).

reload'un varsayilan olarak KAPALI olmasi kritik: acik oldugunda uzun suren
ajan/video isleri yeniden baslatmada sessizce kayboluyor.
"""

import main as backend
import pytest

pytestmark = pytest.mark.backend


class TestReload:
    def test_varsayilan_kapali(self, tmp_env):
        tmp_env(DEV_RELOAD=None)
        assert backend.server_options()["reload"] is False

    def test_sifir_degeri_kapali(self, tmp_env):
        tmp_env(DEV_RELOAD="0")
        assert backend.server_options()["reload"] is False

    def test_bir_degeri_acar(self, tmp_env):
        tmp_env(DEV_RELOAD="1")
        assert backend.server_options()["reload"] is True

    def test_bosluk_kirpilir(self, tmp_env):
        tmp_env(DEV_RELOAD=" 1 ")
        assert backend.server_options()["reload"] is True

    @pytest.mark.parametrize("value", ["true", "yes", "on", "evet", ""])
    def test_diger_degerler_kapali_sayilir(self, tmp_env, value):
        """Yalnizca "1" acar; belirsiz degerler guvenli tarafta kalir."""
        tmp_env(DEV_RELOAD=value)
        assert backend.server_options()["reload"] is False


class TestHostPort:
    def test_varsayilan_yerel(self, tmp_env):
        tmp_env(BACKEND_HOST=None, BACKEND_PORT=None)
        options = backend.server_options()

        # Backend asla tunele acilmamali; varsayilan loopback kalmali.
        assert options["host"] == "127.0.0.1"
        assert options["port"] == 8000

    def test_ortamdan_gecersiz_kilinabilir(self, tmp_env):
        tmp_env(BACKEND_HOST="0.0.0.0", BACKEND_PORT="9001")
        options = backend.server_options()

        assert options["host"] == "0.0.0.0"
        assert options["port"] == 9001

    def test_port_tam_sayiya_cevrilir(self, tmp_env):
        tmp_env(BACKEND_PORT="8080")
        assert backend.server_options()["port"] == 8080
        assert isinstance(backend.server_options()["port"], int)

"""
web/backend/main.py — API token korumasi, CORS ve sir sizintisi.

Bu testler PR #12'deki guvenlik degisikliklerinin regresyona ugramamasini
garanti eder. TestClient lifespan olaylarini tetiklemez; Ollama/SD
baslatilmaz.
"""

import pytest
from fastapi.testclient import TestClient

import main as backend

pytestmark = pytest.mark.backend


@pytest.fixture
def client():
    return TestClient(backend.app)


KORUNAN_GET_UCLARI = [
    "/api/agent/progress",
    "/api/imgbb/config",
    "/api/instagram/graph-config",
    "/api/progress",
]

KORUNAN_POST_UCLARI = [
    "/api/chat",
    "/api/agent/run",
    "/api/agent/cancel",
    "/api/instagram/graph-config",
    "/api/imgbb/config",
]


class TestTokenKorumasi:
    @pytest.mark.parametrize("path", KORUNAN_GET_UCLARI)
    def test_tokensiz_get_reddedilir(self, client, path):
        assert client.get(path).status_code == 401

    @pytest.mark.parametrize("path", KORUNAN_POST_UCLARI)
    def test_tokensiz_post_reddedilir(self, client, path):
        assert client.post(path, json={}).status_code == 401

    def test_canli_yayin_ucu_tokensiz_calismaz(self, client):
        """En riskli uc: gercek Instagram paylasimi tetikliyor."""
        r = client.post("/api/agent/run", params={"live": "true"})
        assert r.status_code == 401

    def test_yanlis_token_reddedilir(self, client):
        r = client.get("/api/agent/progress", headers={"X-Atlas-Token": "yanlis"})
        assert r.status_code == 401

    def test_dogru_token_kabul_edilir(self, client, api_token):
        r = client.get("/api/agent/progress", headers={"X-Atlas-Token": api_token})
        assert r.status_code == 200

    def test_query_parametresi_ile_de_calisir(self, client, api_token):
        r = client.get("/api/agent/progress", params={"token": api_token})
        assert r.status_code == 200

    def test_401_cevabi_aciklayici(self, client):
        r = client.get("/api/agent/progress")
        assert "token" in r.json()["detail"].lower()


class TestKorumasizYollar:
    """Frontend'in <img> etiketleri ve saglik kontrolu bozulmamali."""

    def test_kok_erisilebilir(self, client):
        assert client.get("/").status_code == 200

    def test_robots_erisilebilir(self, client):
        assert client.get("/robots.txt").status_code == 200


class TestCORS:
    def test_yildiz_origin_kaldirildi(self):
        assert "*" not in backend.ALLOWED_ORIGINS

    def test_vite_origini_izinli(self):
        assert "http://127.0.0.1:5173" in backend.ALLOWED_ORIGINS
        assert "http://localhost:5173" in backend.ALLOWED_ORIGINS

    def test_preflight_token_istemez(self, client):
        r = client.options(
            "/api/chat",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-atlas-token",
            },
        )
        assert r.status_code == 200

    def test_preflight_token_basligina_izin_verir(self, client):
        r = client.options(
            "/api/chat",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-atlas-token",
            },
        )
        allowed = r.headers.get("access-control-allow-headers", "").lower()
        assert "x-atlas-token" in allowed

    def test_yabanci_origine_izin_yok(self, client):
        r = client.options(
            "/api/chat",
            headers={
                "Origin": "http://kotu-site.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in r.headers

    def test_izinli_origine_izin_var(self, client):
        r = client.options(
            "/api/chat",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


class TestSirSizintisi:
    def test_imgbb_anahtari_dondurulmez(self, client, api_token, monkeypatch):
        monkeypatch.setattr(
            backend, "_read_env_values",
            lambda: {"IMGBB_API_KEY": "cok-gizli-anahtar-9999"},
        )

        body = client.get("/api/imgbb/config", headers={"X-Atlas-Token": api_token}).json()

        assert "imgbb_api_key" not in body
        assert "cok-gizli-anahtar-9999" not in str(body)
        assert body["configured"] is True
        assert body["masked"].endswith("9999")

    def test_graph_config_sirlari_dondurmez(self, client, api_token, monkeypatch, tmp_path):
        env = tmp_path / ".env"
        env.write_text(
            "FB_APP_SECRET=gizli-secret\nFB_ACCESS_TOKEN=gizli-token\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        body = client.get(
            "/api/instagram/graph-config", headers={"X-Atlas-Token": api_token}
        ).json()

        assert "gizli-secret" not in str(body)
        assert "gizli-token" not in str(body)


class TestMaskeleme:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("ABCD1234EFGH", "********EFGH"),
            ("", ""),
            ("ab", "**"),
            ("abcd", "****"),
            ("abcde", "*bcde"),
        ],
    )
    def test_maskeleme(self, value, expected):
        assert backend._mask_secret(value) == expected

    def test_none_guvenli(self):
        assert backend._mask_secret(None) == ""

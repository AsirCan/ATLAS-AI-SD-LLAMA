"""
web/backend/image_server.py — tunele acilan servisin izolasyonu.

Bu servis internete aciliyor. Bu yuzden UZERINDE HICBIR /api UCU OLMAMALI;
issue #1'in cozumunun temeli bu.
"""

import pytest
from fastapi.testclient import TestClient

import image_server

pytestmark = pytest.mark.backend


@pytest.fixture
def client():
    return TestClient(image_server.app)


def test_saglik_kontrolu(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text == "ok"


def test_kayitli_rotalar_sadece_statik():
    paths = {str(getattr(route, "path", "")) for route in image_server.app.routes}
    assert paths == {"/images", "/healthz", "/robots.txt"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/chat",
        "/api/agent/run",
        "/api/imgbb/config",
        "/api/instagram/graph-config",
        "/api/instagram/upload",
        "/api/tts",
    ],
)
def test_api_uclari_burada_yok(client, path):
    assert client.post(path, json={}).status_code == 404
    assert client.get(path).status_code == 404


def test_api_rotasi_hic_kayitli_degil():
    for route in image_server.app.routes:
        assert not str(getattr(route, "path", "")).startswith("/api")


def test_openapi_kapali(client):
    """Dokumantasyon uclari disariya acik servisde kapali olmali."""
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_robots_indekslemeyi_engeller(client):
    assert "Disallow: /" in client.get("/robots.txt").text


def test_images_salt_okunur(client):
    """Statik mount yalnizca GET/HEAD kabul etmeli."""
    assert client.post("/images/x.png", content=b"veri").status_code in (404, 405)
    assert client.put("/images/x.png", content=b"veri").status_code in (404, 405)
    assert client.delete("/images/x.png").status_code in (404, 405)


def test_dizin_disina_cikilamaz(client):
    """Path traversal denemesi dosya sistemine ulasmamali."""
    r = client.get("/images/../../.env")
    assert r.status_code in (404, 403, 400)

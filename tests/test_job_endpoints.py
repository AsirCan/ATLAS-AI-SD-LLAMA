"""
web/backend/main.py — job-ID tabanli uclar (issue #3).

Eskiden /api/agent/run ikinci kez cagrildiginda ilerleme durumu birincinin
ustune yaziliyordu. Artik kayit defteri catismayi backend'de reddediyor.
"""

import main as backend
import pytest
from fastapi.testclient import TestClient

from core.runtime import jobs

pytestmark = pytest.mark.backend


@pytest.fixture
def client():
    return TestClient(backend.app)


@pytest.fixture(autouse=True)
def temiz_kayit():
    """Her test bos kayit defteriyle baslasin."""
    jobs.registry.clear()
    yield
    jobs.registry.clear()


@pytest.fixture
def auth(api_token):
    return {"X-Atlas-Token": api_token}


@pytest.fixture
def no_background(monkeypatch):
    """
    Arka plan isini calistirma; yalnizca uc davranisini test ediyoruz.
    Gercek is Ollama/SD gerektirirdi.
    """
    from fastapi import BackgroundTasks

    monkeypatch.setattr(BackgroundTasks, "add_task", lambda self, *a, **k: None)


class TestIsBaslatma:
    def test_ajan_baslatinca_job_id_doner(self, client, auth, no_background):
        body = client.post("/api/agent/run", headers=auth).json()

        assert body["success"] is True
        assert body["job_id"]

    def test_carousel_baslatinca_job_id_doner(self, client, auth, no_background):
        body = client.post("/api/carousel/generate", headers=auth).json()
        assert body["job_id"]

    def test_video_baslatinca_job_id_doner(self, client, auth, no_background):
        body = client.post("/api/news/video_generate", headers=auth).json()
        assert body["job_id"]

    def test_her_calistirma_yeni_kimlik_uretir(self, client, auth, no_background):
        first = client.post("/api/agent/run", headers=auth).json()["job_id"]
        jobs.registry.get(first).finish("done")
        second = client.post("/api/agent/run", headers=auth).json()["job_id"]

        assert first != second


class TestCatisma:
    def test_ikinci_ajan_reddedilir(self, client, auth, no_background):
        client.post("/api/agent/run", headers=auth)

        body = client.post("/api/agent/run", headers=auth).json()

        assert body["success"] is False
        assert body["active_job"] == "agent"

    def test_ajan_calisirken_video_reddedilir(self, client, auth, no_background):
        client.post("/api/agent/run", headers=auth)

        body = client.post("/api/news/video_generate", headers=auth).json()

        assert body["success"] is False
        assert body["active_job"] == "agent"

    def test_carousel_calisirken_ajan_reddedilir(self, client, auth, no_background):
        client.post("/api/carousel/generate", headers=auth)

        body = client.post("/api/agent/run", headers=auth).json()

        assert body["success"] is False
        assert body["active_job"] == "carousel"

    def test_catisma_cevabi_aktif_kimligi_verir(self, client, auth, no_background):
        active_id = client.post("/api/agent/run", headers=auth).json()["job_id"]

        body = client.post("/api/news/video_generate", headers=auth).json()

        assert body["active_job_id"] == active_id

    def test_bitmis_isten_sonra_yeni_is_kabul_edilir(self, client, auth, no_background):
        first = client.post("/api/agent/run", headers=auth).json()["job_id"]
        jobs.registry.get(first).finish("done")

        assert client.post("/api/news/video_generate", headers=auth).json()["success"] is True


class TestIlerlemeSorgusu:
    def test_bos_kayitta_idle_doner(self, client, auth):
        body = client.get("/api/agent/progress", headers=auth).json()

        assert body["status"] == "idle"
        assert body["job_id"] is None

    def test_job_id_ile_sorgulanir(self, client, auth, no_background):
        job_id = client.post("/api/agent/run", headers=auth).json()["job_id"]
        jobs.registry.get(job_id).set_stage("visual", 55, "cizim")

        body = client.get(f"/api/agent/progress/{job_id}", headers=auth).json()

        assert body["job_id"] == job_id
        assert body["percent"] == 55
        assert body["stage"] == "visual"

    def test_job_id_siz_uc_hala_calisir(self, client, auth, no_background):
        """Geriye donuk uyumluluk: eski frontend kimlik gondermiyor."""
        job_id = client.post("/api/agent/run", headers=auth).json()["job_id"]

        body = client.get("/api/agent/progress", headers=auth).json()

        assert body["job_id"] == job_id

    def test_isler_birbirinin_ilerlemesini_bozmaz(self, client, auth, no_background):
        agent_id = client.post("/api/agent/run", headers=auth).json()["job_id"]
        jobs.registry.get(agent_id).set_stage("visual", 55, "ajan isi")
        jobs.registry.get(agent_id).finish("done")

        video_id = client.post("/api/news/video_generate", headers=auth).json()["job_id"]
        jobs.registry.get(video_id).set_stage("encoding", 30, "video isi")

        agent_body = client.get(f"/api/agent/progress/{agent_id}", headers=auth).json()
        video_body = client.get(f"/api/news/video_progress?job_id={video_id}", headers=auth).json()

        assert agent_body["percent"] == 100
        assert agent_body["current_task"] == "ajan isi"
        assert video_body["percent"] == 30
        assert video_body["current_task"] == "video isi"

    def test_ilerleme_ucu_token_ister(self, client):
        assert client.get("/api/agent/progress").status_code == 401


class TestIptal:
    def test_calisan_is_iptal_edilir(self, client, auth, no_background, monkeypatch):
        monkeypatch.setattr(backend, "_interrupt_stable_diffusion", lambda: None)
        job_id = client.post("/api/agent/run", headers=auth).json()["job_id"]

        body = client.post(f"/api/agent/cancel/{job_id}", headers=auth).json()

        assert body["success"] is True
        assert jobs.registry.get(job_id).cancel_requested is True

    def test_calisan_is_yoksa_hata(self, client, auth):
        body = client.post("/api/agent/cancel", headers=auth).json()
        assert body["success"] is False

    def test_iptal_yalnizca_hedef_ise_uygulanir(self, client, auth, no_background, monkeypatch):
        monkeypatch.setattr(backend, "_interrupt_stable_diffusion", lambda: None)
        first = client.post("/api/agent/run", headers=auth).json()["job_id"]
        jobs.registry.get(first).finish("done")
        second = client.post("/api/news/video_generate", headers=auth).json()["job_id"]

        client.post(f"/api/agent/cancel/{second}", headers=auth)

        assert jobs.registry.get(first).cancel_requested is False
        assert jobs.registry.get(second).cancel_requested is True

    def test_iptal_sd_kesintisini_tetikler(self, client, auth, no_background, monkeypatch):
        calls = []
        monkeypatch.setattr(backend, "_interrupt_stable_diffusion", lambda: calls.append(1))
        job_id = client.post("/api/agent/run", headers=auth).json()["job_id"]

        client.post(f"/api/agent/cancel/{job_id}", headers=auth)

        assert calls == [1]

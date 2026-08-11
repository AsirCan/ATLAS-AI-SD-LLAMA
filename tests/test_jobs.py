"""
core/runtime/jobs.py — job-ID tabanli is takibi (issue #3).

Onceki tasarimda ilerleme global sozluklerdeydi: iki is ayni anda
baslatildiginda ikincisi birincinin ustune yaziyor, cancel bayragi yanlis
ise uygulaniyordu. Bu testler o davranisin geri gelmemesini garanti eder.
"""

import time

import pytest

from core.runtime import jobs
from core.runtime.jobs import Job, JobConflict, JobRegistry


@pytest.fixture
def registry():
    return JobRegistry()


class TestJob:
    def test_her_isin_benzersiz_kimligi_var(self):
        ids = {Job(kind="agent").id for _ in range(20)}
        assert len(ids) == 20

    def test_baslangicta_aktif(self):
        assert Job(kind="agent").is_active is True

    def test_bitmis_is_aktif_degil(self):
        job = Job(kind="agent")
        job.finish("done")
        assert job.is_active is False

    def test_iptal_ediliyor_durumu_aktif_sayilir(self):
        """Iptal beklerken is hala GPU'yu tutuyor; yeni is baslamamali."""
        job = Job(kind="agent")
        job.status = "cancelling"
        assert job.is_active is True

    def test_done_yuzdeyi_yuze_cekiyor(self):
        job = Job(kind="agent")
        job.set_stage("visual", 55, "cizim")
        job.finish("done")
        assert job.percent == 100

    def test_iptal_yuzdeyi_zorlamaz(self):
        job = Job(kind="agent")
        job.set_stage("visual", 55, "cizim")
        job.finish("cancelled")
        assert job.percent == 55

    def test_yuzde_sinirlanir(self):
        job = Job(kind="agent")
        job.set_stage("x", 250, "t")
        assert job.percent == 100
        job.set_stage("x", -20, "t")
        assert job.percent == 0

    def test_loglar_zaman_damgali(self):
        job = Job(kind="agent")
        job.log("merhaba")
        assert job.logs[0].endswith("merhaba")
        assert job.logs[0].startswith("[")

    def test_log_listesi_sinirlanir(self):
        """Onceki tasarimda log listesi hic kirpilmiyordu."""
        job = Job(kind="agent")
        for i in range(jobs.MAX_LOG_LINES + 250):
            job.log(f"satir {i}")

        assert len(job.logs) == jobs.MAX_LOG_LINES
        # En yeni satirlar korunmali
        assert job.logs[-1].endswith(f"satir {jobs.MAX_LOG_LINES + 249}")

    def test_sozluge_cevrilir(self):
        job = Job(kind="video")
        data = job.to_dict()

        assert data["job_id"] == job.id
        assert data["kind"] == "video"
        assert "logs" in data


class TestTekIsKurali:
    def test_ilk_is_olusturulur(self, registry):
        job = registry.create("agent")
        assert job.kind == "agent"

    def test_ikinci_is_reddedilir(self, registry):
        """En kritik test: iki is ayni anda calisamaz (tek GPU)."""
        first = registry.create("agent")

        with pytest.raises(JobConflict) as exc:
            registry.create("video")

        assert exc.value.active_kind == "agent"
        assert exc.value.active_job_id == first.id

    def test_farkli_turler_de_catisir(self, registry):
        registry.create("carousel")
        with pytest.raises(JobConflict):
            registry.create("agent")

    def test_ayni_tur_de_catisir(self, registry):
        registry.create("agent")
        with pytest.raises(JobConflict):
            registry.create("agent")

    def test_bitmis_isten_sonra_yeni_is_baslar(self, registry):
        first = registry.create("agent")
        first.finish("done")

        second = registry.create("video")
        assert second.id != first.id

    def test_iptal_beklerken_yeni_is_baslamaz(self, registry):
        job = registry.create("agent")
        registry.request_cancel(job.id)

        with pytest.raises(JobConflict):
            registry.create("video")

    def test_catisma_mesaji_hangi_isin_calistigini_soyler(self, registry):
        registry.create("carousel")
        with pytest.raises(JobConflict, match="Carousel"):
            registry.create("agent")


class TestDurumIzolasyonu:
    def test_isler_birbirinin_durumunu_bozmaz(self, registry):
        """Eski global sozluk tasariminin asil hatasi buydu."""
        first = registry.create("agent")
        first.set_stage("visual", 55, "birinci is")
        first.log("birinci log")
        first.finish("done")

        second = registry.create("video")
        second.set_stage("encoding", 30, "ikinci is")
        second.log("ikinci log")

        assert first.percent == 100
        assert first.current_task == "birinci is"
        assert len(first.logs) == 1
        assert "birinci log" in first.logs[0]

        assert second.percent == 30
        assert second.current_task == "ikinci is"
        assert len(second.logs) == 1
        assert "ikinci log" in second.logs[0]

    def test_iptal_bayragi_yalnizca_hedef_ise_uygulanir(self, registry):
        first = registry.create("agent")
        first.finish("done")
        second = registry.create("video")

        registry.request_cancel(second.id)

        assert second.cancel_requested is True
        assert first.cancel_requested is False


class TestSnapshot:
    def test_kayit_bossa_idle_doner(self, registry):
        snap = registry.snapshot(kind="agent")

        assert snap["status"] == "idle"
        assert snap["job_id"] is None
        assert snap["logs"] == []

    def test_bilinmeyen_job_id_idle_doner(self, registry):
        assert registry.snapshot("olmayan-kimlik")["status"] == "idle"

    def test_job_id_ile_dogru_is_doner(self, registry):
        job = registry.create("agent")
        job.set_stage("news", 20, "haber")

        snap = registry.snapshot(job.id)

        assert snap["job_id"] == job.id
        assert snap["percent"] == 20

    def test_job_id_yoksa_en_son_is_doner(self, registry):
        old = registry.create("agent")
        old.finish("done")
        new = registry.create("agent")

        assert registry.snapshot(kind="agent")["job_id"] == new.id

    def test_tur_filtresi_calisir(self, registry):
        agent = registry.create("agent")
        agent.finish("done")
        video = registry.create("video")
        video.finish("done")

        assert registry.snapshot(kind="agent")["job_id"] == agent.id
        assert registry.snapshot(kind="video")["job_id"] == video.id

    def test_idle_snapshot_kopyalanir(self, registry):
        """Cagiran taraf sozlugu degistirse sabit bozulmamali."""
        snap = registry.snapshot(kind="agent")
        snap["status"] = "kurcalandi"

        assert registry.snapshot(kind="agent")["status"] == "idle"


class TestIptal:
    def test_calisan_is_iptal_edilir(self, registry):
        job = registry.create("agent")

        cancelled = registry.request_cancel(job.id)

        assert cancelled is job
        assert job.cancel_requested is True
        assert job.status == "cancelling"

    def test_bitmis_is_iptal_edilemez(self, registry):
        job = registry.create("agent")
        job.finish("done")

        assert registry.request_cancel(job.id) is None

    def test_olmayan_is_iptal_edilemez(self, registry):
        assert registry.request_cancel("yok-boyle-kimlik") is None

    def test_kayit_bossa_none_doner(self, registry):
        assert registry.request_cancel(kind="agent") is None

    def test_job_id_yoksa_en_son_is_iptal_edilir(self, registry):
        job = registry.create("agent")

        assert registry.request_cancel(kind="agent") is job


class TestTemizlik:
    def test_eski_bitmis_isler_dusurulur(self):
        registry = JobRegistry(ttl_seconds=60)
        job = registry.create("agent")
        job.finish("done")
        job.finished_at = time.time() - 120

        assert registry.prune() == 1
        assert registry.get(job.id) is None

    def test_yeni_bitmis_isler_korunur(self):
        registry = JobRegistry(ttl_seconds=3600)
        job = registry.create("agent")
        job.finish("done")

        assert registry.prune() == 0
        assert registry.get(job.id) is not None

    def test_calisan_is_dusurulmez(self):
        registry = JobRegistry(ttl_seconds=0)
        job = registry.create("agent")
        job.created_at = time.time() - 99999

        assert registry.prune() == 0
        assert registry.get(job.id) is not None


class TestEsZamanlilik:
    def test_ayni_anda_tek_is_olusur(self, registry):
        """
        Yirmi thread ayni anda is baslatmaya calissa bile yalnizca biri
        basarili olmali; kilit calismazsa birden fazla is olusurdu.
        """
        import threading

        created = []
        errors = []
        barrier = threading.Barrier(20)

        def worker():
            barrier.wait()
            try:
                created.append(registry.create("agent"))
            except JobConflict:
                errors.append(1)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(created) == 1
        assert len(errors) == 19

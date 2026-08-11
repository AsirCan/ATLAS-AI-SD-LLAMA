"""
core/pipeline/orchestrator.py — pipeline akisi ve guard'lar.

Orchestrator'in en kritik ozelligi: her adimdan sonra invariant kontrolu yapip
eksik ciktida ILERLEMEMESI. Bu testler her guard'i ayri ayri tetikler.
"""

from datetime import datetime

import pytest

from core.agents.base import CancelledError
from core.pipeline import orchestrator as orch_module
from core.pipeline.orchestrator import Orchestrator


class StubAgent:
    """State'i verilen fonksiyonla degistiren sahte agent."""

    def __init__(self, mutate=None, raises=None):
        self.mutate = mutate
        self.raises = raises
        self.called = False

    def process(self, state):
        self.called = True
        if self.raises:
            raise self.raises
        if self.mutate:
            self.mutate(state)
        return state

    def set_log_callback(self, _cb):
        pass

    def set_cancel_checker(self, _checker):
        pass


def build(dry_run=True, **agents):
    """
    Gercek agent'lari stub'larla degistirilmis bir Orchestrator kurar.
    Varsayilan: her adim basariyla tamamlanir (mutlu yol).
    """
    o = Orchestrator(dry_run=dry_run)

    defaults = {
        "news_agent": StubAgent(lambda s: setattr(s, "news_items", [{"title": "Haber"}])),
        "risk_agent": StubAgent(lambda s: setattr(s, "safe_news_items", [{"title": "Haber"}])),
        "visual_agent": StubAgent(lambda s: setattr(s, "generated_images", ["img.png"])),
        "caption_agent": StubAgent(lambda s: setattr(s, "final_caption", "Bir caption")),
        "scheduler_agent": StubAgent(lambda s: setattr(s, "scheduled_time", datetime(2026, 1, 1))),
    }
    defaults.update(agents)

    for name, agent in defaults.items():
        setattr(o, name, agent)
    return o


@pytest.fixture(autouse=True)
def _no_news_memory_write(monkeypatch):
    """Testler gercek 'kullanilmis haber' deposuna yazmasin."""
    monkeypatch.setattr(orch_module, "mark_used_titles", lambda *_a, **_k: None)


@pytest.fixture
def upload_spy(monkeypatch):
    calls = []

    def fake_upload(image, caption):
        calls.append((image, caption))
        return True, "yuklendi"

    monkeypatch.setattr(orch_module, "login_and_upload", fake_upload)
    return calls


class TestGuardlar:
    def test_haber_yoksa_durur(self):
        o = build(news_agent=StubAgent(lambda s: None))
        state = o.run_pipeline()

        assert state.safe_news_items == []
        assert o.risk_agent.called is False

    def test_guvenli_haber_yoksa_durur(self):
        o = build(risk_agent=StubAgent(lambda s: None))
        state = o.run_pipeline()

        assert state.generated_images == []
        assert o.visual_agent.called is False

    def test_gorsel_yoksa_durur(self):
        o = build(visual_agent=StubAgent(lambda s: None))
        state = o.run_pipeline()

        assert state.final_caption is None
        assert o.caption_agent.called is False

    def test_caption_yoksa_durur(self):
        o = build(caption_agent=StubAgent(lambda s: None))
        state = o.run_pipeline()

        assert state.scheduled_time is None
        assert o.scheduler_agent.called is False

    def test_zamanlama_yoksa_yayinlanmaz(self, upload_spy):
        o = build(dry_run=False, scheduler_agent=StubAgent(lambda s: None))
        state = o.run_pipeline()

        assert upload_spy == []
        assert state.upload_status == {}


class TestMutluYol:
    def test_dry_run_upload_yapmaz(self, upload_spy):
        o = build(dry_run=True)
        state = o.run_pipeline()

        assert upload_spy == []
        assert state.upload_status["success"] is True
        assert state.upload_status["message"] == "Dry Run OK"

    def test_live_mod_upload_yapar(self, upload_spy):
        o = build(dry_run=False)
        state = o.run_pipeline()

        assert upload_spy == [("img.png", "Bir caption")]
        assert state.upload_status["success"] is True

    def test_tum_adimlar_sirayla_calisir(self):
        o = build()
        o.run_pipeline()

        for name in ("news_agent", "risk_agent", "visual_agent", "caption_agent", "scheduler_agent"):
            assert getattr(o, name).called is True, f"{name} calismadi"

    def test_basarili_gorselden_sonra_haber_kullanildi_isaretlenir(self, monkeypatch):
        marked = []
        monkeypatch.setattr(
            orch_module, "mark_used_titles",
            lambda titles, source=None: marked.append((list(titles), source)),
        )

        build().run_pipeline()

        assert marked == [(["Haber"], "agent")]


class TestIptal:
    def test_baslangicta_iptal(self):
        o = build()
        o.set_cancel_checker(lambda: True)

        state = o.run_pipeline()

        assert state.upload_status == {"success": False, "message": "Cancelled"}
        assert o.news_agent.called is False

    def test_ortada_iptal_upload_engeller(self, upload_spy):
        flag = {"cancel": False}

        def cancel_after_news(state):
            state.news_items = [{"title": "Haber"}]
            flag["cancel"] = True

        o = build(dry_run=False, news_agent=StubAgent(cancel_after_news))
        o.set_cancel_checker(lambda: flag["cancel"])

        state = o.run_pipeline()

        assert upload_spy == []
        assert state.upload_status["message"] == "Cancelled"

    def test_agent_icinden_gelen_iptal_yakalanir(self):
        o = build(visual_agent=StubAgent(raises=CancelledError("SD sirasinda")))

        state = o.run_pipeline()

        assert state.upload_status == {"success": False, "message": "Cancelled"}

    def test_iptal_checker_bozuksa_pipeline_devam_eder(self, upload_spy):
        def broken():
            raise RuntimeError("checker bozuk")

        o = build(dry_run=True)
        o.set_cancel_checker(broken)

        state = o.run_pipeline()

        assert state.upload_status["success"] is True


class TestLoglama:
    def test_log_callback_tetiklenir(self):
        logs = []
        o = build()
        o.set_logger(logs.append)

        o.run_pipeline()

        assert any("Step 1/6" in line for line in logs)
        assert any("Pipeline complete" in line for line in logs)

    def test_guard_hatasi_loglanir(self):
        logs = []
        o = build(news_agent=StubAgent(lambda s: None))
        o.set_logger(logs.append)

        o.run_pipeline()

        assert any("GUARD FAILURE" in line for line in logs)


def test_upload_hatasi_state_e_yansir(monkeypatch):
    monkeypatch.setattr(
        orch_module, "login_and_upload",
        lambda image, caption: (False, "Graph token gecersiz"),
    )

    state = build(dry_run=False).run_pipeline()

    assert state.upload_status["success"] is False
    assert "Graph token gecersiz" in state.upload_status["message"]


def test_state_ozeti_serilestirilebilir():
    state = build().run_pipeline()
    summary = state.to_dict()

    assert summary["safe_news_count"] == 1
    assert summary["generated_images_count"] == 1
    assert summary["final_caption_preview"] == "Bir caption"

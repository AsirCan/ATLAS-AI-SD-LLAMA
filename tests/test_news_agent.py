"""
core/agents/news_agent.py — haber toplama, filtreleme ve skorlama.

Skorlama kasitli olarak iki parcali: LLM yalnizca ANALIZ (0-10 puanlar)
uretir, KARAR (agirlikli formul ve siralama) Python tarafinda verilir.
Testler bu ayrimin korundugunu dogrular.
"""

import types

import pytest

from core.agents import news_agent as na_module
from core.agents.news_agent import NewsAgent, _find_keyword_hit
from core.errors import LLMUnavailableError
from core.pipeline.state import PipelineState


def entry(title, summary="ozet", link="http://ornek/1"):
    return types.SimpleNamespace(title=title, summary=summary, link=link)


@pytest.fixture
def feed(monkeypatch):
    """feedparser.parse ciktisini kontrol etmek icin."""

    def _set(entries):
        monkeypatch.setattr(
            na_module.feedparser,
            "parse",
            lambda *_a, **_k: types.SimpleNamespace(entries=entries),
        )

    return _set


@pytest.fixture(autouse=True)
def bos_hafiza(monkeypatch):
    """Kullanilmis haber deposu her testte bos baslasin."""
    monkeypatch.setattr(na_module, "prune_expired", lambda *_a, **_k: None)
    monkeypatch.setattr(na_module, "get_used_title_set", lambda *_a, **_k: set())


class TestKeywordHit:
    def test_kelime_siniri_korunur(self):
        assert _find_keyword_hit("warehouse sale", ["war"]) is None
        assert _find_keyword_hit("the war ended", ["war"]) == "war"

    def test_bos_baslik(self):
        assert _find_keyword_hit("", ["war"]) is None


class TestHaberCekme:
    def test_haberler_toplanir(self, feed, fake_llm):
        feed([entry("Yeni kopru acildi"), entry("Bilim insanlari kesif yapti")])
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://ornek/rss"])

        items = agent._fetch_news()

        assert len(items) == 2
        assert items[0]["title"] == "Yeni kopru acildi"

    def test_yasakli_kelime_iceren_haber_elenir(self, feed, fake_llm):
        feed([entry("Deadly attack downtown"), entry("Yeni park acildi")])
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://ornek/rss"])

        titles = [i["title"] for i in agent._fetch_news()]

        assert titles == ["Yeni park acildi"]

    def test_kullanilmis_haber_tekrar_alinmaz(self, feed, fake_llm, monkeypatch):
        monkeypatch.setattr(na_module, "get_used_title_set", lambda *_a, **_k: {"zaten paylasildi"})
        feed([entry("Zaten paylasildi"), entry("Taze haber")])
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://ornek/rss"])

        titles = [i["title"] for i in agent._fetch_news()]

        assert titles == ["Taze haber"]

    def test_kaynak_basina_en_fazla_bes_haber(self, feed, fake_llm):
        feed([entry(f"Haber {i}") for i in range(20)])
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://ornek/rss"])

        assert len(agent._fetch_news()) == 5

    def test_bozuk_kaynak_digerlerini_engellemez(self, fake_llm, monkeypatch):
        def parse(url):
            if "bozuk" in url:
                raise RuntimeError("XML hatali")
            return types.SimpleNamespace(entries=[entry("Calisan kaynak haberi")])

        monkeypatch.setattr(na_module.feedparser, "parse", parse)
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://bozuk/rss", "http://saglam/rss"])

        titles = [i["title"] for i in agent._fetch_news()]

        assert titles == ["Calisan kaynak haberi"]

    def test_bos_kaynak_atlanir(self, feed, fake_llm):
        feed([])
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://ornek/rss"])

        assert agent._fetch_news() == []


class TestSkorlama:
    def test_agirlikli_formul_python_tarafinda(self, fake_llm):
        """final_score = viral*0.6 + emotional*0.4"""
        llm = fake_llm(responses=[{"emotional_score": 10, "viral_potential": 5, "reason": ""}])
        agent = NewsAgent(llm, rss_urls=[])

        scored = agent._score_news([{"title": "T", "summary": "S"}])

        assert scored[0]["final_score"] == pytest.approx(5 * 0.6 + 10 * 0.4)

    def test_viral_puani_daha_agirlikli(self, fake_llm):
        llm = fake_llm(
            responses=[
                {"emotional_score": 0, "viral_potential": 10, "reason": ""},
                {"emotional_score": 10, "viral_potential": 0, "reason": ""},
            ]
        )
        agent = NewsAgent(llm, rss_urls=[])

        scored = agent._score_news([{"title": "Viral", "summary": ""}, {"title": "Duygusal", "summary": ""}])

        assert scored[0]["final_score"] > scored[1]["final_score"]

    def test_eksik_puanlar_sifir_sayilir(self, fake_llm):
        llm = fake_llm(responses=[{"reason": "eksik cevap"}])
        agent = NewsAgent(llm, rss_urls=[])

        scored = agent._score_news([{"title": "T", "summary": "S"}])

        assert scored[0]["final_score"] == 0

    def test_skorlama_hatasi_haberi_atlar(self, fake_llm):
        llm = fake_llm(
            responses=[
                ValueError("LLM cevabi bozuk"),
                {"emotional_score": 5, "viral_potential": 5, "reason": ""},
            ]
        )
        agent = NewsAgent(llm, rss_urls=[])

        scored = agent._score_news([{"title": "Bozuk", "summary": ""}, {"title": "Saglam", "summary": ""}])

        assert [i["title"] for i in scored] == ["Saglam"]

    def test_ollama_baglanti_hatasi_yutulmaz(self, fake_llm):
        llm = fake_llm(responses=[LLMUnavailableError("connection refused")])
        agent = NewsAgent(llm, rss_urls=[])

        with pytest.raises(LLMUnavailableError):
            agent._score_news([{"title": "T", "summary": "S"}])

    def test_orijinal_alanlar_korunur(self, fake_llm):
        llm = fake_llm(responses=[{"emotional_score": 5, "viral_potential": 5, "reason": "iyi"}])
        agent = NewsAgent(llm, rss_urls=[])

        scored = agent._score_news([{"title": "T", "summary": "S", "link": "http://x"}])

        assert scored[0]["link"] == "http://x"
        assert scored[0]["analysis_reason"] == "iyi"


class TestExecute:
    def test_en_yuksek_skorlu_haberler_secilir(self, feed, fake_llm):
        feed([entry("Dusuk"), entry("Yuksek")])
        llm = fake_llm(
            responses=[
                {"emotional_score": 1, "viral_potential": 1, "reason": ""},
                {"emotional_score": 9, "viral_potential": 9, "reason": ""},
            ]
        )
        agent = NewsAgent(llm, rss_urls=["http://ornek/rss"])

        state = agent._execute(PipelineState())

        assert state.news_items[0]["title"] == "Yuksek"

    def test_en_fazla_on_haber(self, feed, fake_llm):
        feed([entry(f"H{i}") for i in range(5)])
        llm = fake_llm(responses=[{"emotional_score": 5, "viral_potential": 5, "reason": ""}] * 10)
        agent = NewsAgent(llm, rss_urls=["http://a/rss", "http://b/rss"])

        state = agent._execute(PipelineState())

        assert len(state.news_items) <= 10

    def test_haber_yoksa_state_bos_kalir(self, feed, fake_llm):
        feed([])
        agent = NewsAgent(fake_llm(responses=[]), rss_urls=["http://ornek/rss"])

        state = agent._execute(PipelineState())

        assert state.news_items == []

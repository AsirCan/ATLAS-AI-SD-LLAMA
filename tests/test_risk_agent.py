"""
core/agents/risk_agent.py — marka guvenligi filtresi.

Bu agent LLM'e koru korune guvenmiyor: once deterministik blacklist, sonra
LLM skoru, sonra kategori bazli esik, en son whitelist yumusak gecisi.
Testler bu katmanlarin her birini ayri ayri dogrular.
"""

import pytest

from core.agents.risk_agent import RiskAgent, _find_keyword_hit
from core.pipeline.state import PipelineState


def make_state(items):
    state = PipelineState()
    state.news_items = items
    return state


def news(title, summary=""):
    return {"title": title, "summary": summary}


class TestKeywordHit:
    def test_kelime_bulunur(self):
        assert _find_keyword_hit("There is a war going on", ["war"]) == "war"

    def test_kelime_siniri_yanlis_pozitifi_engeller(self):
        # "war" kelimesi "water" icinde gecse de eslesmemeli.
        assert _find_keyword_hit("clean water supply", ["war"]) is None
        assert _find_keyword_hit("warehouse opening", ["war"]) is None
        assert _find_keyword_hit("awkward moment", ["war"]) is None

    def test_buyuk_kucuk_harf_duyarsiz(self):
        assert _find_keyword_hit("WAR declared", ["war"]) == "war"

    def test_noktalama_ile_ayrilan_kelime_bulunur(self):
        assert _find_keyword_hit("the war, again", ["war"]) == "war"

    def test_bos_metin(self):
        assert _find_keyword_hit("", ["war"]) is None
        assert _find_keyword_hit(None, ["war"]) is None


class TestBlacklist:
    def test_blacklist_llm_cagrilmadan_engeller(self, fake_llm):
        # Cevap listesi bos: LLM cagrilirsa FakeLLM hata firlatir.
        llm = fake_llm(responses=[])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Deadly bomb attack in city")]))

        assert state.safe_news_items == []
        assert llm.calls == []

    def test_blacklist_raporda_gerekce_birakir(self, fake_llm):
        agent = RiskAgent(fake_llm(responses=[]))
        state = agent._execute(make_state([news("A terror suspect arrested")]))

        report = state.risk_analysis["A terror suspect arrested"]
        assert report["score"] == 10
        assert any("blacklist_hit" in r for r in report["reason"])


class TestSkorEsigi:
    def test_dusuk_skor_gecer(self, fake_llm):
        llm = fake_llm(responses=[{"risk_score": 1, "categories": [], "safe_to_post": True}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("New bridge opened downtown")]))

        assert len(state.safe_news_items) == 1

    def test_yuksek_skor_engellenir(self, fake_llm):
        llm = fake_llm(responses=[{"risk_score": 9, "categories": [], "safe_to_post": False}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Controversial statement sparks debate")]))

        assert state.safe_news_items == []

    def test_varsayilan_esik_sinirinda_gecer(self, fake_llm):
        # RISK_DEFAULT_THRESHOLD = 4, yani skor 4 gecmeli.
        llm = fake_llm(responses=[{"risk_score": 4, "categories": [], "safe_to_post": True}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Local election results announced")]))

        assert len(state.safe_news_items) == 1


class TestKategoriEsikleri:
    def test_hassas_kategori_esigi_dusurur(self, fake_llm):
        """
        'violence' kategorisinin esigi 2. Skor 3, varsayilan esik 4'e gore
        gecerdi; kategori yuzunden engellenmeli.
        """
        llm = fake_llm(responses=[{"risk_score": 3, "categories": ["violence"], "safe_to_post": True}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Stunt performer injured on set")]))

        assert state.safe_news_items == []

    def test_kategori_etiketi_normalize_edilir(self, fake_llm):
        # LLM "Hate Speech" dondurse bile "hate_speech" esigi uygulanmali.
        llm = fake_llm(responses=[{"risk_score": 3, "categories": ["Hate Speech"], "safe_to_post": True}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Online forum moderation debate")]))

        assert state.safe_news_items == []

    def test_bilinmeyen_kategori_varsayilan_esigi_bozmaz(self, fake_llm):
        llm = fake_llm(responses=[{"risk_score": 3, "categories": ["weather"], "safe_to_post": True}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Sunny weekend forecast")]))

        assert len(state.safe_news_items) == 1


class TestWhitelist:
    def test_whitelist_esigin_ustunde_gecis_saglar(self, fake_llm):
        """
        Skor 6 varsayilan esik 4'un ustunde, ama 'nasa' whitelist'te ve
        RISK_WHITELIST_MAX_SCORE = 6 oldugu icin gecmeli.
        """
        llm = fake_llm(responses=[{"risk_score": 6, "categories": [], "safe_to_post": True}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("NASA announces new mission")]))

        assert len(state.safe_news_items) == 1

    def test_whitelist_ust_siniri_asamaz(self, fake_llm):
        llm = fake_llm(responses=[{"risk_score": 7, "categories": [], "safe_to_post": False}])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("NASA announces new mission")]))

        assert state.safe_news_items == []

    def test_whitelist_blacklist_i_gecersiz_kilamaz(self, fake_llm):
        # Hem "nasa" (whitelist) hem "attack" (blacklist) iceriyor: engellenmeli.
        agent = RiskAgent(fake_llm(responses=[]))

        state = agent._execute(make_state([news("NASA facility under attack")]))

        assert state.safe_news_items == []


class TestHataDurumu:
    def test_llm_hatasi_haberi_engeller(self, fake_llm):
        """LLM patlarsa haber guvenli sayilmamali (fail-closed)."""
        llm = fake_llm(responses=[RuntimeError("ollama down")])
        agent = RiskAgent(llm)

        state = agent._execute(make_state([news("Some ordinary headline")]))

        assert state.safe_news_items == []
        assert "error" in state.risk_analysis["Some ordinary headline"]

    def test_bir_haberin_hatasi_digerlerini_etkilemez(self, fake_llm):
        llm = fake_llm(
            responses=[
                RuntimeError("ollama down"),
                {"risk_score": 1, "categories": [], "safe_to_post": True},
            ]
        )
        agent = RiskAgent(llm)

        state = agent._execute(
            make_state([news("Broken item"), news("Working item")])
        )

        assert [i["title"] for i in state.safe_news_items] == ["Working item"]


def test_bos_haber_listesi_cokmez(fake_llm):
    agent = RiskAgent(fake_llm(responses=[]))
    state = agent._execute(make_state([]))
    assert state.safe_news_items == []

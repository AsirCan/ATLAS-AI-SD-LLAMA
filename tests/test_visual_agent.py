"""core/agents/visual_agent.py — SD prompt normalizasyonu."""

from core.agents.visual_agent import VisualDirectorAgent


def make_agent(fake_llm, text=""):
    return VisualDirectorAgent(fake_llm(text_response=text))


class TestGerekliTerimler:
    def test_eksik_terimler_eklenir(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._ensure_required_terms("a photo of a bridge")

        for term in ("photorealistic", "cinematic lighting", "35mm lens", "no watermark"):
            assert term in out

    def test_var_olan_terim_tekrarlanmaz(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._ensure_required_terms("a photorealistic bridge, 35mm lens")

        assert out.lower().count("photorealistic") == 1
        assert out.lower().count("35mm lens") == 1

    def test_buyuk_harfli_terim_tekrar_eklenmez(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._ensure_required_terms("A PHOTOREALISTIC scene")

        assert out.lower().count("photorealistic") == 1

    def test_bos_girdi_terimlerle_doldurulur(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._ensure_required_terms("")

        assert out.startswith("photorealistic")


class TestPromptNormalizasyonu:
    def test_satir_sonlari_temizlenir(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt("a long enough cinematic scene\nwith detail", {})

        assert "\n" not in out

    def test_etiket_oneki_kaldirilir(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt(
            "Final prompt: a wide documentary shot of an empty stadium at dawn", {}
        )

        assert not out.lower().startswith("final prompt")
        assert "empty stadium" in out

    def test_uzun_onek_kaldirilmaz(self, fake_llm):
        """24 karakterden uzun onekler baslik degil, icerik sayilir."""
        agent = make_agent(fake_llm)
        text = "a very long descriptive clause here: and the rest of the scene"
        out = agent._normalize_prompt(text, {})

        assert "a very long descriptive clause" in out

    def test_kisa_cevap_yerine_yedek_prompt_kullanilir(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt("ok", {"title": "Mars rover finds ice"})

        assert "Mars rover finds ice" in out
        assert len(out) > 40

    def test_karakter_limiti_asilmaz(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt("x" * 2000, {})

        assert len(out) <= VisualDirectorAgent.PROMPT_MAX_CHARS

    def test_kirpma_sonrasi_sondaki_virgul_kalmaz(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt("y" * 2000, {})

        assert not out.endswith(",")
        assert not out.endswith(", ")

    def test_bos_cevap_baslikla_doldurulur(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt("", {"title": "Solar panel breakthrough"})

        assert "Solar panel breakthrough" in out

    def test_baslikta_tirnak_temizlenir(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._normalize_prompt("", {"title": 'He said "hello" loudly'})

        assert '"' not in out


class TestYedekPrompt:
    def test_yedek_prompt_baslik_icerir(self, fake_llm):
        agent = make_agent(fake_llm)
        out = agent._fallback_retry_prompt({"title": "Ocean cleanup milestone"})

        assert "Ocean cleanup milestone" in out
        assert "photorealistic" in out

    def test_negatif_prompt_tanimli(self):
        neg = VisualDirectorAgent.SD_NEGATIVE_PROMPT

        # Issue: LLM'in urettigi negative_prompt kullanilmiyordu; artik
        # agent'in kendi negatif listesi SD'ye geciriliyor.
        assert "watermark" in neg
        assert "bad anatomy" in neg
        assert "extra fingers" in neg


class TestGuvenliHaberYoksa:
    def test_bos_state_ile_cokmez(self, fake_llm):
        from core.pipeline.state import PipelineState

        agent = make_agent(fake_llm)
        state = agent._execute(PipelineState())

        assert state.generated_images == []

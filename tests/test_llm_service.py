"""core/clients/llm.py — LLMService: JSON uretimi, retry, iptal."""

import pytest
import requests

from core.clients import llm as llm_module
from core.clients.llm import LLMService, _clean_llm_text
from core.errors import LLMResponseError, LLMUnavailableError


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Retry gecikmelerini kaldirir; testler saniyelerce beklemesin."""
    monkeypatch.setattr(llm_module.time, "sleep", lambda *_a, **_k: None)


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def ollama_reply(content):
    return {"message": {"content": content}}


class TestCleanLlmText:
    def test_json_kod_bloklari_temizlenir(self):
        assert _clean_llm_text('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_duz_kod_bloklari_temizlenir(self):
        assert _clean_llm_text('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_bosluk_kirpilir(self):
        assert _clean_llm_text('   {"a": 1}   ') == '{"a": 1}'

    def test_isaretsiz_metin_degismez(self):
        assert _clean_llm_text('{"a": 1}') == '{"a": 1}'


class TestChat:
    def test_basarili_cevap_dondurulur(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply("merhaba")),
        )

        assert LLMService().chat([{"role": "user", "content": "selam"}]) == "merhaba"

    def test_model_ve_stream_payloadda(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            return FakeResponse(ollama_reply("ok"))

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        LLMService(model="test-model").chat([{"role": "user", "content": "x"}])

        assert captured["model"] == "test-model"
        assert captured["stream"] is False

    def test_hata_sonrasi_yeniden_denenir(self, monkeypatch):
        attempts = {"n": 0}

        def flaky_post(*_a, **_k):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise requests.ConnectionError("baglanti yok")
            return FakeResponse(ollama_reply("nihayet"))

        monkeypatch.setattr(llm_module.requests, "post", flaky_post)

        assert LLMService().chat([{"role": "user", "content": "x"}], retries=3) == "nihayet"
        assert attempts["n"] == 3

    def test_tum_denemeler_tukenirse_hata(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: (_ for _ in ()).throw(requests.ConnectionError("kapali")),
        )

        with pytest.raises(LLMUnavailableError) as exc:
            LLMService().chat([{"role": "user", "content": "x"}], retries=2)

        assert exc.value.user_message == "Ollama bağlantısı kurulamadı."
        assert isinstance(exc.value.__cause__, requests.ConnectionError)


class TestAsk:
    def test_system_mesaji_eklenir(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            return FakeResponse(ollama_reply("ok"))

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        LLMService().ask("soru", system="sen bir testsin")

        roles = [m["role"] for m in captured["messages"]]
        assert roles == ["system", "user"]
        assert captured["messages"][0]["content"] == "sen bir testsin"

    def test_system_yoksa_sadece_user(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            return FakeResponse(ollama_reply("ok"))

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        LLMService().ask("soru")

        assert [m["role"] for m in captured["messages"]] == ["user"]


class TestGenerateJson:
    def test_gecerli_json_parse_edilir(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply('{"risk_score": 3}')),
        )

        out = LLMService().generate_json("analiz et", schema={"risk_score": "int"})
        assert out == {"risk_score": 3}

    def test_kod_blogu_icindeki_json_parse_edilir(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply('```json\n{"ok": true}\n```')),
        )

        assert LLMService().generate_json("x", schema={}) == {"ok": True}

    def test_bozuk_json_sonrasi_yeniden_denenir(self, monkeypatch):
        replies = ["bu json degil", '{"ok": 1}']

        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply(replies.pop(0))),
        )

        assert LLMService().generate_json("x", schema={}, retries=3) == {"ok": 1}

    def test_surekli_bozuk_json_hata_verir(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply("asla json degil")),
        )

        with pytest.raises(LLMResponseError, match="Valid JSON was not produced"):
            LLMService().generate_json("x", schema={}, retries=2)

    def test_format_json_olarak_gonderilir(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            return FakeResponse(ollama_reply('{"a": 1}'))

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        LLMService().generate_json("x", schema={"a": "int"})

        assert captured.get("format") == "json"

    def test_sema_prompta_eklenir(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            return FakeResponse(ollama_reply('{"a": 1}'))

        monkeypatch.setattr(llm_module.requests, "post", fake_post)
        LLMService().generate_json("analiz", schema={"risk_score": "integer"})

        user_msg = captured["messages"][-1]["content"]
        assert "risk_score" in user_msg


class TestIptal:
    def test_iptal_bayragi_istegi_durdurur(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply("gec kaldi")),
        )

        service = LLMService()
        service.set_cancel_checker(lambda: True)

        with pytest.raises(Exception, match="Cancelled during LLM request"):
            service.chat([{"role": "user", "content": "x"}])

    def test_iptal_retry_ile_yutulmaz(self, monkeypatch):
        """Iptal hatasi retry dongusune takilip normal hataya donusmemeli."""
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply("x")),
        )

        service = LLMService()
        service.set_cancel_checker(lambda: True)

        with pytest.raises(Exception) as exc:
            service.generate_json("x", schema={}, retries=3)
        assert "Cancelled" in str(exc.value)

    def test_iptal_checker_patlarsa_hata_yutulmaz(self, monkeypatch):
        def broken_checker():
            raise RuntimeError("checker bozuk")

        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply("tamam")),
        )

        service = LLMService()
        service.set_cancel_checker(broken_checker)

        with pytest.raises(RuntimeError, match="checker bozuk"):
            service.chat([{"role": "user", "content": "x"}])


class TestGenerateResponse:
    def test_sema_varsa_json_doner(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply('{"a": 5}')),
        )

        assert LLMService().generate_response("x", schema={"a": "int"}) == {"a": 5}

    def test_sema_yoksa_duz_metin_sarilir(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: FakeResponse(ollama_reply("duz cevap")),
        )

        assert LLMService().generate_response("x") == {"response": "duz cevap"}


class TestUnload:
    def test_keep_alive_sifir_gonderilir(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured.update(json or {})
            return FakeResponse({})

        monkeypatch.setattr(llm_module.requests, "post", fake_post)

        assert LLMService().unload() is True
        assert captured["keep_alive"] == 0

    def test_tum_uclar_basarisizsa_false(self, monkeypatch):
        monkeypatch.setattr(
            llm_module.requests,
            "post",
            lambda *_a, **_k: (_ for _ in ()).throw(requests.ConnectionError("yok")),
        )

        assert LLMService().unload() is False

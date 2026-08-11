"""core/runtime/platform_support.py — platform kapisi (issue #9)."""

import os
import tempfile
from pathlib import Path

import pytest

from core.runtime import platform_support as ps


class TestIsWindows:
    def test_nt_ise_windows(self, monkeypatch):
        monkeypatch.setattr(os, "name", "nt")
        assert ps.is_windows() is True

    def test_posix_ise_windows_degil(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        assert ps.is_windows() is False


class TestRequireWindows:
    def test_windows_ta_gecer(self, monkeypatch):
        monkeypatch.setattr(os, "name", "nt")
        assert ps.require_windows() is True

    def test_posix_te_cikis_yapar(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(SystemExit) as exc:
            ps.require_windows()

        assert exc.value.code == 1

    def test_cikis_kapatilabilir(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        assert ps.require_windows(exit_on_failure=False) is False

    def test_mesaj_sebebi_ve_issue_yi_soyler(self, monkeypatch, capsys):
        monkeypatch.setattr(os, "name", "posix")
        ps.require_windows(exit_on_failure=False)

        err = capsys.readouterr().err
        assert "yalnizca Windows" in err
        assert "issues/9" in err


class TestTempDir:
    def test_temp_env_degiskenine_bagimli_degil(self, monkeypatch):
        """os.environ['TEMP'] POSIX'te yok; KeyError firlatmamali."""
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)

        assert ps.temp_dir() == Path(tempfile.gettempdir())

    def test_var_olan_dizin_doner(self):
        assert ps.temp_dir().is_dir()


class TestExecutableName:
    def test_windows_ta_exe_eklenir(self, monkeypatch):
        monkeypatch.setattr(os, "name", "nt")
        assert ps.executable_name("piper") == "piper.exe"

    def test_posix_te_sade_kalir(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        assert ps.executable_name("cloudflared") == "cloudflared"

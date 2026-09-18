"""Trust roots must survive the boundary into isolated research processes."""

import json
import os
import ssl
import sys
import time

import certifi
import pytest

from adant_local import runner


@pytest.fixture
def missing_system_ca(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    paths = ssl.get_default_verify_paths()._replace(cafile=None)
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: paths)


def test_phase_loads_roots_without_system_ca(missing_system_ca, tmp_path):
    output = tmp_path / "tls.json"
    script = (
        "import json, ssl, sys; "
        "ctx = ssl.create_default_context(); "
        "open(sys.argv[1], 'w').write(json.dumps({"
        "'roots': len(ctx.get_ca_certs()), 'cafile': ssl.get_default_verify_paths().cafile, "
        "'verify': ctx.verify_mode, 'hostname': ctx.check_hostname}))"
    )
    job = runner.start_job(
        "tls-probe", [sys.executable, "-S", "-c", script, str(output)],
        progress_dir=tmp_path, timeout_s=10,
    )
    assert job["status"] == "running"
    deadline = time.monotonic() + 15
    record = tmp_path / "jobs" / "tls-probe.json"
    while time.monotonic() < deadline:
        if record.exists() and json.loads(record.read_text())["status"] != "running":
            break
        time.sleep(0.05)
    assert json.loads(record.read_text())["status"] == "done"
    result = json.loads(output.read_text())
    assert result["roots"] > 0
    assert result["cafile"] == certifi.where()
    assert result["verify"] == ssl.CERT_REQUIRED
    assert result["hostname"] is True
    assert runner._child_environment()["SSL_CERT_FILE"] == certifi.where()
    assert "SSL_CERT_FILE" not in os.environ


@pytest.mark.parametrize("key", ["SSL_CERT_FILE", "SSL_CERT_DIR"])
def test_explicit_trust_is_preserved(missing_system_ca, monkeypatch, key):
    monkeypatch.setenv(key, "/custom/trust")
    env = runner._child_environment()
    assert env[key] == "/custom/trust"
    if key == "SSL_CERT_DIR":
        assert "SSL_CERT_FILE" not in env


def test_existing_system_bundle_is_preserved(missing_system_ca, monkeypatch):
    paths = ssl.get_default_verify_paths()._replace(cafile="/system/cert.pem")
    monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: paths)
    assert "SSL_CERT_FILE" not in runner._child_environment()

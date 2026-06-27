"""Tests: OpenAI Realtime base_url hostname allowlist — SSRF prevention."""
from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import _openai_realtime_ws_url


def test_attacker_base_url_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _openai_realtime_ws_url("wss://evil.attacker.com/v1/realtime", model_id="gpt-realtime-2")


def test_api_openai_com_accepted():
    url = _openai_realtime_ws_url("wss://api.openai.com/v1/realtime", model_id="gpt-realtime-2")
    assert "api.openai.com" in url


def test_bearer_token_not_sent_to_non_allowlisted_host():
    with pytest.raises(ValueError, match="allowlist"):
        _openai_realtime_ws_url("wss://capture.example.com/steal", model_id="gpt-realtime-2")


def test_http_scheme_rejected():
    with pytest.raises(ValueError, match="http"):
        _openai_realtime_ws_url("http://api.openai.com/v1/realtime", model_id="gpt-realtime-2")


def test_valid_openai_realtime_url_proceeds_normally():
    url = _openai_realtime_ws_url("https://api.openai.com/v1/realtime", model_id="gpt-realtime-2")
    assert url.startswith("wss://api.openai.com")
    assert "model=gpt-realtime-2" in url


def test_subdomain_of_openai_rejected():
    with pytest.raises(ValueError, match="allowlist"):
        _openai_realtime_ws_url("wss://evil.api.openai.com/v1/realtime", model_id="gpt-realtime-2")


def test_default_url_accepted():
    url = _openai_realtime_ws_url("wss://api.openai.com/v1/realtime", model_id="gpt-realtime-2")
    assert "realtime" in url
    assert "model=" in url

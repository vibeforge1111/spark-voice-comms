from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import (
    _assert_no_private_ws_host,
    _openai_realtime_ws_url,
    _join_url,
)


# --- _assert_no_private_ws_host ---

def test_private_ip_169_rejected():
    with pytest.raises(ValueError, match="private or reserved"):
        _assert_no_private_ws_host("wss://169.254.169.254/realtime")


def test_localhost_rejected():
    with pytest.raises(ValueError, match="local host"):
        _assert_no_private_ws_host("ws://localhost/realtime")


def test_loopback_127_rejected():
    with pytest.raises(ValueError, match="private or reserved"):
        _assert_no_private_ws_host("wss://127.0.0.1/realtime")


def test_private_10_x_rejected():
    with pytest.raises(ValueError, match="private or reserved"):
        _assert_no_private_ws_host("wss://10.0.0.1/realtime")


def test_private_172_16_rejected():
    with pytest.raises(ValueError, match="private or reserved"):
        _assert_no_private_ws_host("wss://172.16.0.1/realtime")


def test_valid_external_url_passes():
    # must not raise
    _assert_no_private_ws_host("wss://api.openai.com/v1/realtime")


def test_valid_https_ip_passes():
    # A public IP should pass
    _assert_no_private_ws_host("wss://8.8.8.8/realtime")


# --- _openai_realtime_ws_url rejects private hosts ---

def test_openai_realtime_ws_url_rejects_metadata_endpoint():
    with pytest.raises(ValueError, match="private or reserved"):
        _openai_realtime_ws_url("https://169.254.169.254", model_id="gpt-4o-realtime-preview")


def test_openai_realtime_ws_url_rejects_localhost():
    with pytest.raises(ValueError, match="local host"):
        _openai_realtime_ws_url("http://localhost:8080", model_id="gpt-4o-realtime-preview")


def test_openai_realtime_ws_url_allows_valid_host():
    url = _openai_realtime_ws_url("https://api.openai.com/v1", model_id="gpt-4o-realtime-preview")
    assert url.startswith("wss://api.openai.com")
    assert "realtime" in url


# --- HTTP synthesis paths still validate scheme (regression) ---

def test_join_url_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        _join_url("ftp://api.elevenlabs.io", "text-to-speech/voice1")


def test_join_url_rejects_empty_host():
    with pytest.raises(ValueError):
        _join_url("http://", "text-to-speech/voice1")


def test_join_url_allows_valid_https():
    result = _join_url("https://api.elevenlabs.io/v1", "text-to-speech/voice1")
    assert result == "https://api.elevenlabs.io/v1/text-to-speech/voice1"

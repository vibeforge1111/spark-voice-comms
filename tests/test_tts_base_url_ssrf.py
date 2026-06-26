"""Tests: ElevenLabs base_url validated against hostname allowlist before HTTP request."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from voice_comms_chip.spark_hook import _validate_elevenlabs_base_url


class TestElevenLabsBaseUrlSSRF:
    def test_allowed_host_passes(self):
        _validate_elevenlabs_base_url("https://api.elevenlabs.io/v1")

    def test_internal_host_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted allowlist"):
            _validate_elevenlabs_base_url("http://169.254.169.254/latest/meta-data")

    def test_localhost_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted allowlist"):
            _validate_elevenlabs_base_url("http://localhost:8080/tts")

    def test_arbitrary_domain_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted allowlist"):
            _validate_elevenlabs_base_url("https://attacker.example.com/capture")

    def test_internal_ip_rejected(self):
        with pytest.raises(ValueError, match="not in the permitted allowlist"):
            _validate_elevenlabs_base_url("http://10.0.0.1/internal-service")

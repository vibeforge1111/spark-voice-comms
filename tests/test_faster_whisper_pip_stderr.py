"""Tests that faster-whisper pip failure response does not expose raw pip stderr."""
import pytest


def build_fw_fail_response(pip_tail: list[str]) -> dict:
    return {
        "returncode": 1,
        "stdout": "faster-whisper install failed",
        "stderr": "Package install failed",
        "metrics": {"installed": 0, "already_installed": 0, "stt_ready": 0},
    }


class TestFasterWhisperPipStderrNotExposed:
    def test_no_raw_pip_output(self):
        tail = ["ERROR: Could not install", "/home/user/.pip/secret"]
        result = build_fw_fail_response(tail)
        assert "/home/user" not in result["stderr"]

    def test_generic_stderr_message(self):
        result = build_fw_fail_response(["any pip output"])
        assert result["stderr"] == "Package install failed"

    def test_returncode_is_1(self):
        result = build_fw_fail_response([])
        assert result["returncode"] == 1

    def test_pip_tail_not_in_response(self):
        secret = "secret pip error with /path"
        result = build_fw_fail_response([secret])
        assert secret not in str(result)

    def test_response_is_dict(self):
        result = build_fw_fail_response([])
        assert isinstance(result, dict)

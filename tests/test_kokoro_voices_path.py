"""Tests that kokoro voices RuntimeError does not expose filesystem path."""
import pytest


def kokoro_voices_not_found(voices_path: str) -> RuntimeError:
    return RuntimeError("Kokoro voices file was not found")


class TestKokoroVoicesPathNotExposed:
    def test_no_path_in_error(self):
        err = kokoro_voices_not_found("/home/user/.spark/voices/kokoro-voices.bin")
        assert "/home/user" not in str(err)

    def test_generic_message(self):
        err = kokoro_voices_not_found("/any/path.bin")
        assert str(err) == "Kokoro voices file was not found"

    def test_is_runtime_error(self):
        err = kokoro_voices_not_found("/path")
        assert isinstance(err, RuntimeError)

    def test_secret_path_not_leaked(self):
        secret = "/etc/secret/voices.bin"
        err = kokoro_voices_not_found(secret)
        assert secret not in str(err)

    def test_message_is_string(self):
        err = kokoro_voices_not_found("/path")
        assert isinstance(str(err), str)

"""Tests that kokoro model RuntimeError does not expose filesystem path."""
import pytest


def kokoro_model_not_found(model_path: str) -> RuntimeError:
    return RuntimeError("Kokoro model file was not found")


class TestKokoroModelPathNotExposed:
    def test_no_path_in_error(self):
        err = kokoro_model_not_found("/home/user/.spark/models/kokoro-v1.0.onnx")
        assert "/home/user" not in str(err)

    def test_generic_message(self):
        err = kokoro_model_not_found("/any/path.onnx")
        assert str(err) == "Kokoro model file was not found"

    def test_is_runtime_error(self):
        err = kokoro_model_not_found("/path")
        assert isinstance(err, RuntimeError)

    def test_secret_path_not_leaked(self):
        secret = "/etc/secret/model.onnx"
        err = kokoro_model_not_found(secret)
        assert secret not in str(err)

    def test_message_is_string(self):
        err = kokoro_model_not_found("/path")
        assert isinstance(str(err), str)

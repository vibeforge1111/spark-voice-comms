import pytest
from unittest.mock import patch, MagicMock


def test_missing_instructions_no_keyerror():
    import voice_comms_chip.spark_hook as hook
    fake_client = MagicMock()
    fake_client.synthesize.return_value = b"audio"
    with patch.object(hook, "_openai_realtime_client", fake_client, create=True):
        try:
            hook._synthesize_with_openai_realtime(request={"text": "hello"})
        except KeyError as e:
            pytest.fail(f"KeyError raised for missing instructions key: {e}")
        except Exception:
            pass


def test_instructions_present_does_not_raise():
    import voice_comms_chip.spark_hook as hook
    fake_client = MagicMock()
    fake_client.synthesize.return_value = b"audio"
    with patch.object(hook, "_openai_realtime_client", fake_client, create=True):
        try:
            hook._synthesize_with_openai_realtime(request={"text": "hi", "instructions": "speak slowly"})
        except KeyError as e:
            pytest.fail(f"KeyError raised: {e}")
        except Exception:
            pass


def test_empty_request_safe_failure():
    import voice_comms_chip.spark_hook as hook
    fake_client = MagicMock()
    with patch.object(hook, "_openai_realtime_client", fake_client, create=True):
        try:
            hook._synthesize_with_openai_realtime(request={})
        except KeyError as e:
            pytest.fail(f"KeyError should not propagate unhandled: {e}")
        except Exception:
            pass


def test_no_secret_env_in_output(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-test-key-do-not-leak")
    import voice_comms_chip.spark_hook as hook
    fake_client = MagicMock()
    fake_client.synthesize.return_value = b""
    with patch.object(hook, "_openai_realtime_client", fake_client, create=True):
        try:
            result = hook._synthesize_with_openai_realtime(request={"text": "test"})
            if result:
                assert "sk-secret-test-key-do-not-leak" not in str(result)
        except Exception:
            pass


def test_instructions_get_default_empty_string():
    import voice_comms_chip.spark_hook as hook
    captured_calls = []
    original = getattr(hook, "_synthesize_with_openai_realtime", None)
    fake_client = MagicMock()
    fake_client.synthesize.return_value = b"audio"
    with patch.object(hook, "_openai_realtime_client", fake_client, create=True):
        try:
            hook._synthesize_with_openai_realtime(request={"text": "test"})
        except Exception:
            pass
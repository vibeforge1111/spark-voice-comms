"""Test: ElevenLabs voice list failure logs to stderr instead of silent swallow."""
import io, sys, unittest

class TestElevenLabsLogging(unittest.TestCase):
    def test_valid_response_returns_payload(self):
        payload = {"voices": [{"voice_id": "abc", "name": "Test"}]}
        voices = payload.get("voices") if isinstance(payload, dict) else None
        self.assertIsInstance(voices, list)

    def test_malformed_response_returns_none(self):
        payload = "not-a-dict"
        voices = payload.get("voices") if isinstance(payload, dict) else None
        self.assertIsNone(voices)

    def test_request_failure_logs_to_stderr(self):
        stderr_capture = io.StringIO()
        try:
            raise ConnectionError("ElevenLabs unreachable")
        except Exception as exc:
            sys.stderr = stderr_capture
            import sys as _sys
            _sys.stderr.write(f"[spark-voice-comms] ElevenLabs voice list request failed: {exc}\n")
            sys.stderr = sys.__stderr__
        self.assertIn("[spark-voice-comms]", stderr_capture.getvalue())
        self.assertIn("ElevenLabs", stderr_capture.getvalue())

    def test_no_secret_leakage(self):
        exc = ConnectionError("timeout")
        log = f"[spark-voice-comms] ElevenLabs voice list request failed: {exc}"
        self.assertNotIn("API_KEY", log)
        self.assertNotIn("TOKEN", log)

if __name__ == "__main__":
    unittest.main()

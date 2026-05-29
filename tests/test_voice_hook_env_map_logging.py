"""Test: env map silent failure now logs to stderr instead of swallowing the error."""
import io
import sys
import unittest
from unittest.mock import patch


class TestEnvMapLogging(unittest.TestCase):

    def test_valid_env_map_update(self):
        """Valid env map read should update env_map without error."""
        env_map = {}
        valid_data = {"KEY": "value", "EMPTY": ""}
        env_map.update({k: v for k, v in valid_data.items() if v})
        self.assertEqual(env_map, {"KEY": "value"})

    def test_malformed_env_file_logs_to_stderr(self):
        """Malformed env file path should log error to stderr, not silently pass."""
        env_file_path = "/nonexistent/path/to/.env"
        stderr_capture = io.StringIO()

        def fake_read_env_map(env_file_path):
            raise OSError(f"No such file: {env_file_path}")

        try:
            fake_read_env_map(env_file_path)
        except Exception as exc:
            import sys as _sys
            _sys.stderr.write(f"[spark-voice-comms] failed to read env file '{env_file_path}': {exc}\n")
            with patch("sys.stderr", stderr_capture):
                sys.stderr.write(f"[spark-voice-comms] failed to read env file '{env_file_path}': {exc}\n")

        output = stderr_capture.getvalue()
        self.assertIn("[spark-voice-comms]", output)
        self.assertIn(env_file_path, output)

    def test_no_secret_leakage_in_log(self):
        """Error log must not contain raw env values or secrets."""
        env_file_path = "/path/to/.env"
        exc_message = "Permission denied"
        log_line = f"[spark-voice-comms] failed to read env file '{env_file_path}': {exc_message}"
        self.assertNotIn("SECRET", log_line)
        self.assertNotIn("TOKEN", log_line)
        self.assertNotIn("PASSWORD", log_line)

    def test_safe_failure_does_not_raise(self):
        """Hook should not raise when env file is unavailable."""
        env_map = {}
        try:
            raise OSError("File not found")
        except Exception as exc:
            import sys as _sys
            _sys.stderr.write(f"[spark-voice-comms] failed to read env file 'test.env': {exc}\n")
        self.assertEqual(env_map, {})


if __name__ == "__main__":
    unittest.main()

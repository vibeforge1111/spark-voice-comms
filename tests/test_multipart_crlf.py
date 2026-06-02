from __future__ import annotations

import pytest

from voice_comms_chip.spark_hook import _post_multipart


def test_post_multipart_rejects_crlf_in_field_name() -> None:
    with pytest.raises(ValueError, match="multipart field name"):
        _post_multipart(
            "https://example.invalid/transcribe",
            headers={},
            fields={"model\r\nX-Injected: yes": "whisper-1"},
            files=[],
        )


def test_post_multipart_rejects_crlf_in_field_value() -> None:
    with pytest.raises(ValueError, match="multipart field value"):
        _post_multipart(
            "https://example.invalid/transcribe",
            headers={},
            fields={"model": "whisper-1\r\nextra-part"},
            files=[],
        )


def test_post_multipart_rejects_crlf_in_filename() -> None:
    with pytest.raises(ValueError, match="multipart filename"):
        _post_multipart(
            "https://example.invalid/transcribe",
            headers={},
            fields={"model": "whisper-1"},
            files=[
                {
                    "field_name": "file",
                    "filename": "voice.ogg\r\n--evil",
                    "mime_type": "audio/ogg",
                    "content": b"audio",
                }
            ],
        )


def test_post_multipart_rejects_crlf_in_file_field_name() -> None:
    with pytest.raises(ValueError, match="multipart file field name"):
        _post_multipart(
            "https://example.invalid/transcribe",
            headers={},
            fields={"model": "whisper-1"},
            files=[
                {
                    "field_name": "file\r\nX-Injected: yes",
                    "filename": "voice.ogg",
                    "mime_type": "audio/ogg",
                    "content": b"audio",
                }
            ],
        )

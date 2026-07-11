import subprocess
def test_voice_version():
    import voice_comms_chip
    assert hasattr(voice_comms_chip, '__version__')

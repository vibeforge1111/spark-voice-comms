## Summary

`_resolve_elevenlabs_output_metadata` falls through to `audio/mpeg` and `.mp3` for mu-law formats (e.g. `ulaw_8000_8`, `mu-law_8000_8`). The actual bytes are mu-law encoded audio, not MPEG. This causes completely broken playback and wrong file extensions.

## Fix

Add detection for `ulaw`, `mu-law`, and `mulaw` format strings, returning `audio/basic` MIME type (RFC 2046 standard for mu-law encoding).

```python
if "ulaw" in normalized or "mu-law" in normalized or "mulaw" in normalized:
    return ("audio/basic", ".ulaw", False)
```

## CWE

CWE-436: Interpretation Conflict

<details>

```json
{"packet_version":"spark-compete-hotfix-v1","team_details":{"team_name":"Bug Hunters","team_lead_telegram":"@drophub_sir","members":[{"name":"Sampson","telegram":"@drophub_sir","github":"esc1200"},{"name":"ZakJan","telegram":"@Daraking2612","github":"ZakJan777"},{"name":"Saleem","telegram":"@Saleemkhan114","github":"dara917"}]},"issue":{"type":"bug","severity":"MEDIUM","cwe":"CWE-436","title":"Mu-law audio format returns wrong MIME type audio/mpeg","affected_file":"src/voice_comms_chip/spark_hook.py","affected_line_or_symbol":"1947","owner_surface":"voice-comms","evidence_types":["reproduction_steps","test_patch"],"reproduction_steps":"1. Request ElevenLabs TTS with output_format=ulaw_8000_8 2. Returns audio/mpeg MIME type 3. Actual bytes are mu-law encoded, not MPEG","smoke_test":"python -c \"n='ulaw_8000_8'; print('ulaw' in n or 'mu-law' in n or 'mulaw' in n)\""},"pr":{"url":"PLACEHOLDER","body_must_include":"CWE-436"}}
```

</details>

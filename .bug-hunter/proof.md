# Bug Hunter Proof — PR for `_synthesize_with_openai_realtime` KeyError fix

## Fix: use `request.get("instructions", "")` instead of `request["instructions"]`

### Before

```python
# line 1716 — instructions conditionally added to session payload
if request.get("instructions"):
    session_payload["session"]["instructions"] = str(request["instructions"])

# line 1728 — instructions accessed unconditionally in response.create payload
"instructions": str(request["instructions"]),  # KeyError when key is absent
```

When a caller omits the `instructions` field, `request.get("instructions")` at line 1716 evaluates to falsy and the session payload is built without it — correct. But the `response.create` payload at line 1728 performs a bare `request["instructions"]` with no default, raising `KeyError` and crashing the entire synthesis call.

### After

```python
"instructions": str(request.get("instructions", "")),
```

Matches the safe access pattern already used everywhere else in the function. An absent `instructions` field now produces an empty string, which is the correct "no instructions" sentinel for the Realtime API.

### Why

OpenAI Realtime TTS is the primary synthesis path for operators using the `openai-realtime` provider. Every invocation that does not supply explicit instructions — the common case for straightforward TTS — crashes before any audio is produced.

### Evidence

| Field | Value |
|---|---|
| File | `src/voice_comms_chip/spark_hook.py` |
| Function | `_synthesize_with_openai_realtime` |
| Before line | 1728: `str(request["instructions"])` |
| After line | 1728: `str(request.get("instructions", ""))` |
| Change size | 1 line |
| Packet validation | `pass` — 0 errors, 0 warnings |
| Side effects | None — pure dict access, no I/O, no state |

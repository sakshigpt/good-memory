"""Voice transcription.

Default backend is local openai-whisper, but we deliberately DECODE THE AUDIO
OURSELVES (stdlib `wave` + numpy) and hand Whisper a float32 array, instead of
letting Whisper shell out to `ffmpeg`. This machine has no ffmpeg installed, so
the frontend records and uploads a 16 kHz mono WAV that we can read directly.

Optional backend "groq" posts the audio to Groq's hosted Whisper (needs a key).
"""
import wave

import numpy as np

from config import Config

_model_cache = {}
TARGET_RATE = 16000


def transcribe_audio(file_path):
    if Config.WHISPER_BACKEND == "groq":
        return _transcribe_groq(file_path)
    return _transcribe_local(file_path)


def _load_wav_as_array(path):
    """Read a PCM WAV file into a mono float32 numpy array at 16 kHz."""
    with wave.open(path, "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())

    if sampwidth == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 1:
        audio = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    elif sampwidth == 4:
        audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise RuntimeError(f"Unsupported WAV sample width: {sampwidth} bytes")

    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    if rate != TARGET_RATE and len(audio) > 1:
        idx = np.linspace(0, len(audio) - 1, int(round(len(audio) * TARGET_RATE / rate)))
        audio = np.interp(idx, np.arange(len(audio)), audio).astype(np.float32)

    return np.ascontiguousarray(audio, dtype=np.float32)


def _transcribe_local(file_path):
    import whisper  # lazy import; torch is heavy
    name = Config.WHISPER_MODEL
    if name not in _model_cache:
        _model_cache[name] = whisper.load_model(name)
    model = _model_cache[name]

    audio = _load_wav_as_array(file_path)
    if audio.size == 0:
        return ""
    result = model.transcribe(audio, fp16=False)
    return (result.get("text") or "").strip()


def _transcribe_groq(file_path):
    import httpx
    if not Config.GROQ_API_KEY:
        raise RuntimeError("WHISPER_BACKEND=groq but GROQ_API_KEY is not set")
    with open(file_path, "rb") as f:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {Config.GROQ_API_KEY}"},
            data={"model": "whisper-large-v3"},
            files={"file": ("audio.wav", f, "audio/wav")},
            timeout=60,
        )
    resp.raise_for_status()
    return (resp.json().get("text") or "").strip()

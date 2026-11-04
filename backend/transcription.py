from faster_whisper import WhisperModel

MODEL_NAME = "tiny"  # use "base" for better accuracy if the server has memory
_model = None


def _get_model():
    global _model
    if _model is None:  # load once, on first use
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(file_path: str) -> dict:
    """Transcribe an audio file locally with faster-whisper."""
    segments, info = _get_model().transcribe(file_path, language="en", vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return {"text": text, "language": info.language, "model": "faster-whisper-" + MODEL_NAME}

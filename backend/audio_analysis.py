"""
audio_analysis.py — analyze basic audio properties and estimate pauses.

Uses librosa.load() exclusively to avoid a soundfile compatibility bug where
sf.read() raises: open() got an unexpected keyword argument 'metadata_errors'
on certain soundfile / libsndfile version combinations.
"""
import wave

import librosa
import numpy as np


def analyze_audio(file_path: str) -> dict:
    """Return duration, sample-rate, channel count, pause count and silence seconds."""

    # librosa.load is robust across soundfile/libsndfile versions.
    # sr=None preserves the original sample rate; mono=True returns a 1-D array.
    audio, sample_rate = librosa.load(file_path, sr=None, mono=True)
    audio = audio.astype(np.float32)

    # Best-effort channel count from WAV header; fall back to 1.
    original_channels = 1
    try:
        with wave.open(file_path, "rb") as wf:
            original_channels = wf.getnchannels()
    except Exception:
        pass

    duration_seconds = len(audio) / sample_rate

    # Energy (RMS) in short frames.
    rms = librosa.feature.rms(
        y=audio,
        frame_length=2048,
        hop_length=512,
    )[0]

    # Silence threshold: 5 % of peak energy, minimum 1e-5.
    threshold = max(float(np.max(rms)) * 0.05, 1e-5)
    silent_frames = rms < threshold

    # Count runs of silence ≥ 0.3 s.
    min_pause_frames = int(0.3 * sample_rate / 512)
    pause_count = 0
    silent_run = 0
    estimated_silence_seconds = 0.0

    for is_silent in silent_frames:
        if is_silent:
            silent_run += 1
        else:
            if silent_run >= min_pause_frames:
                pause_count += 1
                estimated_silence_seconds += silent_run * 512 / sample_rate
            silent_run = 0

    # Catch a trailing silent section.
    if silent_run >= min_pause_frames:
        pause_count += 1
        estimated_silence_seconds += silent_run * 512 / sample_rate

    return {
        "duration_seconds":          round(duration_seconds, 2),
        "sample_rate":               sample_rate,
        "channels":                  original_channels,
        "estimated_pause_count":     pause_count,
        "estimated_silence_seconds": round(estimated_silence_seconds, 2),
    }


import soundfile as sf
import librosa
import numpy as np


def analyze_audio(file_path: str) -> dict:
    """Analyze basic audio properties and estimate pauses."""

    audio, sample_rate = sf.read(file_path)

    # Remember the original number of channels.
    if audio.ndim == 2:
        original_channels = audio.shape[1]
        audio = audio.mean(axis=1)
    else:
        original_channels = 1

    duration_seconds = len(audio) / sample_rate

    # Calculate audio energy in short frames.
    rms = librosa.feature.rms(
        y=audio.astype(np.float32),
        frame_length=2048,
        hop_length=512,
    )[0]

    # Estimate which frames contain silence.
    threshold = max(float(np.max(rms)) * 0.05, 1e-5)
    silent_frames = rms < threshold

    # Count continuous silent sections of at least 0.3 seconds.
    min_pause_frames = int(
        0.3 * sample_rate / 512
    )

    pause_count = 0
    silent_run = 0
    estimated_silence_seconds = 0.0

    for is_silent in silent_frames:
        if is_silent:
            silent_run += 1
        else:
            if silent_run >= min_pause_frames:
                pause_count += 1
                estimated_silence_seconds += (
                    silent_run * 512 / sample_rate
                )
            silent_run = 0

    # Include a silent section that continues to the end.
    if silent_run >= min_pause_frames:
        pause_count += 1
        estimated_silence_seconds += (
            silent_run * 512 / sample_rate
        )

    return {
        "duration_seconds": round(duration_seconds, 2),
        "sample_rate": sample_rate,
        "channels": original_channels,
        "estimated_pause_count": pause_count,
        "estimated_silence_seconds": round(
            estimated_silence_seconds, 2
        ),
    }

import re


def analyze_speech_content(transcript: str, duration_seconds: float) -> dict:
    """Estimate speaking rate and count common filler words or phrases."""

    words = re.findall(r"\b[\w']+\b", transcript.lower())
    word_count = len(words)

    if duration_seconds > 0:
        speaking_rate = round(word_count / duration_seconds * 60, 1)
    else:
        speaking_rate = 0.0

    # Match longer phrases first to avoid counting their words twice.
    filler_pattern = re.compile(
        r"\b(?:you\s+know|i\s+mean|kind\s+of|sort\s+of|"
        r"um|uh|erm|actually|basically)\b",
        re.IGNORECASE,
    )
    filler_matches = filler_pattern.findall(transcript)
    filler_counts = {}

    for phrase in filler_matches:
        key = phrase.lower()
        filler_counts[key] = filler_counts.get(key, 0) + 1

    feedback = []

    if word_count < 5:
        feedback.append(
            "The transcript is very short, so speaking-rate feedback "
            "may not be meaningful. Try speaking for 30–60 seconds."
        )
    else:
        if speaking_rate < 100:
            feedback.append(
                "Your estimated speaking rate is slow. If your speech "
                "feels hesitant, try practising a slightly steadier pace."
            )
        elif speaking_rate <= 160:
            feedback.append(
                "Your estimated speaking rate is within a commonly "
                "comfortable practice range. Check whether it feels natural."
            )
        else:
            feedback.append(
                "Your estimated speaking rate is fast. Practise pausing "
                "between ideas if listeners may find it difficult to follow."
            )

    total_fillers = sum(filler_counts.values())

    if total_fillers:
        feedback.append(
            f"The transcript contains {total_fillers} possible filler "
            "words or phrases. Review them and practise replacing "
            "unnecessary fillers with brief pauses."
        )
    else:
        feedback.append(
            "No tracked filler words were found in the transcript. "
            "Whisper may miss some fillers, so this is not a guarantee "
            "that none occurred."
        )

    return {
        "transcript_word_count": word_count,
        "estimated_speaking_rate_wpm": speaking_rate,
        "estimated_filler_count": total_fillers,
        "filler_counts": filler_counts,
        "feedback": feedback,
    }

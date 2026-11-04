"""Answer evaluation: concept coverage + delivery + structure, with actionable tips."""
STAR = ["situation", "task", "action", "result"]

def evaluate_answer(q, transcript, wpm=None, fillers=0):
    text = (transcript or "").lower()
    words = len(text.split())
    hits = [k for k in q["keywords"] if k.lower() in text]
    missing = [k for k in q["keywords"] if k not in hits]
    concept = len(hits) / len(q["keywords"])

    delivery = max(0.0, 1 - fillers / max(1, words / 10))
    if wpm:
        delivery *= 1.0 if 100 <= wpm <= 160 else 0.7
    length = 1.0 if 40 <= words <= 220 else (words / 40 if words < 40 else 0.6)

    score = round(100 * (0.6 * concept + 0.25 * delivery + 0.15 * length)) if words else 0
    tips = []
    if missing: tips.append("Try to cover: " + ", ".join(missing) + ".")
    if words < 40: tips.append(f"Your answer is short ({words} words). Aim for 40-220 words with an example.")
    if fillers: tips.append(f"Replace {fillers} filler word(s) with short pauses.")
    if wpm and not 100 <= wpm <= 160: tips.append(f"Pace was about {round(wpm)} WPM; aim for 100-160.")
    if q["topic"] == "Behavioral":
        used = [w for w in STAR if w in text]
        if len(used) < 4: tips.append("Structure the story with STAR: Situation, Task, Action, Result.")
    if not tips: tips.append("Strong answer. Add a measurable result to stand out.")
    return {"question_id": q["id"], "topic": q["topic"], "score": score,
            "matched": hits, "missing": missing, "tips": tips[:4]}

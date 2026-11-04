"""
AI Interview Preparation Platform — FastAPI backend
Run:  uvicorn backend.main:app --reload
"""
import json, os, shutil, subprocess, tempfile

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import auth
from backend.audio_analysis import analyze_audio
from backend.evaluation import evaluate_answer
from backend.speech import analyze_speech_content

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MAX_UPLOAD = 25 * 1024 * 1024  # 25 MB

# ── Load questions ──────────────────────────────────────────────────────────
with open(os.path.join(BASE_DIR, "questions.json"), encoding="utf-8") as f:
    QUESTIONS = json.load(f)
BY_ID = {q["id"]: q for q in QUESTIONS}

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Interview Preparation Platform",
    version="2.1.0",
    description=(
        "Practice interview answers by voice, video or text; "
        "get scored feedback and track progress."
    ),
)

# Allow any localhost or file origin so the frontend works both when
# served by uvicorn (/app) and when opened directly in a browser during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_origins=["null"],        # allow file:// origins (browser opens HTML directly)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ─────────────────────────────────────────────────────────────────
class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=6, max_length=100)


class TextAnswer(BaseModel):
    question_id: int
    answer: str = Field(max_length=5000)


# ── Auth helpers ─────────────────────────────────────────────────────────────
def current_user(authorization: str = Header(None)) -> int:
    token = (authorization or "").removeprefix("Bearer ").strip()
    uid   = auth.user_from_token(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return uid


def save_attempt(uid: int, ev: dict) -> None:
    c = auth.get_db()
    with c:
        c.execute(
            "INSERT INTO attempts(user_id,qid,topic,score) VALUES(?,?,?,?)",
            (uid, ev["question_id"], ev["topic"], ev["score"]),
        )
    c.close()


# ── ffmpeg conversion ────────────────────────────────────────────────────────
def to_wav(src: str) -> str:
    """Convert any audio/video upload to 16 kHz mono WAV (requires ffmpeg)."""
    if not shutil.which("ffmpeg"):
        return src
    dst = src + ".wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", dst],
        check=True, capture_output=True, timeout=180,
    )
    return dst


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    """Health check — returns {status: ok}."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/app/")


@app.post("/auth/register", tags=["Auth"])
def register(c: Credentials):
    """Register a new account. Returns a bearer token."""
    token = auth.register(c.username, c.password)
    if not token:
        raise HTTPException(status_code=409, detail="Username already taken.")
    return {"token": token, "username": c.username.lower()}


@app.post("/auth/login", tags=["Auth"])
def login(c: Credentials):
    """Authenticate and return a bearer token."""
    token = auth.login(c.username, c.password)
    if not token:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    return {"token": token, "username": c.username.lower()}


@app.delete("/me", tags=["Auth"])
def delete_account(uid: int = Depends(current_user)):
    """Delete the authenticated account and all its data."""
    c = auth.get_db()
    with c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    c.close()
    return {"deleted": True}


@app.get("/questions", tags=["Questions"])
def questions(role: str | None = None):
    """
    Return all questions grouped by role, or filtered to a single role.
    Keywords are excluded from the response.
    """
    out: dict[str, list] = {}
    for q in QUESTIONS:
        if role and q["role"] != role:
            continue
        out.setdefault(q["role"], []).append(
            {k: v for k, v in q.items() if k != "keywords"}
        )
    return out.get(role, []) if role else out


@app.post("/evaluate-text", tags=["Evaluation"])
def evaluate_text(body: TextAnswer, uid: int = Depends(current_user)):
    """Evaluate a typed answer against the target question."""
    if body.question_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown question ID.")
    fillers = analyze_speech_content(body.answer, 0)["estimated_filler_count"]
    ev = evaluate_answer(BY_ID[body.question_id], body.answer, None, fillers)
    save_attempt(uid, ev)
    return ev


@app.get("/progress", tags=["Progress"])
def progress(uid: int = Depends(current_user)):
    """Return per-topic averages and the 10 most recent attempt scores."""
    c = auth.get_db()
    topics = [
        {"topic": t, "avg": round(a), "attempts": n, "weak": a < 60}
        for t, a, n in c.execute(
            "SELECT topic, AVG(score), COUNT(*) FROM attempts "
            "WHERE user_id=? GROUP BY topic ORDER BY AVG(score)",
            (uid,),
        )
    ]
    recent = [
        {"topic": t, "score": s, "created": d}
        for t, s, d in c.execute(
            "SELECT topic, score, created FROM attempts "
            "WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (uid,),
        )
    ]
    c.close()
    return {"topics": topics, "recent": recent}


@app.post("/analyze-audio", tags=["Audio"])
async def analyze_uploaded_audio(
    file: UploadFile = File(...),
    question_id: int | None = Form(None),
    uid: int = Depends(current_user),
):
    """
    Accept an audio (wav/webm/mp3) or video (webm/mp4) recording.
    Returns transcription, speech analysis, audio metrics, and optional evaluation.
    """
    paths: list[str] = []
    try:
        # Save upload to a temp file
        suffix = os.path.splitext(file.filename or "")[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            paths.append(tmp.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(status_code=413, detail="File too large (max 25 MB).")
                tmp.write(chunk)

        # Convert to WAV if needed
        wav = to_wav(paths[0])
        if wav != paths[0]:
            paths.append(wav)

        # Heavy import — loaded on first real request
        from backend.transcription import transcribe_audio  # noqa: PLC0415

        audio  = analyze_audio(wav)
        trans  = transcribe_audio(wav)
        speech = analyze_speech_content(trans["text"], audio["duration_seconds"])

        evaluation = None
        if question_id is not None and question_id in BY_ID:
            evaluation = evaluate_answer(
                BY_ID[question_id],
                trans["text"],
                speech["estimated_speaking_rate_wpm"],
                speech["estimated_filler_count"],
            )
            save_attempt(uid, evaluation)

        return {
            "filename":      file.filename,
            "analysis":      audio,
            "transcription": trans,
            "speech_content": speech,
            "evaluation":    evaluation,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process recording: {exc}",
        ) from exc
    finally:
        await file.close()
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass


# ── Static frontend ──────────────────────────────────────────────────────────
_frontend_dir = os.path.join(BASE_DIR, "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/app", StaticFiles(directory=_frontend_dir, html=True), name="frontend")

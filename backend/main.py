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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_UPLOAD = 25 * 1024 * 1024  # 25 MB

with open(os.path.join(BASE_DIR, "questions.json"), encoding="utf-8") as f:
    QUESTIONS = json.load(f)
BY_ID = {q["id"]: q for q in QUESTIONS}

app = FastAPI(title="AI Interview Preparation Platform", version="2.0.0",
              description="Practice interview answers by voice, video or text; get scored feedback and track progress.")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=100)


class TextAnswer(BaseModel):
    question_id: int
    answer: str = Field(max_length=5000)


def current_user(authorization: str = Header(None)) -> int:
    uid = auth.user_from_token((authorization or "").removeprefix("Bearer ").strip())
    if not uid:
        raise HTTPException(status_code=401, detail="Please log in.")
    return uid


def save_attempt(uid, ev):
    c = auth.get_db()
    with c:
        c.execute("INSERT INTO attempts(user_id,qid,topic,score) VALUES(?,?,?,?)", (uid, ev["question_id"], ev["topic"], ev["score"]))
    c.close()


def to_wav(src):
    """Convert any audio/video upload to 16 kHz mono WAV (needs ffmpeg; skipped if missing)."""
    if not shutil.which("ffmpeg"):
        return src
    dst = src + ".wav"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", dst],
                   check=True, capture_output=True, timeout=180)
    return dst


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/app/")


@app.post("/auth/register")
def register(c: Credentials):
    token = auth.register(c.username, c.password)
    if not token:
        raise HTTPException(status_code=409, detail="Username already taken.")
    return {"token": token, "username": c.username.lower()}


@app.post("/auth/login")
def login(c: Credentials):
    token = auth.login(c.username, c.password)
    if not token:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    return {"token": token, "username": c.username.lower()}


@app.delete("/me")
def delete_account(uid: int = Depends(current_user)):
    c = auth.get_db()
    with c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))  # tokens and attempts cascade
    c.close()
    return {"deleted": True}


@app.get("/questions")
def questions(role: str | None = None):
    out = {}
    for q in QUESTIONS:
        if role and q["role"] != role:
            continue
        out.setdefault(q["role"], []).append({k: v for k, v in q.items() if k != "keywords"})
    return out.get(role, []) if role else out


@app.post("/evaluate-text")
def evaluate_text(body: TextAnswer, uid: int = Depends(current_user)):
    if body.question_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown question.")
    fillers = analyze_speech_content(body.answer, 0)["estimated_filler_count"]
    ev = evaluate_answer(BY_ID[body.question_id], body.answer, None, fillers)
    save_attempt(uid, ev)
    return ev


@app.get("/progress")
def progress(uid: int = Depends(current_user)):
    c = auth.get_db()
    topics = [{"topic": t, "avg": round(a), "attempts": n, "weak": a < 60} for t, a, n in c.execute(
        "SELECT topic, AVG(score), COUNT(*) FROM attempts WHERE user_id=? GROUP BY topic ORDER BY AVG(score)", (uid,))]
    recent = [{"topic": t, "score": s, "created": d} for t, s, d in c.execute(
        "SELECT topic, score, created FROM attempts WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))]
    c.close()
    return {"topics": topics, "recent": recent}


@app.post("/analyze-audio")
async def analyze_uploaded_audio(file: UploadFile = File(...), question_id: int | None = Form(None),
                                 uid: int = Depends(current_user)):
    """Accepts audio (wav/webm/mp3...) or video (webm/mp4) recordings."""
    paths = []
    try:
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(file.filename or "")[1] or ".wav", delete=False) as tmp:
            paths.append(tmp.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(status_code=413, detail="File too large (max 25 MB).")
                tmp.write(chunk)
        wav = to_wav(paths[0])
        if wav != paths[0]:
            paths.append(wav)

        from backend.transcription import transcribe_audio  # heavy import, loaded on first use
        audio = analyze_audio(wav)
        trans = transcribe_audio(wav)
        speech = analyze_speech_content(trans["text"], audio["duration_seconds"])
        evaluation = None
        if question_id in BY_ID:
            evaluation = evaluate_answer(BY_ID[question_id], trans["text"],
                                         speech["estimated_speaking_rate_wpm"], speech["estimated_filler_count"])
            save_attempt(uid, evaluation)
        return {"evaluation": evaluation, "filename": file.filename, "analysis": audio,
                "transcription": trans, "speech_content": speech}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process recording: {exc}") from exc
    finally:
        await file.close()
        for p in paths:
            if os.path.exists(p):
                os.remove(p)


app.mount("/app", StaticFiles(directory=os.path.join(BASE_DIR, "..", "frontend"), html=True), name="frontend")

# AI Interview Preparation Platform
B Ramsingh (23C002675) · B.Tech CSE (AI & ML), 4th Year

Practice interview questions by **voice, video or text**, get a scored evaluation with tips, and track weak topics.
Based on *AI Communication Coach* by Ruchasa Johnson, used and extended with the author's permission.

## Features
- Accounts (register/login, hashed passwords, per-user progress, delete account)
- Role-based question bank (15 questions, 5 roles) · voice, **video** and typed answers
- Speech-to-text (faster-whisper, runs locally), live browser captions, pace / pause / filler analysis
- Scoring: 60% concept coverage, 25% delivery, 15% length; STAR check for behavioral questions
- Topic progress with weak-topic flags · health check · 25 MB upload limit
- Video is analysed in memory and **not stored**; only scores are saved

## Run locally
```
python -m venv venv && .\venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt                         # also install ffmpeg (needed for video)
python -m uvicorn backend.main:app --reload --port 8000
```
Open http://127.0.0.1:8000/app · API docs at /docs · tests: `python -m backend.test_core`

## Deploy (Render, free tier)
1. Push this folder to your GitHub repo.
2. Render dashboard → New → Web Service → connect the repo → Runtime **Docker** (it reads `render.yaml`).
3. Wait for the build (several minutes: installs ffmpeg and downloads the speech model). Open the `.onrender.com` URL.
HTTPS is provided automatically, which browsers require for camera and microphone.
Notes: free plans sleep when idle and reset SQLite data on redeploy; for persistent data use a paid plan with a disk
(`DB_PATH=/data/interview.db`) or move to a hosted database. If memory is tight (512 MB), keep the `tiny` model.
Any Docker host (Railway, Fly.io, a VPS) works with the same `Dockerfile`.

## Limitations
Scoring is a keyword-based baseline, not a judgement of interview success. Transcripts and audio measurements are estimates.
No facial or posture analysis yet (video is used for practice and its audio is analysed).

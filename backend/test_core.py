"""Run: python -m backend.test_core   (no server or speech model needed)"""
import json, os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
from backend import auth
from backend.evaluation import evaluate_answer
from backend.speech import analyze_speech_content

assert auth.verify_password("secret1", auth.hash_password("secret1"))
assert not auth.verify_password("wrong", auth.hash_password("secret1"))
t = auth.register("Ruth", "secret1"); assert t and auth.user_from_token(t)
assert auth.register("ruth", "other12") is None          # duplicate
assert auth.login("RUTH", "secret1") and not auth.login("ruth", "bad")
q = json.load(open(os.path.join(os.path.dirname(__file__), "questions.json"), encoding="utf-8"))[0]
assert evaluate_answer(q, "encapsulation inheritance polymorphism abstraction " * 8, 130, 0)["score"] >= 90
assert analyze_speech_content("um you know it works", 3)["estimated_filler_count"] == 2
print("core tests OK")

"""Accounts and storage (SQLite): PBKDF2 password hashing and bearer tokens."""
import hashlib, hmac, os, secrets, sqlite3

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "interview.db"))


def get_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tokens(token TEXT PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        qid INT, topic TEXT, score INT, created TEXT DEFAULT CURRENT_TIMESTAMP);""")
    return c


def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${h}"


def verify_password(pw, stored):
    salt, _ = stored.split("$")
    return hmac.compare_digest(hash_password(pw, salt), stored)


def _new_token(c, uid):
    t = secrets.token_urlsafe(32)
    with c:
        c.execute("INSERT INTO tokens VALUES(?,?)", (t, uid))
    return t


def register(username, password):
    c = get_db()
    try:
        with c:
            uid = c.execute("INSERT INTO users(username,pw_hash) VALUES(?,?)", (username.lower(), hash_password(password))).lastrowid
        return _new_token(c, uid)
    except sqlite3.IntegrityError:
        return None
    finally:
        c.close()


def login(username, password):
    c = get_db()
    row = c.execute("SELECT id, pw_hash FROM users WHERE username=?", (username.lower(),)).fetchone()
    token = _new_token(c, row[0]) if row and verify_password(password, row[1]) else None
    c.close()
    return token


def user_from_token(token):
    if not token:
        return None
    c = get_db()
    row = c.execute("SELECT user_id FROM tokens WHERE token=?", (token,)).fetchone()
    c.close()
    return row[0] if row else None

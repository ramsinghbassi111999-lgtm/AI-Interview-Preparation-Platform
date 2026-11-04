/**
 * interview.js
 * Extends the core page with: auth, server-side questions, video recording,
 * typed-answer evaluation and progress tracking.
 */

/* ─── Base URL & state ─── */
const BASE  = API.replace("/analyze-audio", "");
let   QS    = {};         // questions from server, keyed by role
let   currentQ = null;    // active question object
let   TOKEN = localStorage.getItem("ai.token") || "";

/* ─────────────────────────────────────────────
   FETCH WRAPPER
   • Attaches Bearer token to every API call
   • Appends question_id to audio-analysis forms
   • Intercepts 401s to show auth sheet
   • Reads evaluation from audio-analysis response
───────────────────────────────────────────── */
const _rawFetch = window.fetch;
window.fetch = async (url, opts = {}) => {
  const str = String(url);

  // Attach auth header for all calls to our API
  if (str.startsWith(BASE) && TOKEN) {
    opts.headers = { ...(opts.headers || {}), Authorization: "Bearer " + TOKEN };
  }

  // Inject question_id into audio-analysis form submissions
  if (url === API && opts.body instanceof FormData && currentQ) {
    opts.body.append("question_id", currentQ.id);
  }

  const res = await _rawFetch(url, opts);

  // Trigger auth sheet on 401 (except from auth endpoints themselves)
  if (res.status === 401 && !str.includes("/auth/")) {
    showAuth("Please sign in to continue.");
  }

  // Show evaluation result if present in audio-analysis response
  if (url === API && res.ok) {
    res.clone().json().then(d => { if (d && d.evaluation) showEval(d.evaluation); }).catch(() => {});
  }

  return res;
};

/* Shorthand helpers */
const apiCall = (path, opts)  => window.fetch(BASE + path, opts);
const apiPost = (path, body)  => apiCall(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body)
});

/* ─────────────────────────────────────────────
   SERVER QUESTIONS
   Fetches questions from /questions and replaces
   the in-page prompt text when in interview mode.
───────────────────────────────────────────── */
const _corePrompt = window.prompt;      // save reference used in core script

/** Override renderPrompt to prefer server questions when available. */
const _coreRenderPrompt = window.renderPrompt || function(){};
window.renderPrompt = function () {
  _coreRenderPrompt();                  // let core script set defaults first

  if (mode === "interview") {
    const list = QS[role];
    if (list && list.length) {
      currentQ = list[idx % list.length];
      const qEl    = document.getElementById("question");
      const metaEl = document.getElementById("qmeta");
      if (qEl)    qEl.textContent   = currentQ.question;
      if (metaEl) metaEl.textContent =
        "Question " + (idx + 1) + " · " + role + " · " +
        currentQ.topic.toUpperCase() + " · " + currentQ.difficulty.toUpperCase();
      return;
    }
  }
  currentQ = null;
};

/* Load questions on startup */
_rawFetch(BASE + "/questions")
  .then(r => r.json())
  .then(d => { QS = d; window.renderPrompt(); })
  .catch(() => { /* backend offline — use inline prompts */ });

/* ─────────────────────────────────────────────
   AUTH SHEET
───────────────────────────────────────────── */
function showAuth(msg) {
  const msgEl = document.getElementById("authMsg");
  if (msgEl && msg) msgEl.textContent = msg;
  const box = document.getElementById("authBox");
  if (box) box.classList.add("show");
  const au = document.getElementById("au");
  if (au) au.focus();
}

function hideAuth() {
  const box = document.getElementById("authBox");
  if (box) box.classList.remove("show");
}

// Close auth sheet when clicking the backdrop
document.getElementById("authBox").addEventListener("click", e => {
  if (e.target === e.currentTarget) hideAuth();
});

async function authenticate(path) {
  const au  = document.getElementById("au");
  const ap  = document.getElementById("ap");
  const err = document.getElementById("authErr");
  if (!au || !ap || !err) return;

  err.textContent = "";
  const res  = await apiPost(path, { username: au.value.trim(), password: ap.value });
  const data = await res.json();

  if (!res.ok) {
    err.textContent = typeof data.detail === "string"
      ? data.detail
      : "Username: 3–30 chars (letters/numbers); password: 6+ chars.";
    return;
  }

  TOKEN = data.token;
  localStorage.setItem("ai.token", TOKEN);
  localStorage.setItem("ai.user",  data.username);
  ap.value = "";
  hideAuth();

  /* Show account controls in progress section */
  const acct = document.getElementById("acctSection");
  if (acct) acct.hidden = false;

  /* Update nav button */
  const navBtn = document.getElementById("topAuthBtn");
  if (navBtn) { navBtn.textContent = data.username; navBtn.onclick = signOut; }

  loadProgress();
}

const form = document.getElementById("authForm");
if (form) form.onsubmit = e => { e.preventDefault(); authenticate("/auth/login"); };

const doReg = document.getElementById("doReg");
if (doReg) doReg.onclick = () => {
  const f = document.getElementById("authForm");
  if (f && !f.reportValidity()) return;
  authenticate("/auth/register");
};

function signOut() {
  TOKEN = "";
  localStorage.removeItem("ai.token");
  localStorage.removeItem("ai.user");
  const topicBars = document.getElementById("topicBars");
  if (topicBars) topicBars.replaceChildren();
  const acct = document.getElementById("acctSection");
  if (acct) acct.hidden = true;
  const navBtn = document.getElementById("topAuthBtn");
  if (navBtn) { navBtn.textContent = "Sign in"; navBtn.onclick = showAuth; }
  showAuth("Signed out. Sign in to continue.");
}

/* Boot: show auth if no token */
if (TOKEN) {
  const acct = document.getElementById("acctSection");
  if (acct) acct.hidden = false;
  const navBtn = document.getElementById("topAuthBtn");
  if (navBtn) {
    const user = localStorage.getItem("ai.user");
    if (user) { navBtn.textContent = user; navBtn.onclick = signOut; }
  }
  loadProgress();
} else {
  showAuth();
}

/* ─────────────────────────────────────────────
   TYPED-ANSWER EVALUATION
───────────────────────────────────────────── */
function showEval(ev) {
  const scoreEl   = document.getElementById("evalScore");
  const tipsEl    = document.getElementById("evalTips");
  const missingEl = document.getElementById("evalMissing");
  const box       = document.getElementById("evalBox");
  const badge     = document.getElementById("sessionBadge");

  if (scoreEl) scoreEl.textContent = ev.score + "/100";
  if (missingEl) missingEl.textContent = ev.missing && ev.missing.length
    ? "Missing concepts: " + ev.missing.join(", ") + "."
    : "All key concepts covered.";

  if (tipsEl) {
    tipsEl.replaceChildren();
    (ev.tips || []).forEach(t => {
      const li = document.createElement("li");
      li.textContent = t;
      tipsEl.appendChild(li);
    });
  }

  if (box)   box.style.display = "block";
  if (badge) { badge.textContent = "Score " + ev.score; badge.className = "tag blue"; }

  /* Update score ring */
  if (typeof setRing === "function") setRing(ev.score);

  loadProgress();
}

const evalTyped = document.getElementById("evalTyped");
if (evalTyped) {
  evalTyped.onclick = async () => {
    if (!currentQ) {
      if (typeof setStatus === "function") setStatus("Select Interview mode and start a session first.");
      return;
    }
    const typed = document.getElementById("typed");
    const answer = typed ? typed.value.trim() : "";
    if (!answer) {
      if (typeof setStatus === "function") setStatus("Type an answer before evaluating.");
      return;
    }
    const res = await apiPost("/evaluate-text", { question_id: currentQ.id, answer });
    if (res.ok) {
      showEval(await res.json());
      if (typeof goStep === "function") goStep(4);
      if (typeof setStatus === "function") setStatus("Typed answer evaluated.");
    } else if (res.status !== 401) {
      if (typeof setStatus === "function") setStatus("Could not evaluate the answer. Is the backend running?");
    }
  };
}

/* ─────────────────────────────────────────────
   VIDEO RECORDING
───────────────────────────────────────────── */
let cam = null, mr = null, vidChunks = [], speechRec = null;

function startCaptions() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  speechRec = new SR();
  speechRec.continuous     = true;
  speechRec.interimResults = true;
  speechRec.lang           = "en-US";
  speechRec.onresult = e => {
    let t = "";
    for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
    const liveEl = document.getElementById("live");
    if (liveEl) liveEl.textContent = "Live captions: " + t;
  };
  try { speechRec.start(); } catch (_) {}
}

function stopCaptions() {
  if (speechRec) { try { speechRec.stop(); } catch(_){} speechRec = null; }
}

const camOn  = document.getElementById("camOn");
const camOff = document.getElementById("camOff");
const vidRec = document.getElementById("vidRec");

if (camOn) camOn.onclick = async () => {
  try {
    cam = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    const v = document.getElementById("cam");
    if (v) { v.srcObject = cam; v.muted = true; v.style.display = "block"; v.play(); }
    if (vidRec) vidRec.disabled = false;
    if (camOff) camOff.disabled = false;
    if (typeof setStatus === "function") setStatus("Camera ready. Press Record video.");
  } catch(e) {
    if (typeof setStatus === "function") setStatus("Camera unavailable: " + e.message);
  }
};

if (camOff) camOff.onclick = () => {
  if (mr && mr.state === "recording") mr.stop();
  if (cam) cam.getTracks().forEach(t => t.stop());
  cam = null;
  const v = document.getElementById("cam");
  if (v) v.style.display = "none";
  if (vidRec) vidRec.disabled = true;
  if (camOff) camOff.disabled = true;
};

if (vidRec) vidRec.onclick = () => {
  if (mr && mr.state === "recording") { mr.stop(); return; }
  if (!cam) return;

  vidChunks = [];
  const liveEl = document.getElementById("live");
  if (liveEl) liveEl.textContent = "";

  const v = document.getElementById("cam");
  if (v) { v.controls = false; v.removeAttribute("src"); v.srcObject = cam; v.muted = true; v.play(); }

  const type = ["video/webm;codecs=vp8,opus","video/webm","video/mp4"]
    .find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t));

  mr = new MediaRecorder(cam, type ? { mimeType: type } : {});
  mr.ondataavailable = e => e.data.size && vidChunks.push(e.data);
  mr.onstop = () => {
    stopCaptions();
    // Assign to the shared `blob` variable used by the Analyze button
    window.blob = new Blob(vidChunks, { type: mr.mimeType || "video/webm" });
    blob = window.blob;

    if (v) { v.srcObject = null; v.muted = false; v.controls = true; v.src = URL.createObjectURL(blob); }

    const analyzeBtn = document.getElementById("analyze");
    if (analyzeBtn) analyzeBtn.disabled = false;
    if (vidRec) vidRec.textContent = "Record video";

    const badge = document.getElementById("sessionBadge");
    if (badge) { badge.textContent = "Video ready"; badge.className = "tag green"; }
    if (typeof setStatus === "function") setStatus("Video recorded. Tap Analyze to continue.");
  };

  mr.start();
  startCaptions();
  vidRec.textContent = "Stop recording";

  const badge = document.getElementById("sessionBadge");
  if (badge) badge.textContent = "Recording";
  if (typeof setStatus === "function") setStatus("Recording video answer…");
};

/* ─────────────────────────────────────────────
   PROGRESS (server-side)
───────────────────────────────────────────── */
async function loadProgress() {
  if (!TOKEN) return;
  try {
    const res = await apiCall("/progress");
    if (!res.ok) return;
    const data = await res.json();
    const el   = document.getElementById("topicBars");
    if (!el) return;

    el.replaceChildren();

    if (!data.topics || !data.topics.length) {
      const msg = document.createElement("p");
      msg.style.cssText = "font-size:13px;color:var(--label-3)";
      msg.textContent = "No evaluated answers yet. Complete an interview answer to see progress.";
      el.appendChild(msg);
      return;
    }

    data.topics.forEach(t => {
      const row  = document.createElement("div");
      row.className = "metric";

      const name = document.createElement("span");
      name.className   = "metric-name";
      name.textContent = t.topic + (t.weak ? " · needs practice" : "");

      const val = document.createElement("span");
      val.className   = "metric-val";
      val.textContent = t.avg;

      const track = document.createElement("div");
      track.className = "bar-track";
      const fill  = document.createElement("div");
      fill.className  = "bar-fill " + (t.weak ? "a" : "g");
      fill.style.width = t.avg + "%";
      track.appendChild(fill);

      row.append(name, val, track);
      el.appendChild(row);
    });
  } catch(_) { /* backend offline */ }
}

/* Account buttons */
const outBtn = document.getElementById("outBtn");
const delBtn = document.getElementById("delBtn");

if (outBtn) outBtn.onclick = signOut;
if (delBtn) delBtn.onclick = async () => {
  if (!confirm("Delete your account and all saved progress? This cannot be undone.")) return;
  const res = await apiCall("/me", { method: "DELETE" });
  if (res.ok) signOut();
};

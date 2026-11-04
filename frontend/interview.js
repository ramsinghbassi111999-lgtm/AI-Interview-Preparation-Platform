/* Interview-platform add-on: login, server questions, video recording, evaluation, progress. */
const BASE = API.replace("/analyze-audio", "");
let QS = {}, currentQ = null, TOKEN = localStorage.getItem("ai.token") || "";

/* ---------- fetch wrapper: auth header, question id, evaluation display ---------- */
const _fetch = window.fetch;
window.fetch = async (u, o = {}) => {
  if (String(u).startsWith(BASE) && TOKEN) o.headers = { ...(o.headers || {}), Authorization: "Bearer " + TOKEN };
  if (u === API && o.body instanceof FormData && currentQ) o.body.append("question_id", currentQ.id);
  const r = await _fetch(u, o);
  if (r.status === 401 && !String(u).includes("/auth/")) showAuth("Please log in to continue.");
  if (u === API && r.ok) r.clone().json().then(d => d.evaluation && showEval(d.evaluation));
  return r;
};
const call = (path, opts) => window.fetch(BASE + path, opts);
const post = (path, body) => call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/* ---------- questions ---------- */
const _prompt = prompt;
window.prompt = function () {
  _prompt();
  const list = QS[role];
  if (mode === "interview" && list && list.length) {
    currentQ = list[idx % list.length];
    $("question").textContent = currentQ.question;
    $("qmeta").textContent += " · " + currentQ.topic.toUpperCase() + " · " + currentQ.difficulty.toUpperCase();
  } else currentQ = null;
};
_fetch(BASE + "/questions").then(r => r.json()).then(d => { QS = d; prompt(); }).catch(() => {});

/* ---------- login / register ---------- */
const css = document.createElement("style");
css.textContent = "#authBox{position:fixed;inset:0;background:rgba(7,18,38,.96);display:none;align-items:center;justify-content:center;z-index:99}#authBox form{background:#101d36;border:1px solid #2b4268;border-radius:16px;padding:24px;width:min(360px,90vw);color:#e8f0ff}#authBox input{width:100%;margin:6px 0 12px;padding:10px;border-radius:8px;border:1px solid #2b4268;background:transparent;color:inherit;font:inherit}#authBox button{margin-right:8px}#authErr{color:#ff8a8a;min-height:1.2em}";
document.head.appendChild(css);
const box = document.createElement("div"); box.id = "authBox";
box.innerHTML = '<form id="authForm"><h2>AI Interview Preparation Platform</h2><p id="authMsg">Log in or create an account to save your progress.</p><label for="au">Username</label><input id="au" autocomplete="username" required minlength="3"><label for="ap">Password (6+ characters)</label><input id="ap" type="password" autocomplete="current-password" required minlength="6"><div id="authErr" role="alert"></div><button class="primary" type="submit" id="doLogin">Log in</button><button class="primary" type="button" id="doReg">Register</button></form>';
document.body.appendChild(box);
function showAuth(msg) { $("authMsg").textContent = msg || $("authMsg").textContent; box.style.display = "flex"; $("au").focus(); }
async function authenticate(path) {
  const r = await post(path, { username: $("au").value.trim(), password: $("ap").value });
  const d = await r.json();
  if (!r.ok) { $("authErr").textContent = typeof d.detail === "string" ? d.detail : "Username: 3-30 letters/numbers; password: 6+ characters."; return; }
  TOKEN = d.token; localStorage.setItem("ai.token", TOKEN); localStorage.setItem("ai.user", d.username);
  $("authErr").textContent = ""; box.style.display = "none"; $("ap").value = ""; loadProgress();
}
$("authForm").onsubmit = e => { e.preventDefault(); authenticate("/auth/login"); };
$("doReg").onclick = () => $("authForm").reportValidity() && authenticate("/auth/register");
function signOut() { TOKEN = ""; localStorage.removeItem("ai.token"); $("topicBars").replaceChildren(); showAuth("Signed out. Log in to continue."); }

/* ---------- evaluation display ---------- */
function fill(id, items) { const ul = $(id); ul.replaceChildren(); items.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); }); }
function showEval(ev) {
  $("evalScore").textContent = ev.score + "/100";
  fill("evalTips", ev.tips);
  $("evalMissing").textContent = ev.missing.length ? "Missing concepts: " + ev.missing.join(", ") : "All key concepts covered.";
  $("evalBox").style.display = "block";
  $("sessionBadge").textContent = "Score " + ev.score;
  loadProgress();
}
$("evalTyped").onclick = async () => {
  if (!currentQ) { setStatus("Typed answers need Interview mode with a question selected."); return; }
  const answer = $("typed").value.trim();
  if (!answer) { setStatus("Type an answer first."); return; }
  const r = await post("/evaluate-text", { question_id: currentQ.id, answer });
  if (r.ok) { showEval(await r.json()); step(4); setStatus("Typed answer evaluated."); } else if (r.status !== 401) setStatus("Could not evaluate the answer.");
};

/* ---------- video recording with live captions ---------- */
const vb = document.createElement("div");
vb.innerHTML = '<video id="cam" playsinline style="display:none;width:100%;margin-top:10px;border-radius:12px;background:#000"></video><div class="modes" style="margin-top:10px"><button class="mode" id="camOn">Camera on</button><button class="mode" id="vidRec" disabled>Record video</button><button class="mode" id="camOff" disabled>Camera off</button></div><div class="hint" id="live" aria-live="polite"></div>';
$("player").after(vb);
let cam = null, mr = null, chunks = [], rec = null;
function startLive() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition; if (!SR) return;
  rec = new SR(); rec.continuous = true; rec.interimResults = true; rec.lang = "en-US";
  rec.onresult = e => { let t = ""; for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript; $("live").textContent = "Live captions: " + t; };
  try { rec.start(); } catch (e) { /* already started */ }
}
function stopLive() { if (rec) { try { rec.stop(); } catch (e) {} rec = null; } }
$("camOn").onclick = async () => {
  try {
    cam = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    const v = $("cam"); v.srcObject = cam; v.muted = true; v.style.display = "block"; v.play();
    $("vidRec").disabled = false; $("camOff").disabled = false; setStatus("Camera ready. Press Record video.");
  } catch (e) { setStatus("Camera unavailable: " + e.message + ". Check browser permission (HTTPS is required online)."); }
};
$("camOff").onclick = () => {
  if (mr && mr.state === "recording") mr.stop();
  if (cam) cam.getTracks().forEach(t => t.stop());
  cam = null; $("cam").style.display = "none"; $("vidRec").disabled = true; $("camOff").disabled = true;
};
$("vidRec").onclick = () => {
  if (mr && mr.state === "recording") { mr.stop(); return; }
  if (!cam) return;
  chunks = []; $("live").textContent = "";
  const v = $("cam"); v.controls = false; v.removeAttribute("src"); v.srcObject = cam; v.muted = true; v.play();
  const type = ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"].find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t));
  mr = new MediaRecorder(cam, type ? { mimeType: type } : {});
  mr.ondataavailable = e => e.data.size && chunks.push(e.data);
  mr.onstop = () => {
    stopLive();
    blob = new Blob(chunks, { type: mr.mimeType || "video/webm" });   // reuses the existing Analyze button
    v.srcObject = null; v.muted = false; v.controls = true; v.src = URL.createObjectURL(blob);
    $("analyze").disabled = false; $("vidRec").textContent = "Record video";
    $("sessionBadge").textContent = "Answer ready"; setStatus("Video recorded. Analyze it, or record again.");
  };
  mr.start(); startLive(); $("vidRec").textContent = "Stop recording"; $("sessionBadge").textContent = "Recording"; setStatus("Recording video answer…");
};

/* ---------- progress + account actions ---------- */
const acct = document.createElement("div"); acct.className = "modes"; acct.style.marginTop = "12px";
acct.innerHTML = '<button class="mode" id="outBtn">Sign out</button><button class="mode" id="delBtn">Delete my account</button>';
$("topicProgress").appendChild(acct);
$("outBtn").onclick = signOut;
$("delBtn").onclick = async () => {
  if (!confirm("Delete your account and all saved progress? This cannot be undone.")) return;
  const r = await call("/me", { method: "DELETE" });
  if (r.ok) { signOut(); }
};
async function loadProgress() {
  if (!TOKEN) return;
  try {
    const r = await call("/progress"); if (!r.ok) return;
    const d = await r.json(), el = $("topicBars"); el.replaceChildren();
    if (!d.topics.length) el.textContent = "No evaluated answers yet.";
    d.topics.forEach(t => {
      const row = document.createElement("div"); row.className = "metric";
      const name = document.createElement("span"); name.textContent = t.topic + (t.weak ? " (needs practice)" : "");
      const bar = document.createElement("span"); bar.className = "bar" + (t.weak ? " y" : " g");
      const i = document.createElement("i"); i.style.width = t.avg + "%"; bar.appendChild(i);
      const val = document.createElement("span"); val.className = "val"; val.textContent = t.avg;
      row.append(document.createElement("span"), name, bar, val); el.appendChild(row);
    });
  } catch (e) { /* backend offline */ }
}
if (TOKEN) loadProgress(); else showAuth();

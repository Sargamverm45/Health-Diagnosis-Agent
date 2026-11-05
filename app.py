"""
Web UI for the AI Health Triage Agent (demo, NOT a medical diagnosis tool).

Keep this file in the SAME folder as health_agent.py, then run:
    python app.py
A browser tab opens at http://127.0.0.1:8000 with a chat interface.
No extra installs needed (uses only Python + the 'requests' you already have).
"""
import json
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import health_agent as ha  # the agent logic you already have

PORT = 8000
PROFILE_FIELDS = ["age", "sex", "existing conditions", "medicines", "allergies"]

STATE = {"chat": None, "profile": {}, "transcript": []}
LOCK = threading.Lock()
API_KEY = ""

URGENCY_WORDS = ["EMERGENCY", "URGENT", "ROUTINE", "SELF-CARE"]
EMERGENCY_TEXT = (
    "What you describe may be serious. Call emergency services (112 in India) "
    "or go to the nearest hospital NOW. Do not wait for this app."
)


def detect_urgency(reply):
    """Find the urgency level on a line that mentions 'urgency'."""
    for line in reply.splitlines():
        if "urgency" in line.lower():
            found = [w for w in URGENCY_WORDS if w in line]
            if len(found) == 1:
                return found[0]
    return ""


def start_chat(profile):
    clean = {}
    for key in PROFILE_FIELDS:
        value = str(profile.get(key, "")).strip()[:200]
        if value:
            clean[key] = value
    STATE["profile"] = clean
    STATE["chat"] = ha.new_chat(API_KEY, clean)
    STATE["transcript"] = []


def friendly_error(err):
    text = str(err)
    low = text.lower()
    if "api key" in low or " 400" in text or " 401" in text or " 403" in text:
        return text + "  (Check that your Gemini API key is correct.)"
    if " 404" in text:
        return text + "  (The model name may be wrong. Change MODEL in health_agent.py.)"
    if " 429" in text:
        return text + "  (Free usage limit reached. Wait a minute and try again.)"
    return text


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        else:
            self._send(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            payload = {}

        if self.path == "/api/start":
            with LOCK:
                start_chat(payload.get("profile") or {})
            self._json({"ok": True})

        elif self.path == "/api/chat":
            message = str(payload.get("message", "")).strip()[:2000]
            if not message:
                return self._json({"error": "Please type a message."})
            with LOCK:
                STATE["transcript"].append(("You", message))
                if ha.has_red_flag(message):
                    STATE["transcript"].append(("System", "Emergency warning shown."))
                    return self._json({"emergency": True, "reply": EMERGENCY_TEXT})
                try:
                    reply = ha.send_with_retry(STATE["chat"], message)
                except Exception as e:
                    STATE["transcript"].pop()
                    return self._json({"error": friendly_error(e)})
                STATE["transcript"].append(("Agent", reply))
            self._json({"reply": reply, "urgency": detect_urgency(reply)})

        elif self.path == "/api/report":
            with LOCK:
                if not STATE["transcript"]:
                    return self._json({"error": "Describe your symptoms first."})
                try:
                    report = ha.send_with_retry(STATE["chat"], ha.REPORT_PROMPT)
                except Exception as e:
                    return self._json({"error": friendly_error(e)})
                path = ha.save_report(report, STATE["transcript"], STATE["profile"])
            self._json({"report": report, "path": path})

        else:
            self._send(404, "Not found", "text/plain; charset=utf-8")


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Health Triage Agent</title>
<style>
  :root {
    --bg:#f2f6f7; --card:#ffffff; --text:#1c2b33; --muted:#6a7b84; --line:#dfe7ea;
    --accent:#0d8a8a; --accent-d:#0a6f6f; --user:#0d8a8a; --user-t:#ffffff;
    --agent:#eef3f5; --warn:#fff4e5; --warn-t:#8a5300; --danger:#c62828; --danger-bg:#fdecea;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:#10181c; --card:#18232a; --text:#e6eef1; --muted:#8fa2ac; --line:#2a3a43;
      --accent:#26a9a9; --accent-d:#1f9090; --user:#1f9090; --user-t:#ffffff;
      --agent:#22313a; --warn:#3a2d14; --warn-t:#f0c274; --danger:#ff6b6b; --danger-bg:#3b1d1d;
    }
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { font-family: "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif;
         background: var(--bg); color: var(--text); display: flex; flex-direction: column; }
  header { background: var(--accent); color: #fff; padding: 14px 22px; display: flex;
           align-items: center; gap: 12px; }
  header .logo { font-size: 26px; font-weight: 700; background: #fff; color: var(--accent);
                 width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; }
  header h1 { font-size: 18px; margin: 0; }
  header p { font-size: 12.5px; margin: 2px 0 0; opacity: .9; }
  .banner { background: var(--warn); color: var(--warn-t); font-size: 13px; padding: 8px 22px;
            border-bottom: 1px solid var(--line); }
  main { flex: 1; min-height: 0; display: grid; grid-template-columns: 300px 1fr; gap: 16px;
         padding: 16px 22px; }
  aside, .chatbox { background: var(--card); border: 1px solid var(--line); border-radius: 14px; }
  aside { padding: 16px; overflow-y: auto; }
  aside h2 { font-size: 15px; margin: 0 0 4px; }
  aside .hint { font-size: 12.5px; color: var(--muted); margin: 0 0 12px; }
  label { display: block; font-size: 12.5px; color: var(--muted); margin: 10px 0 4px; }
  input[type=text], textarea {
    width: 100%; padding: 9px 11px; border: 1px solid var(--line); border-radius: 9px;
    background: var(--bg); color: var(--text); font: inherit; font-size: 14px; }
  input:focus, textarea:focus { outline: 2px solid var(--accent); border-color: transparent; }
  button { font: inherit; cursor: pointer; border: 0; border-radius: 9px; padding: 9px 14px;
           font-size: 14px; }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent-d); }
  .btn-ghost { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn-ghost:hover { background: var(--agent); }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .side-actions { display: grid; gap: 8px; margin-top: 16px; }
  .chatbox { display: flex; flex-direction: column; min-height: 0; }
  #chat { flex: 1; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; }
  .msg { max-width: 78%; padding: 11px 14px; border-radius: 14px; line-height: 1.5; font-size: 14.5px;
         word-wrap: break-word; }
  .msg p { margin: 0 0 6px; } .msg p:last-child { margin-bottom: 0; }
  .msg ul { margin: 4px 0 6px; padding-left: 20px; }
  .msg.agent { align-self: flex-start; background: var(--agent); border-bottom-left-radius: 4px; }
  .msg.user { align-self: flex-end; background: var(--user); color: var(--user-t);
              border-bottom-right-radius: 4px; white-space: pre-wrap; }
  .msg.error { align-self: center; background: var(--danger-bg); color: var(--danger); font-size: 13.5px; }
  .msg.emergency { align-self: stretch; max-width: 100%; background: var(--danger-bg);
                   border: 2px solid var(--danger); color: var(--danger); font-weight: 600; }
  .badge { display: inline-block; margin-top: 8px; padding: 3px 10px; border-radius: 99px;
           font-size: 12px; font-weight: 700; color: #fff; }
  .badge.EMERGENCY { background: #c62828; } .badge.URGENT { background: #e65100; }
  .badge.ROUTINE { background: #f9a825; color: #3b2a00; } .badge.SELF-CARE { background: #2e7d32; }
  .typing { align-self: flex-start; background: var(--agent); padding: 12px 16px; border-radius: 14px; }
  .typing span { display: inline-block; width: 7px; height: 7px; margin: 0 2px; border-radius: 50%;
                 background: var(--muted); animation: blink 1.2s infinite; }
  .typing span:nth-child(2) { animation-delay: .2s; } .typing span:nth-child(3) { animation-delay: .4s; }
  @keyframes blink { 0%,80%,100% { opacity: .25; } 40% { opacity: 1; } }
  .chips { padding: 0 18px 10px; display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { background: var(--agent); color: var(--text); border: 1px solid var(--line);
          border-radius: 99px; padding: 6px 12px; font-size: 13px; }
  .chip:hover { border-color: var(--accent); }
  form.composer { display: flex; gap: 10px; padding: 12px 14px; border-top: 1px solid var(--line); }
  form.composer input { flex: 1; }
  .modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: none;
              align-items: center; justify-content: center; padding: 20px; z-index: 10; }
  .modal-bg.show { display: flex; }
  .modal { background: var(--card); border-radius: 14px; width: min(720px, 100%); max-height: 88vh;
           display: flex; flex-direction: column; }
  .modal h3 { margin: 0; padding: 16px 20px 8px; }
  .modal pre { margin: 0; padding: 8px 20px 16px; overflow: auto; white-space: pre-wrap;
               font: 13.5px/1.55 Consolas, "Courier New", monospace; flex: 1; }
  .modal .row { display: flex; gap: 8px; justify-content: flex-end; padding: 12px 20px;
                border-top: 1px solid var(--line); flex-wrap: wrap; }
  .saved { padding: 0 20px 8px; font-size: 12.5px; color: var(--muted); }
  @media (max-width: 820px) {
    main { grid-template-columns: 1fr; overflow-y: auto; }
    aside { order: 2; } .chatbox { min-height: 70vh; } .msg { max-width: 92%; }
  }
</style>
</head>
<body>
<header>
  <div class="logo">+</div>
  <div>
    <h1>AI Health Triage Agent</h1>
    <p>Describe your symptoms and get guidance on what to do next</p>
  </div>
</header>
<div class="banner">Demo project. This is not a medical diagnosis and does not replace a doctor.
  In an emergency call 112 (India).</div>

<main>
  <aside>
    <h2>Your profile (optional)</h2>
    <p class="hint">Helps the agent give safer, more relevant guidance.</p>
    <label for="age">Age</label><input type="text" id="age" placeholder="e.g. 24">
    <label for="sex">Sex</label><input type="text" id="sex" placeholder="e.g. female">
    <label for="cond">Existing conditions</label><input type="text" id="cond" placeholder="e.g. asthma">
    <label for="meds">Medicines you take</label><input type="text" id="meds" placeholder="e.g. none">
    <label for="alg">Allergies</label><input type="text" id="alg" placeholder="e.g. penicillin">
    <div class="side-actions">
      <button class="btn-primary" id="startBtn">Start new consultation</button>
      <button class="btn-ghost" id="reportBtn">Generate triage report</button>
    </div>
  </aside>

  <section class="chatbox">
    <div id="chat"></div>
    <div class="chips" id="chips">
      <button class="chip" type="button">I have a headache and fever since yesterday</button>
      <button class="chip" type="button">I have a sore throat and cough for 3 days</button>
      <button class="chip" type="button">I have stomach pain and nausea</button>
    </div>
    <form class="composer" id="composer" autocomplete="off">
      <input type="text" id="msg" placeholder="Type your symptoms here..." autofocus>
      <button class="btn-primary" id="send" type="submit">Send</button>
    </form>
  </section>
</main>

<div class="modal-bg" id="modalBg">
  <div class="modal">
    <h3>Triage report</h3>
    <div class="saved" id="savedPath"></div>
    <pre id="reportText"></pre>
    <div class="row">
      <button class="btn-ghost" id="copyBtn" type="button">Copy</button>
      <button class="btn-ghost" id="dlBtn" type="button">Download .txt</button>
      <button class="btn-primary" id="closeBtn" type="button">Close</button>
    </div>
  </div>
</div>

<script>
const $ = (s) => document.querySelector(s);
const chatEl = $('#chat'), inputEl = $('#msg'), sendBtn = $('#send');
let busy = false, lastReport = '';

function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function inline(t) {
  return t.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/`(.+?)`/g, '<code>$1</code>');
}
function md(text) {
  const lines = esc(text).split('\n');
  let html = '', inList = false;
  for (const line of lines) {
    const li = line.match(/^\s*(?:[-*\u2022]|\d+\.)\s+(.*)$/);
    const h = line.match(/^\s*#{1,6}\s+(.*)$/);
    if (li) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += '<li>' + inline(li[1]) + '</li>';
      continue;
    }
    if (inList) { html += '</ul>'; inList = false; }
    if (h) html += '<p><b>' + inline(h[1]) + '</b></p>';
    else if (line.trim() !== '') html += '<p>' + inline(line) + '</p>';
  }
  if (inList) html += '</ul>';
  return html;
}

function scrollDown() { chatEl.scrollTop = chatEl.scrollHeight; }
function addMsg(kind, text, urgency) {
  const d = document.createElement('div');
  d.className = 'msg ' + kind;
  if (kind === 'agent') d.innerHTML = md(text); else d.textContent = text;
  if (urgency) {
    const b = document.createElement('div');
    b.className = 'badge ' + urgency;
    b.textContent = 'Urgency: ' + urgency;
    d.appendChild(b);
  }
  chatEl.appendChild(d);
  scrollDown();
}
function showTyping() {
  const t = document.createElement('div');
  t.className = 'typing'; t.id = 'typing';
  t.innerHTML = '<span></span><span></span><span></span>';
  chatEl.appendChild(t); scrollDown();
}
function hideTyping() { const t = $('#typing'); if (t) t.remove(); }
function setBusy(b) { busy = b; sendBtn.disabled = b; $('#reportBtn').disabled = b; $('#startBtn').disabled = b; }

async function post(url, body) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                               body: JSON.stringify(body || {}) });
  return r.json();
}

async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  $('#chips').style.display = 'none';
  addMsg('user', text);
  inputEl.value = '';
  setBusy(true); showTyping();
  try {
    const d = await post('/api/chat', { message: text });
    hideTyping();
    if (d.error) addMsg('error', d.error);
    else if (d.emergency) addMsg('emergency', '\u26A0 ' + d.reply);
    else addMsg('agent', d.reply, d.urgency);
  } catch (e) {
    hideTyping();
    addMsg('error', 'Could not reach the app. Make sure the program is still running in the terminal.');
  }
  setBusy(false); inputEl.focus();
}

function profile() {
  return { 'age': $('#age').value, 'sex': $('#sex').value, 'existing conditions': $('#cond').value,
           'medicines': $('#meds').value, 'allergies': $('#alg').value };
}

async function startConsultation() {
  setBusy(true);
  try { await post('/api/start', { profile: profile() }); } catch (e) {}
  chatEl.innerHTML = '';
  $('#chips').style.display = 'flex';
  addMsg('agent', "Hello! I'm a health triage assistant. Tell me what symptoms you are having " +
    "and I'll ask a few questions, then suggest possible causes and what to do next.\n\n" +
    "I'm not a doctor, so please see one for a proper diagnosis.");
  setBusy(false); inputEl.focus();
}

async function makeReport() {
  setBusy(true); showTyping();
  try {
    const d = await post('/api/report', {});
    hideTyping();
    if (d.error) addMsg('error', d.error);
    else {
      lastReport = d.report;
      $('#reportText').textContent = d.report;
      $('#savedPath').textContent = 'Saved on your computer: ' + d.path;
      $('#modalBg').classList.add('show');
    }
  } catch (e) { hideTyping(); addMsg('error', 'Could not create the report.'); }
  setBusy(false);
}

$('#composer').addEventListener('submit', (e) => { e.preventDefault(); send(inputEl.value); });
document.querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => send(c.textContent)));
$('#startBtn').addEventListener('click', startConsultation);
$('#reportBtn').addEventListener('click', makeReport);
$('#closeBtn').addEventListener('click', () => $('#modalBg').classList.remove('show'));
$('#copyBtn').addEventListener('click', () => navigator.clipboard && navigator.clipboard.writeText(lastReport));
$('#dlBtn').addEventListener('click', () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lastReport], { type: 'text/plain' }));
  a.download = 'triage_report.txt'; a.click();
});

startConsultation();
</script>
</body>
</html>
"""


def main():
    global API_KEY
    API_KEY = ha.get_key()
    if not API_KEY:
        sys.exit("No API key entered.")
    start_chat({})

    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        sys.exit(f"Port {PORT} is already in use. Close the other app.py window or change PORT.")

    url = f"http://127.0.0.1:{PORT}"
    print(f"\nHealth Triage UI running at {url}")
    print("A browser tab will open. Press Ctrl + C here to stop.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
"""
AI Health Triage Agent (Google Gemini, REST version) - educational demo.
NOT a medical diagnosis tool. Always consult a qualified doctor.

This version talks to Gemini with the 'requests' library only, so it
installs fine on 32-bit Python (no Rust / cryptography build needed).

Features:
  - optional patient profile (age, sex, conditions, medicines, allergies)
  - conversational symptom intake (1-2 follow-up questions at a time)
  - rule-based emergency red-flag check that runs BEFORE the AI
  - commands: /report /reset /help /quit
  - saves a triage report + full transcript to the "reports" folder
  - automatic retry on network problems
"""
import os
import sys
import time
import getpass
from datetime import datetime

import requests

# ---- PUT YOUR KEY HERE (inside the quotes), or leave empty to be asked ----
API_KEY = "AQ.Ab8RN6IX1YU8Lf3UAGoFGG_EWceRh5YxcK2p7kLJK7RjAc7m9g"
# ---------------------------------------------------------------------------

MODEL = "gemini-3.5-flash"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REPORT_DIR = "reports"
DISCLAIMER = "This is not a medical diagnosis. Please consult a doctor."

SYSTEM_TEMPLATE = """You are a careful health triage assistant, not a doctor.

Patient profile (may be empty):
{profile}

Rules:
1. Ask only 1-2 follow-up questions at a time (onset, duration, severity,
   location, associated symptoms, triggers, what makes it better or worse).
2. When you have enough information, reply with:
   (a) 2-4 possible causes, ranked by likelihood, with a short reason each,
   (b) an urgency level: EMERGENCY / URGENT (same day) / ROUTINE (few days) / SELF-CARE,
   (c) simple next steps and what to tell a doctor.
3. Take the profile into account (age, conditions, medicines, allergies).
4. Never claim a definite diagnosis. Never give prescription drug doses.
5. If anything sounds dangerous, tell the person to seek emergency care now.
6. Be warm, clear and brief. Use simple language.
7. End final answers with: "{disclaimer}"
"""

REPORT_PROMPT = """Write a concise triage report from our conversation using
exactly these headings, in plain text with no markdown symbols:

SUMMARY OF SYMPTOMS
POSSIBLE CAUSES (ranked, with reasons)
URGENCY LEVEL
RECOMMENDED NEXT STEPS
WHAT TO TELL A DOCTOR
WARNING SIGNS - SEEK EMERGENCY CARE IF

End with: "{disclaimer}"
""".format(disclaimer=DISCLAIMER)

# Safety layer: simple keyword rules that run BEFORE the AI model.
RED_FLAGS = [
    "chest pain", "chest tightness", "can't breathe", "cannot breathe",
    "difficulty breathing", "short of breath", "slurred speech",
    "face drooping", "sudden weakness", "unconscious", "fainted",
    "severe bleeding", "coughing blood", "vomiting blood", "seizure",
    "suicidal", "want to die", "kill myself", "overdose", "poisoning",
    "severe allergic", "swollen tongue", "worst headache",
]

EMERGENCY_MSG = (
    "\n[!] EMERGENCY WARNING: what you describe may be serious.\n"
    "    Call emergency services (112 in India) or go to the nearest\n"
    "    hospital NOW. Do not wait for this program.\n"
)

HELP_TEXT = """
Commands:
  /report  - create and save a triage report from this conversation
  /reset   - start over with a new conversation
  /help    - show this help
  /quit    - exit (also: quit, exit)
Just type your symptoms normally to chat.
"""


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(f"API error {status}: {message}")
        self.status = status


class Chat:
    """Keeps the conversation history and talks to the Gemini REST API."""

    def __init__(self, api_key, system_prompt):
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.history = []

    def send(self, message):
        contents = self.history + [{"role": "user", "parts": [{"text": message}]}]
        body = {
            "systemInstruction": {"parts": [{"text": self.system_prompt}]},
            "contents": contents,
        }
        resp = requests.post(
            URL.format(model=MODEL),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60,
        )
        if resp.status_code != 200:
            try:
                msg = resp.json()["error"]["message"]
            except Exception:
                msg = resp.text[:300]
            raise ApiError(resp.status_code, msg)

        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError):
            raise ApiError(0, "No answer returned (it may have been blocked). Try rephrasing.")

        self.history = contents + [{"role": "model", "parts": [{"text": text}]}]
        return text


def has_red_flag(text):
    text = text.lower()
    return any(flag in text for flag in RED_FLAGS)


def get_key():
    key = API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        key = getpass.getpass(
            "Paste your Gemini API key and press Enter (it stays hidden): "
        )
    return key.strip().strip('"').strip("'")


def ask_profile():
    print("Optional quick profile. Press Enter to skip any question.")
    fields = [
        ("age", "Age"),
        ("sex", "Sex"),
        ("existing conditions", "Existing conditions"),
        ("medicines", "Medicines you take"),
        ("allergies", "Allergies"),
    ]
    profile = {}
    for key, label in fields:
        value = input(f"  {label}: ").strip()
        if value:
            profile[key] = value
    return profile


def profile_text(profile):
    if not profile:
        return "No profile provided."
    return "\n".join(f"- {k}: {v}" for k, v in profile.items())


def new_chat(api_key, profile):
    system = SYSTEM_TEMPLATE.format(
        profile=profile_text(profile), disclaimer=DISCLAIMER
    )
    return Chat(api_key, system)


def send_with_retry(chat, message, tries=3):
    last_error = None
    for attempt in range(1, tries + 1):
        try:
            return chat.send(message)
        except ApiError as e:
            last_error = e
            # Retry only for rate limits / server problems, not bad key etc.
            if e.status not in (429, 500, 502, 503, 504):
                break
        except requests.RequestException as e:  # network problems
            last_error = e
        if attempt < tries:
            print(f"  (problem, retrying {attempt}/{tries - 1}...)")
            time.sleep(2 * attempt)
    raise RuntimeError(last_error)


def save_report(report_text, transcript, profile):
    os.makedirs(REPORT_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORT_DIR, f"triage_{stamp}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("AI HEALTH TRIAGE REPORT (demo)\n")
        f.write(f"Created: {datetime.now():%Y-%m-%d %H:%M}\n\n")
        f.write("PROFILE\n" + profile_text(profile) + "\n\n")
        f.write(report_text + "\n\n")
        f.write("-" * 60 + "\nFULL CONVERSATION\n" + "-" * 60 + "\n")
        for role, text in transcript:
            f.write(f"{role}: {text}\n\n")
    return path


def main():
    api_key = get_key()
    if not api_key:
        sys.exit("No API key entered.")

    print("\n=== AI Health Triage Agent (demo) ===")
    print(DISCLAIMER)
    print("In an emergency, call 112 (India) immediately.\n")

    profile = ask_profile()
    chat = new_chat(api_key, profile)
    transcript = []

    print(HELP_TEXT)

    while True:
        user_msg = input("You: ").strip()
        if not user_msg:
            continue

        cmd = user_msg.lower()
        if cmd in {"/quit", "quit", "exit"}:
            print("Take care. Goodbye!")
            break
        if cmd == "/help":
            print(HELP_TEXT)
            continue
        if cmd == "/reset":
            profile = ask_profile()
            chat = new_chat(api_key, profile)
            transcript = []
            print("Started a new conversation.\n")
            continue
        if cmd == "/report":
            if not transcript:
                print("Nothing to report yet. Describe your symptoms first.\n")
                continue
            try:
                report = send_with_retry(chat, REPORT_PROMPT)
            except Exception as e:
                print(f"Error: {e}\n")
                continue
            path = save_report(report, transcript, profile)
            print(f"\n{report}\n")
            print(f"Report saved to: {path}\n")
            continue

        transcript.append(("You", user_msg))

        if has_red_flag(user_msg):
            print(EMERGENCY_MSG)
            transcript.append(("System", "Emergency warning shown to user."))
            continue

        try:
            reply = send_with_retry(chat, user_msg)
        except Exception as e:
            print(f"Error: {e}\n")
            transcript.pop()
            continue

        transcript.append(("Agent", reply))
        print(f"\nAgent: {reply}\n")


if __name__ == "__main__":
    main()
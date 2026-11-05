# AI Health Triage Agent

A conversational AI agent that collects a person's symptoms, suggests possible causes, rates the urgency, and recommends next steps. It runs in the terminal or in a browser-based chat interface and uses the Google Gemini API.

> **Disclaimer:** This is an educational project. It is a triage and decision-support demo, **not** a medical diagnosis tool, and it does not replace a doctor. In an emergency, call your local emergency number (112 in India).

## Features

- Conversational symptom intake: asks 1-2 follow-up questions at a time
- Optional profile (age, sex, existing conditions, medicines, allergies) used to personalise guidance
- Ranked list of possible causes with short reasons
- Urgency level: Emergency / Urgent / Routine / Self-care
- **Rule-based emergency check** that runs before the AI model and shows an immediate warning for red-flag symptoms (for example chest pain or difficulty breathing)
- Browser chat interface with urgency badges, example prompts, and light/dark themes
- Saves a structured triage report and full conversation to a local `reports/` folder
- Automatic retry on network or rate-limit errors

## How it works

1. The user's message is checked against a list of emergency red flags.
2. If none match, the message and the conversation history are sent to Gemini with a system prompt that defines the agent's role, question style, and safety rules.
3. The reply is shown in the interface, with an urgency badge when one is detected.
4. `/report` (terminal) or the **Generate triage report** button (web) asks the model for a structured summary and saves it.

## Project structure

```
health_agent.py   Agent logic and terminal chat (run this for the terminal version)
app.py            Web interface (run this for the browser version)
requirements.txt  Python dependencies
.gitignore        Keeps keys, reports and local files out of the repo
```

## Setup

1. Install Python 3.9 or newer.
2. Install the dependency:
   ```
   pip install -r requirements.txt
   ```
3. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
4. Provide the key in one of these ways (never commit it):
   - Set the `GEMINI_API_KEY` environment variable, or
   - Leave `API_KEY` empty in `health_agent.py` and paste the key when the program asks.

## Run

Terminal version:

```
python health_agent.py
```

Commands: `/report`, `/reset`, `/help`, `/quit`.

Web interface:

```
python app.py
```

Then open http://127.0.0.1:8000 (it opens automatically). Press `Ctrl + C` in the terminal to stop.

## Limitations

- The emergency check is keyword based and can miss unusual wording.
- The AI model can make mistakes or sound more certain than it should.
- It cannot examine a patient or run tests, and it has not been clinically validated.

## Future work

- Multi-agent design (intake, reasoning, and safety-review agents)
- Retrieval from trusted guidelines (WHO, MedlinePlus) with citations
- Automated test cases with expected urgency levels
- Drug-interaction and allergy checks
- Multi-language support, including Hindi

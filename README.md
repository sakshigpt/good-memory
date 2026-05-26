# Good Memory

> A personal "people memory" agent. Log a quick note after talking to someone, and Good Memory automatically remembers the details that matter — so you can get a warm briefing before your next catch-up, or just ask *"What's the name of Priya's dog?"* and get an answer.

Built as a focused, end-to-end project: a Flask backend, a zero-build vanilla-JS frontend, a local SQLite store, the Claude API for understanding, and **offline** voice transcription.

---

## What it does

- **People** — add the people you care about, with a relationship and a bit of context.
- **Notes** — after a conversation, jot a quick note (typed) or **speak it** and have it transcribed.
- **Auto-extracted facts** — Claude reads each note and pulls out durable facts (employer, pets, birthdays, family, hobbies…) into a clean, structured profile.
- **Conflict resolution** — if a new note contradicts something already saved ("moved from Google → OpenAI"), it's flagged for you to resolve (keep old / use new / merge) instead of silently overwriting.
- **Pre-call briefings** — *"Brief me on Priya"* generates a warm, accurate summary with conversation starters.
- **Freeform Q&A** — ask natural questions across everyone you track; it answers only from what it actually knows (no hallucinating).

---

## Screenshots

> _Add a screenshot or a short demo GIF here, e.g. `docs/demo.gif`._

```
[ Home / people list ]   [ Person detail: Notes · Facts · Briefing · Ask ]
```

---

## Architecture

```
Browser (vanilla JS SPA)
   │   fetch() JSON  +  mic → 16kHz WAV
   ▼
Flask (routes/)  ──►  Services (services/)  ──►  SQLite (database.py)
                          │
                          ├─ extraction  → Claude Haiku   (note → structured facts)
                          ├─ briefing    → Claude Sonnet  (facts+notes → summary)
                          ├─ qa          → Claude Haiku   (question → answer)
                          ├─ conflict    → pure Python    (no API call)
                          └─ transcription → local Whisper (offline, no API)
```

The design rule throughout: **use the expensive smart model only where judgment is needed.** Conflict detection is deterministic string comparison (free, instant); only understanding language goes to Claude.

### Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Backend | **Flask** | Tiny, no ceremony; perfect for a personal-scale app. |
| Storage | **SQLite** | A single local file — zero setup, fully private. No DB server to run. |
| AI | **Claude** (Haiku + Sonnet) | Haiku for cheap/fast extraction & Q&A; Sonnet for higher-quality briefings. |
| Voice | **Local Whisper** | Runs on-device — free and private. No audio ever leaves the machine. |
| Frontend | **Vanilla JS/HTML/CSS** | No build step, no framework — fast to load, easy to read, nothing to maintain. |

**Model routing** is intentional and configurable in `.env`:
- `claude-haiku-4-5` — extraction & Q&A (high-frequency, cheap, simple)
- `claude-sonnet-4-6` — briefings (low-frequency, quality matters most)

---

## Two engineering problems worth highlighting

Both were caught *during* a build-a-little / test-a-little loop, not after.

### 1. Reliable conflict detection despite a non-deterministic LLM

Conflict detection matches facts on a `key` (e.g. `employer_name`). The problem: when extracting a *new* note, Claude would invent fresh keys — filing the first job under `employer_name` but a later one under `current_employer`. Different keys → the conflict was never seen.

**Fix:** before extracting a new note, the prompt is seeded with the person's **existing fact keys** and instructed to reuse them for the same kind of fact. This anchors the model's output to a stable vocabulary, so contradictions reliably collide on the same key — while keeping detection itself as cheap, deterministic Python.

### 2. Offline voice transcription with no `ffmpeg`

Whisper normally shells out to `ffmpeg` to decode audio — but the target machine had no `ffmpeg` and no easy way to install it.

**Fix:** sidestep `ffmpeg` entirely. The **browser** decodes the recording via the Web Audio API and re-encodes it as a 16 kHz mono PCM WAV; the **server** reads that WAV with Python's stdlib `wave` module into a NumPy array and hands it straight to Whisper. Result: voice works fully offline with **zero extra system dependencies.**

---

## Getting started

**Requirements:** Python 3.9+, an [Anthropic API key](https://console.anthropic.com).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
#   then edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# 3. Run
python app.py
#   → open http://localhost:5050
```

> **Tip:** the app uses port **5050** because macOS reserves 5000 for AirPlay. Change `PORT` in `.env` if you like.

**Voice notes:** the first recording downloads the Whisper model (~150 MB) and warms up (~20–30 s); after that it's fast. Mic access requires `localhost` (browser security) — which is how the app runs by default.

---

## Project structure

```
good-memory/
├── app.py              # Flask entry point + static serving
├── config.py           # Loads .env (key, model names, port)
├── database.py         # SQLite schema + all DB helpers (no ORM)
├── routes/             # HTTP endpoints (people, notes, facts, conflicts, ai, voice)
├── services/           # extraction · briefing · qa · conflict · transcription
├── static/             # index.html · style.css · app.js  (the SPA)
└── data/               # SQLite DB lives here (gitignored)
```

---

## Cost

Only **Claude** calls cost money; voice transcription is local and free. Three actions use the API: saving a note (extraction), asking a question, and generating a briefing. For personal use this is on the order of **pennies per month**. Set a spend cap in the Anthropic Console to be safe.

---

## Limitations & possible next steps

This is intentionally scoped as a private, single-user, local tool. To run it as a hosted service you'd want:

- **Authentication** — there's no login; anyone with the URL could read notes and spend the API budget.
- **Hosted Whisper** — swap local Whisper for a hosted API (e.g. Groq, already supported via `WHISPER_BACKEND=groq`) so the server doesn't ship the heavy `torch` dependency.
- **Proactive nudges** — "you haven't logged a note for X in a while."

---

## Notes for reviewers

- No secrets are committed — `.env` and the database are gitignored; `.env.example` documents required config.
- Conflict detection is deliberately *not* an LLM call: it's deterministic, free, and instant.
- The frontend has no build step on purpose — clone and run, nothing to compile.

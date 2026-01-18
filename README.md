# Dialectic

A shared thinking space where two humans and an LLM co-reason together.

## Quick Start

### 1. Install dependencies

```bash
cd dialectic
pip install -r requirements.txt
```

### 2. Set up PostgreSQL

```bash
# Create database
createdb dialectic

# Apply schema
psql dialectic < schema.sql
```

### 3. Set environment variables

```bash
export DATABASE_URL="postgresql://localhost/dialectic"
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."  # Optional, for fallback
```

### 4. Run the server

```bash
python run.py
```

### 5. Open the UI

Open `frontend/index.html` in your browser.

Or serve it:
```bash
python -m http.server 3000 --directory frontend
```

Then visit http://localhost:3000

## What it does

- **Two humans + one LLM** talk in real-time
- **The LLM is a participant**, not an assistant — it challenges, synthesizes, and provokes
- **Everything persists** — conversations, memories, forks
- **Fork any moment** into a new branch to explore alternatives
- **Shared memory** — both users can add/edit what the LLM remembers

## Architecture

```
dialectic/
├── api/main.py         # FastAPI server
├── llm/                # LLM orchestration
│   ├── providers.py    # Anthropic + OpenAI
│   ├── router.py       # Retry + fallback
│   ├── heuristics.py   # When should LLM speak?
│   └── orchestrator.py # Coordination
├── memory/             # Vector search + versioning
├── transport/          # WebSocket handlers
├── models.py           # Data models
├── operations.py       # Fork, ancestry queries
└── frontend/           # Single-page UI
```

## API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/rooms` | POST | Create room |
| `/users` | POST | Create user |
| `/rooms/{id}/join` | POST | Join room |
| `/rooms/{id}/threads` | GET | List threads |
| `/threads/{id}/messages` | GET | Get messages |
| `/rooms/{id}/memories` | GET/POST | Manage memories |
| `/ws/{room_id}` | WS | Real-time connection |

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `OPENAI_API_KEY` | No | GPT fallback |

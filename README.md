# Liwec — Light-way Education Consultancy

A simple, self-contained video-consultation app: one Flask process serves the
pages **and** handles real-time signaling (no separate backend/frontend
services). Actual video/audio streams directly between participants' browsers
(WebRTC) — the server never sees or stores video.

**Layout:** whoever hosts a meeting is shown large in the "spotlight" at the
top; everyone else appears in a scrollable strip of small tiles underneath.

## Quick start (local testing — SQLite, zero setup)

By default this app uses **SQLite** — a single file on disk, no database
server to install or configure. This is the easiest way to try it out and
keep building on it locally.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

That's it — no `.env` file, no database setup needed. Visit
**http://localhost:5000**, register an account, click **New meeting**, and
share the room code shown on your dashboard with whoever you're consulting
with (open a second browser / incognito window and register a second account
to test two people in the same room).

Your data lives in `instance/consultmeet.db`. Delete that file any time to
start fresh.

## Switching to MySQL later (for real hosting)

When you're ready to host this somewhere, switch the database backend to
MySQL — nothing else in the app changes:

1. Copy `.env.example` to `.env`
2. Set `DB_ENGINE=mysql` and fill in your MySQL connection details
3. Create the database: `CREATE DATABASE consultmeet CHARACTER SET utf8mb4;`
   (or run `schema.sql`)
4. Create the tables: `flask --app app init-db`
5. `pip install PyMySQL` if you removed it (it's in requirements.txt already)
6. `python app.py`

**Windows users:** `run_setup.bat` automates installing MySQL itself (via
Chocolatey), creating the database, and configuring `.env` for you — useful
once you're past local testing and want MySQL running. It sets `DB_ENGINE=mysql`
automatically.

## What's included

- **Auth** — register/login/logout, passwords hashed with Werkzeug.
- **Meetings** — create a meeting (get a unique room code), join by code.
- **Video room** — spotlight layout (host large, others in a filmstrip),
  mic/camera toggles, leave button.
- **Consultation notes** — a slide-out panel per meeting, saved to the
  database, so notes taken during a session persist and can be reviewed later.
- **Recording & playback** — the host's browser records the live layout
  (spotlight + participant grid, with everyone's audio mixed in) and uploads
  it in ~30s chunks as the meeting happens. Once the host clicks **End
  meeting**, the meeting is locked — anyone who enters that same room code
  afterward is shown the recording instead of a live room, playing from the
  beginning. Only the host and people who actually attended can watch it back.
- **Database** — `users`, `meetings`, `meeting_participants`,
  `consultation_notes` tables (see `models.py` / `schema.sql`). Works on
  SQLite or MySQL without any code changes — just the `DB_ENGINE` setting.

## Where to go from here

Some natural next steps once this base is working for you:
- Screen sharing (adding a second `getDisplayMedia` track to the peer connections)
- A waiting room / host-approval step before participants can join
- Explicit recording consent capture (currently everyone just sees a notice banner)
- Meeting scheduling with reminder emails
- TURN server config for participants behind restrictive firewalls (STUN alone
  isn't always enough outside a dev/demo setting)

Let me know which of these you want next and we'll build on this base.

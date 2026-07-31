-- Postgres schema for ConsultMeet (Supabase-compatible).
--
-- You normally DON'T need to run this by hand: `flask --app app init-db`
-- creates these same tables automatically from models.py, against whatever
-- DB_ENGINE/DATABASE_URL you have configured. This file is provided as a
-- reference / for running manually in the Supabase SQL editor if you'd
-- rather not use the Flask CLI.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meetings (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    room_code VARCHAR(16) NOT NULL UNIQUE,
    host_id INTEGER NOT NULL REFERENCES users(id),
    scheduled_time TIMESTAMP NULL,
    status VARCHAR(20) DEFAULT 'scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meeting_participants (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS consultation_notes (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    author_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recordings (
    id SERIAL PRIMARY KEY,
    meeting_id INTEGER NOT NULL UNIQUE REFERENCES meetings(id),
    filename VARCHAR(255) NOT NULL,
    finalized BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_meetings_room_code ON meetings (room_code);

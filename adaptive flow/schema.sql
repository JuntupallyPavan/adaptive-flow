-- AdaptiveFlow: SQLite schema (beginner-friendly, hackathon scope)
-- Tables:
-- - users: login/signup credentials (hashed passwords)
-- - habits: base habit goal per user
-- - entries: daily energy + scaled goal + completion + score contribution

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS habits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  base_goal INTEGER NOT NULL,
  unit TEXT NOT NULL DEFAULT 'units',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  habit_id INTEGER NOT NULL,
  entry_date TEXT NOT NULL,           -- ISO date: YYYY-MM-DD
  energy TEXT NOT NULL,               -- High | Medium | Low | Burnout
  scaled_goal INTEGER NOT NULL,        -- base_goal * multiplier (min 1)
  completed INTEGER NOT NULL,          -- user's actual completed amount
  score_delta REAL NOT NULL,           -- completed / scaled_goal
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(user_id, habit_id, entry_date),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
);

-- Helpful indexes for demo-speed queries
CREATE INDEX IF NOT EXISTS idx_habits_user_active ON habits(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_entries_user_date ON entries(user_id, entry_date);

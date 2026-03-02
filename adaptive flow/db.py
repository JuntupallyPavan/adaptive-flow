import os
import sqlite3
from flask import g


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "adaptiveflow.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def get_db() -> sqlite3.Connection:
    """
    Returns a per-request SQLite connection (stored in Flask's `g`).
    """
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db = conn
    return g.db


def close_db(e=None) -> None:
    """
    Closes the per-request connection if it exists.
    """
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(app) -> None:
    """
    Creates tables if they don't exist yet.
    Kept inline so beginners don't need extra tooling.
    """
    with app.app_context():
        db = get_db()
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        db.executescript(schema_sql)
        db.commit()

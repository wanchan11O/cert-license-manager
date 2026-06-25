import sqlite3
from contextlib import contextmanager


def init_db(path: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS certificates (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                domain     TEXT    NOT NULL,
                issuer     TEXT    NOT NULL,
                expires_at TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS licenses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                product_name TEXT    NOT NULL,
                license_key  TEXT    NOT NULL,
                expires_at   TEXT    NOT NULL,
                created_at   TEXT    DEFAULT (datetime('now'))
            );
        """)


@contextmanager
def get_db(path: str):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

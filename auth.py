"""Accounts and sessions. Passwords stay hashed; the token is the login."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3

ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS)
    return secrets.compare_digest(digest.hex(), digest_hex)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def ensure_accounts(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        );
        """
    )

    def add(table: str, column: str, definition: str) -> None:
        names = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    add("domains", "user_id", "INTEGER")
    add("tombstones", "user_id", "INTEGER")
    _rebuild_domains(conn)


def _rebuild_domains(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'domains'"
    ).fetchone()
    if not row or "name TEXT NOT NULL UNIQUE" not in row["sql"]:
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        """
        CREATE TABLE domains_new (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            uid TEXT,
            user_id INTEGER,
            UNIQUE (user_id, name)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO domains_new (id, name, created_at, uid, user_id)
        SELECT id, name, created_at, uid, user_id FROM domains
        """
    )
    conn.execute("DROP TABLE domains")
    conn.execute("ALTER TABLE domains_new RENAME TO domains")
    conn.execute("PRAGMA foreign_keys = ON")


def claim_unowned(conn: sqlite3.Connection, user_id: int) -> None:
    others = conn.execute("SELECT COUNT(*) AS n FROM users WHERE id != ?", (user_id,)).fetchone()["n"]
    if others:
        return
    conn.execute("UPDATE domains SET user_id = ? WHERE user_id IS NULL", (user_id,))
    conn.execute("UPDATE tombstones SET user_id = ? WHERE user_id IS NULL", (user_id,))

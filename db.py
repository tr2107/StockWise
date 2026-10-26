"""
db.py - connecting to the SQLite database.

Flask calls get_db() whenever a page needs the database. The same connection
is reused for the whole request and closed automatically afterwards.
"""
import os
import sqlite3

from flask import current_app, g

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def connect(path):
    """Open a connection with the settings StockWise needs."""
    # isolation_level=None lets us write BEGIN / COMMIT ourselves, so it is
    # obvious in the code exactly where a database transaction starts and ends.
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row  # rows behave like dictionaries: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless this is on
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(path):
    """Create the tables if they do not exist yet. Existing data is never touched."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = connect(path)
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.close()

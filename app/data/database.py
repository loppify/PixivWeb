import os
import sqlite3

from flask import g

DB_NAME = "pixiv_media.db"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_NAME)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    if not os.path.exists(DB_NAME):
        open(DB_NAME, 'a').close()

    db = get_db()

    db.execute('''
        CREATE TABLE IF NOT EXISTS media (
            filename TEXT PRIMARY KEY,
            is_favorite BOOLEAN DEFAULT 0,
            is_viewed BOOLEAN DEFAULT 0,
            width INTEGER DEFAULT 0,
            height INTEGER DEFAULT 0,
            mtime REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    try:
        db.execute("ALTER TABLE media ADD COLUMN width INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        db.execute("ALTER TABLE media ADD COLUMN height INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        db.execute("ALTER TABLE media ADD COLUMN mtime REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        db.execute("CREATE INDEX IF NOT EXISTS idx_mtime ON media (mtime DESC)")
    except sqlite3.OperationalError:
        pass

    db.commit()
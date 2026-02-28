import sqlite3
import os

DB_PATH = "users.db"

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS dm_users
                 (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS studefi_queue
                 (user_id INTEGER, residence TEXT, email TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    try:
        c.execute('''ALTER TABLE studefi_queue ADD COLUMN priority INTEGER DEFAULT 1''')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def add_to_queue(user_id, residence, email, priority=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO studefi_queue (user_id, residence, email, priority) VALUES (?, ?, ?, ?)", (user_id, residence, email, priority))
    conn.commit()
    conn.close()

def remove_from_queue(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM studefi_queue WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_queue():
    """Returns list of tuples (user_id, residence, email, timestamp, priority) ordered by priority DESC, timestamp ASC"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, residence, email, timestamp, priority FROM studefi_queue ORDER BY priority DESC, timestamp ASC")
    queue = c.fetchall()
    conn.close()
    return queue

def is_in_queue(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM studefi_queue WHERE user_id = ?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def add_dm_user(user_id):
    """Add a user to DM notifications"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO dm_users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_dm_user(user_id):
    """Remove a user from DM notifications"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM dm_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_dm_users():
    """Get all users who want DM notifications"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM dm_users")
    users = {row[0] for row in c.fetchall()}
    conn.close()
    return users

def is_dm_user(user_id):
    """Check if a user has DM notifications enabled"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM dm_users WHERE user_id = ?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

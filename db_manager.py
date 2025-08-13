import sqlite3
import os

DB_PATH = "users.db"

def init_db():
    """Initialize the database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS dm_users
                 (user_id INTEGER PRIMARY KEY)''')
    conn.commit()
    conn.close()

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

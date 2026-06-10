import sqlite3
import hashlib
import time
from datetime import datetime

def get_db_connection(db_path="bookmarks.db"):
    """
    Establish a connection to the SQLite database.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path="bookmarks.db"):
    """
    Initialize the database and create tables if they do not exist.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 1. Bookmarks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL,
        title TEXT,
        folder TEXT,
        category TEXT DEFAULT '📦 其他',
        add_date TEXT,
        hash TEXT,
        status_code INTEGER DEFAULT NULL,
        is_valid INTEGER DEFAULT -1,  -- -1: Untested, 0: Invalid, 1: Valid
        last_checked TEXT DEFAULT NULL
    )
    """)
    
    # 2. Folders tree table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parent_id INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0
    )
    """)
    
    # 3. Import History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        import_time TEXT NOT NULL,
        bookmark_count INTEGER DEFAULT 0
    )
    """)
    
    # 4. Bookmarks Version Snapshot table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookmarks_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL,
        bookmark_id INTEGER,
        url TEXT NOT NULL,
        title TEXT,
        folder TEXT,
        category TEXT,
        add_date TEXT,
        hash TEXT,
        status_code INTEGER,
        is_valid INTEGER,
        last_checked TEXT
    )
    """)
    
    # 5. Operation History log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS operation_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()

def save_version_snapshot(conn, action_type):
    """
    Save a snapshot of the current bookmarks table.
    - If no history exists, the first version is 0 (Initial Bookmarks).
    - Otherwise, the version increments by 1.
    """
    cursor = conn.cursor()
    
    # Get the latest version from operation history
    cursor.execute("SELECT MAX(version) as max_ver FROM operation_history")
    row = cursor.fetchone()
    if row and row['max_ver'] is not None:
        new_version = row['max_ver'] + 1
    else:
        new_version = 0  # Initial state
        
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save the action to history log
    cursor.execute(
        "INSERT INTO operation_history (version, action_type, timestamp) VALUES (?, ?, ?)",
        (new_version, action_type, current_time)
    )
    
    # Copy current bookmarks to version snapshots table
    cursor.execute("SELECT id, url, title, folder, category, add_date, hash, status_code, is_valid, last_checked FROM bookmarks")
    rows = cursor.fetchall()
    
    for r in rows:
        cursor.execute(
            """
            INSERT INTO bookmarks_version 
            (version, bookmark_id, url, title, folder, category, add_date, hash, status_code, is_valid, last_checked) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_version, r['id'], r['url'], r['title'], r['folder'], r['category'], r['add_date'], 
             r['hash'], r['status_code'], r['is_valid'], r['last_checked'])
        )
        
    conn.commit()
    return new_version

def rollback_to_version(conn, target_version):
    """
    Rollback the bookmarks table to target_version.
    Cleans up all versions > target_version.
    """
    cursor = conn.cursor()
    
    # Check if target version exists
    cursor.execute("SELECT COUNT(*) as cnt FROM bookmarks_version WHERE version = ?", (target_version,))
    if cursor.fetchone()['cnt'] == 0:
        return False
        
    # Clear active bookmarks
    cursor.execute("DELETE FROM bookmarks")
    
    # Copy back from snapshot
    cursor.execute(
        """
        SELECT bookmark_id, url, title, folder, category, add_date, hash, status_code, is_valid, last_checked 
        FROM bookmarks_version 
        WHERE version = ?
        """,
        (target_version,)
    )
    rows = cursor.fetchall()
    
    for r in rows:
        cursor.execute(
            """
            INSERT INTO bookmarks (id, url, title, folder, category, add_date, hash, status_code, is_valid, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (r['bookmark_id'], r['url'], r['title'], r['folder'], r['category'], r['add_date'], 
             r['hash'], r['status_code'], r['is_valid'], r['last_checked'])
        )
        
    # Clean up versions and operation history after target_version
    cursor.execute("DELETE FROM bookmarks_version WHERE version > ?", (target_version,))
    cursor.execute("DELETE FROM operation_history WHERE version > ?", (target_version,))
    
    conn.commit()
    return True

def get_latest_version(conn):
    """
    Get the current latest version number and its description.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT version, action_type, timestamp FROM operation_history ORDER BY version DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row['version'], row['action_type'], row['timestamp']
    return -1, None, None

def get_all_operations(conn):
    """
    Return lists of operation history.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT version, action_type, timestamp FROM operation_history ORDER BY version ASC")
    return cursor.fetchall()

def clear_all_bookmarks(conn):
    """
    Clear active database records and all version history.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookmarks")
    cursor.execute("DELETE FROM folders")
    cursor.execute("DELETE FROM bookmarks_version")
    cursor.execute("DELETE FROM operation_history")
    conn.commit()

import sqlite3
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import database

def get_all_urls(conn):
    """
    Get all URLs currently in the bookmarks table.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM bookmarks")
    return [r['url'] for r in cursor.fetchall()]

def check_integrity(original_urls):
    """
    Integrity check decorator/helper.
    Ensures no unique URLs are lost after an operation (like deduplication or sorting).
    """
    def decorator(func):
        def wrapper(conn, *args, **kwargs):
            # 1. Get unique original URLs
            orig_set = set(original_urls)
            
            # 2. Run the operation
            res = func(conn, *args, **kwargs)
            
            # 3. Get new unique URLs
            new_urls = get_all_urls(conn)
            new_set = set(new_urls)
            
            # 4. Verify no unique URL is lost
            missing = orig_set - new_set
            if missing:
                raise ValueError(f"Integrity check failed: {len(missing)} unique URL(s) were lost during the operation!")
            return res
        return wrapper
    return decorator

def deduplicate_bookmarks(db_path, keep_strategy="oldest"):
    """
    Deduplicates bookmarks in the database based on URL hash.
    keep_strategy: 'oldest' (keep the one with smaller id) or 'latest' (keep the one with larger id).
    """
    conn = database.get_db_connection(db_path)
    try:
        # Get list of unique URLs before operation
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM bookmarks")
        original_urls = [r['url'] for r in cursor.fetchall()]
        
        # Save snapshot
        database.save_version_snapshot(conn, "去重书签")
        
        # Identify duplicates
        cursor.execute("SELECT hash, COUNT(*) as cnt FROM bookmarks GROUP BY hash HAVING cnt > 1")
        dup_hashes = [r['hash'] for r in cursor.fetchall()]
        
        total_deleted = 0
        for h in dup_hashes:
            if keep_strategy == "oldest":
                # Keep the minimum ID, delete others
                cursor.execute("SELECT MIN(id) as keep_id FROM bookmarks WHERE hash = ?", (h,))
                keep_id = cursor.fetchone()['keep_id']
                cursor.execute("DELETE FROM bookmarks WHERE hash = ? AND id != ?", (h, keep_id))
            else:
                # Keep the maximum ID, delete others
                cursor.execute("SELECT MAX(id) as keep_id FROM bookmarks WHERE hash = ?", (h,))
                keep_id = cursor.fetchone()['keep_id']
                cursor.execute("DELETE FROM bookmarks WHERE hash = ? AND id != ?", (h, keep_id))
            total_deleted += cursor.rowcount
            
        conn.commit()
        
        # Verify integrity
        cursor.execute("SELECT url FROM bookmarks")
        new_urls = [r['url'] for r in cursor.fetchall()]
        missing = set(original_urls) - set(new_urls)
        if missing:
            conn.rollback()
            raise ValueError(f"去重后校验失败：有 {len(missing)} 个唯一网址丢失，已自动撤滚！")
            
        return total_deleted
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_invalid_bookmarks(db_path):
    """
    Deletes bookmarks marked as invalid (is_valid = 0) from the database.
    """
    conn = database.get_db_connection(db_path)
    try:
        # Save snapshot
        database.save_version_snapshot(conn, "删除失效书签")
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookmarks WHERE is_valid = 0")
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def check_single_url(bm_id, url):
    """
    Checks if a single URL is valid.
    Returns: (id, status_code, is_valid)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Secure validation of inputs
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return bm_id, -2, 0  # Invalid protocol
        
    try:
        # Try HEAD request first for speed
        response = requests.head(url, headers=headers, timeout=3.0, allow_redirects=True, verify=False)
        status = response.status_code
        
        # If server rejects HEAD (e.g. 405 Method Not Allowed), try GET stream=True
        if status in [404, 405]:
            response = requests.get(url, headers=headers, timeout=3.0, allow_redirects=True, verify=False, stream=True)
            status = response.status_code
            
        is_valid = 1 if status < 400 else 0
        return bm_id, status, is_valid
    except requests.exceptions.Timeout:
        return bm_id, -1, 0  # Timeout
    except Exception:
        return bm_id, -9, 0  # Connection failed / SSL error / DNS error

def check_all_bookmarks_validity(db_path, progress_callback=None, check_cancelled=None):
    """
    Checks validity of all bookmarks concurrently using a thread pool.
    - progress_callback: a function receiving (current, total)
    - check_cancelled: a function returning True if execution should stop
    """
    # Disable warnings for verify=False requests
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    
    conn = database.get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url FROM bookmarks")
    rows = cursor.fetchall()
    conn.close()
    
    total = len(rows)
    if total == 0:
        return 0
        
    completed = 0
    valid_count = 0
    invalid_count = 0
    
    # To write updates back, we will do it in chunks or open/close connection inside loop
    # Opening connection on updates to avoid database lock issues during long threads.
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(check_single_url, r['id'], r['url']): r for r in rows}
        
        for future in as_completed(futures):
            if check_cancelled and check_cancelled():
                # Cancel remainder
                break
                
            try:
                bm_id, status_code, is_valid = future.result()
                
                # Update database
                conn_up = database.get_db_connection(db_path)
                cursor_up = conn_up.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor_up.execute(
                    "UPDATE bookmarks SET status_code = ?, is_valid = ?, last_checked = ? WHERE id = ?",
                    (status_code, is_valid, now_str, bm_id)
                )
                conn_up.commit()
                conn_up.close()
                
                if is_valid == 1:
                    valid_count += 1
                else:
                    invalid_count += 1
            except Exception:
                pass
                
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
                
    return completed

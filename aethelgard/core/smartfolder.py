import os
import sqlite3
from pathlib import Path

DEFAULT_SQLITE_DB = "./file_state.db"

class SmartFolder:
    """Acts like 'git status' by tracking file modification times in SQLite.
       Used a super-light variant of DMC
    """

    def __init__(self, db_path=DEFAULT_SQLITE_DB):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS file_state (
                filepath TEXT PRIMARY KEY,
                timestamp REAL,
                size INTEGER
            )
        ''')
        self.conn.commit()

    def get_changed_files(self, directory: Path):
        """Scans the directory and yields files that are new or modified."""
        cursor = self.conn.cursor()

        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith('.json'):
                    continue

                filepath = str(Path(root) / file)
                stat = os.stat(filepath)
                timestamp = stat.st_mtime
                size = stat.st_size

                cursor.execute("SELECT timestamp, size FROM file_state WHERE filepath = ?", (filepath,))
                row = cursor.fetchone()

                # If file is not in DB, or if timestamp/size has changed
                if row is None or row[0] != timestamp or row[1] != size:
                    yield filepath, timestamp, size

    def mark_processed(self, filepath: str, timestamp: float, size: int):
        """Updates the SQLite database after successful processing."""
        self.conn.execute('''
            INSERT OR REPLACE INTO file_state (filepath, timestamp, size)
            VALUES (?, ?, ?)
        ''', (filepath, timestamp, size))
        self.conn.commit()
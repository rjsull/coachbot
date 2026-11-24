import json
import os
import sqlite3
from pathlib import Path


class CoachStore:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        parent = self.path.parent
        if not parent.exists():
            parent.mkdir(parents=True)
            os.chmod(parent, 0o700)
        existed = self.path.exists()
        self.connection = sqlite3.connect(self.path)
        if not existed:
            os.chmod(self.path, 0o600)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                version INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS checkins (
                week_ending TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def save_plan(self, plan):
        cursor = self.connection.execute(
            "INSERT INTO plans(data) VALUES (?)",
            (json.dumps(plan, sort_keys=True),),
        )
        self.connection.commit()
        return cursor.lastrowid

    def add_checkin(self, checkin):
        try:
            self.connection.execute(
                "INSERT INTO checkins(week_ending, data) VALUES (?, ?)",
                (checkin["week_ending"], json.dumps(checkin, sort_keys=True)),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            raise ValueError(
                f"A check-in for {checkin['week_ending']} already exists; it was not overwritten."
            ) from error

    def history(self):
        rows = self.connection.execute(
            "SELECT data FROM checkins ORDER BY week_ending"
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def active_plan(self):
        row = self.connection.execute(
            "SELECT version, data FROM plans ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return {"version": row[0], "data": json.loads(row[1])}

    def close(self):
        self.connection.close()

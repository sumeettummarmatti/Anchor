import copy
import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional, Protocol

from ..models.analytics_event import AnalyticsEvent


class AnalyticsRepository(Protocol):
    def save(self, event: AnalyticsEvent) -> None: ...
    def get(self, event_id: str) -> Optional[AnalyticsEvent]: ...
    def list_for_user(self, user_id: str) -> list[AnalyticsEvent]: ...


class InMemoryAnalyticsRepository:
    """Small append-only repository used by default for local development."""

    def __init__(self):
        self.events: dict[str, AnalyticsEvent] = {}
        self.lock = threading.RLock()

    def save(self, event: AnalyticsEvent) -> None:
        with self.lock:
            if event.id in self.events:
                raise ValueError(f"Analytics event already exists: {event.id}")
            self.events[event.id] = copy.deepcopy(event)

    def get(self, event_id: str) -> Optional[AnalyticsEvent]:
        with self.lock:
            event = self.events.get(event_id)
            return copy.deepcopy(event) if event else None

    def list_for_user(self, user_id: str) -> list[AnalyticsEvent]:
        with self.lock:
            events = [event for event in self.events.values() if event.user_id == user_id]
            return copy.deepcopy(sorted(events, key=lambda item: item.timestamp))


class SQLiteAnalyticsRepository:
    """Synchronous sqlite3 adapter matching the project's repository style."""

    def __init__(self, path: str = "./analytics.sqlite3"):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    @staticmethod
    def _timestamp(value: str) -> datetime:
        timestamp = datetime.fromisoformat(value)
        return timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

    @staticmethod
    def _event(row) -> AnalyticsEvent:
        return AnalyticsEvent(
            id=row[0],
            user_id=row[1],
            event_type=row[2],
            source=row[3],
            timestamp=SQLiteAnalyticsRepository._timestamp(row[4]),
            metadata=json.loads(row[5]),
        )

    def save(self, event: AnalyticsEvent) -> None:
        with self.lock:
            try:
                self.connection.execute(
                    "INSERT INTO analytics_events (id, user_id, event_type, source, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                    (event.id, event.user_id, event.event_type, event.source, event.timestamp.isoformat(), json.dumps(event.metadata)),
                )
                self.connection.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Analytics event already exists: {event.id}") from exc

    def get(self, event_id: str) -> Optional[AnalyticsEvent]:
        with self.lock:
            row = self.connection.execute("SELECT id, user_id, event_type, source, timestamp, metadata FROM analytics_events WHERE id = ?", (event_id,)).fetchone()
        return self._event(row) if row else None

    def list_for_user(self, user_id: str) -> list[AnalyticsEvent]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT id, user_id, event_type, source, timestamp, metadata FROM analytics_events WHERE user_id = ? ORDER BY timestamp",
                (user_id,),
            ).fetchall()
        return [self._event(row) for row in rows]

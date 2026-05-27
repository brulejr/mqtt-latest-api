from collections import OrderedDict
from datetime import datetime, timezone
from threading import RLock
from typing import Any


class LatestMessageStore:
    def __init__(self, max_items: int = 1000):
        self._max_items = max_items
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = RLock()

    def upsert(
        self,
        key: str,
        topic: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        item = {
            "key": key,
            "topic": topic,
            "received_at": now,
            "payload": payload,
        }

        with self._lock:
            if key in self._items:
                del self._items[key]

            self._items[key] = item

            while len(self._items) > self._max_items:
                self._items.popitem(last=False)

        return item

    def list_items(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._items.values()))

    def get_item(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._items.get(key)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._items)

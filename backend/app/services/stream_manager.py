from collections import defaultdict
from queue import Empty, Queue
from threading import Lock
from typing import Any, Dict, List

_stream_lock = Lock()
_poll_streams = defaultdict(list)
_subscribers = defaultdict(dict)
_next_subscriber_id = defaultdict(int)
_request_rows = defaultdict(list)


def push_update(request_id, data):
    with _stream_lock:
        _poll_streams[request_id].append(data)

        if isinstance(data, dict) and data.get("type") == "company":
            _request_rows[request_id].append(dict(data))

        for queue in _subscribers[request_id].values():
            queue.put(data)


def clear_request_rows(request_id: int):
    with _stream_lock:
        _request_rows[request_id] = []


def get_request_rows(request_id: int, page: int = 1, limit: int = 50) -> Dict[str, Any]:
    safe_page = max(1, int(page or 1))
    safe_limit = max(1, int(limit or 50))
    offset = (safe_page - 1) * safe_limit

    with _stream_lock:
        rows: List[Dict[str, Any]] = _request_rows[request_id][:]

    return {
        "total": len(rows),
        "page": safe_page,
        "limit": safe_limit,
        "results": rows[offset : offset + safe_limit],
    }


def get_all_request_rows(request_id: int) -> List[Dict[str, Any]]:
    with _stream_lock:
        return _request_rows[request_id][:]


def get_updates(request_id):
    with _stream_lock:
        updates = _poll_streams[request_id][:]
        _poll_streams[request_id] = []
        return updates


def register_subscriber(request_id):
    with _stream_lock:
        subscriber_id = _next_subscriber_id[request_id]
        _next_subscriber_id[request_id] += 1

        queue = Queue()
        _subscribers[request_id][subscriber_id] = queue

        return subscriber_id


def pop_subscriber(request_id, subscriber_id, timeout=15):
    queue = _subscribers.get(request_id, {}).get(subscriber_id)
    if queue is None:
        return None

    try:
        return queue.get(timeout=timeout)
    except Empty:
        return None


def remove_subscriber(request_id, subscriber_id):
    with _stream_lock:
        request_subscribers = _subscribers.get(request_id)
        if not request_subscribers:
            return

        request_subscribers.pop(subscriber_id, None)

        if not request_subscribers:
            _subscribers.pop(request_id, None)

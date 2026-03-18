from collections import defaultdict
from queue import Empty, Queue
from threading import Lock

_stream_lock = Lock()
_poll_streams = defaultdict(list)
_subscribers = defaultdict(dict)
_next_subscriber_id = defaultdict(int)


def push_update(request_id, data):
    with _stream_lock:
        _poll_streams[request_id].append(data)

        for queue in _subscribers[request_id].values():
            queue.put(data)


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

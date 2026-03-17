from collections import defaultdict

streams = defaultdict(list)


def push_update(request_id, data):
    streams[request_id].append(data)


def get_updates(request_id):
    updates = streams[request_id][:]
    streams[request_id] = []
    return updates

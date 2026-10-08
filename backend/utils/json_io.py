import json
import os
import tempfile
import threading
import time

JSON_LOCK = threading.RLock()

def sharing_retry(action):
    # Windows can briefly deny reads/replaces while a file handle or scanner is closing.
    for attempt in range(5):
        try:return action()
        except PermissionError:
            if attempt==4:raise
            time.sleep(.02*(attempt+1))

def read_json(path):
    def read():
        try:
            with open(path,"r",encoding="utf-8") as f:return json.load(f)
        except FileNotFoundError:return None
    with JSON_LOCK:return sharing_retry(read)

def write_json_atomic(path, data):
    with JSON_LOCK:return _write_json_atomic(path,data)

def _write_json_atomic(path, data):
    directory = os.path.dirname(path)
    os.makedirs(
        directory,
        exist_ok=True
    )
    fd, temp_path = tempfile.mkstemp(
        dir=directory,
        suffix=".tmp"
    )
    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=4
            )
            f.flush()
            os.fsync(f.fileno())
        sharing_retry(lambda: os.replace(temp_path,path))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

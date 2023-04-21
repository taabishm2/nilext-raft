import os
import pickle
from threading import Lock
from collections import deque

from .config import globals
from .utils import *

RAFT_BASE_DIR = './logs/logcache'
RAFT_LOG_PATH = RAFT_BASE_DIR + '/durable_log'
RAFT_LOG_DB_PATH = RAFT_BASE_DIR + '/durable_log.db'


class DurLogEntry:
    def __init__(self, request_type, key, value=None):
        self.request_type = request_type  # Can be PUT (and later DELETE, etc.)
        self.key = key  # Key involved in the operation
        self.value = value  # Value (if any) associated with key


class DurLogManager:
    def __init__(self):
        self.lock = Lock()
        self.entries = deque()  # Queue of DurLogEntry objects
        self.load_entries()  # Load entries from stable store to memory.

    def load_entries(self):
        if not os.path.exists(RAFT_BASE_DIR):
            os.makedirs(RAFT_BASE_DIR)  # Create empty

        if not os.path.exists(RAFT_LOG_DB_PATH):
            self.flush_log_to_disk()  # Create empty log file

        with open(RAFT_LOG_PATH, "rb") as log_file:
            self.entries = pickle.load(log_file)

    def append(self, log_entry):
        with self.lock:
            log_me(f"Adding {log_entry.request_type} Entry to Durability Log")
            self.entries.append(log_entry)
            self.flush_log_to_disk()

    # Returns entry at head of queue without removing it from the queue
    def peek_head_entry(self):
        with self.lock:
            return self.entries[0]

    # Call this once request at head has been executed (after consensus, if relevant)
    def pop_head_entry(self):
        with self.lock:
            self.entries.popleft()
            self.flush_log_to_disk()

    def flush_log_to_disk(self):
        with open(RAFT_BASE_DIR, 'wb') as file:
            pickle.dump(self.entries, file)


dur_log_manager = DurLogManager()

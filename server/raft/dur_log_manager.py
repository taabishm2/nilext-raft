from time import time,sleep
import os
import pickle
import shelve
from threading import Lock
from threading import Thread
from collections import deque
import json

from .config import NodeRole, globals
# from .node import raft_node
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
        self.bloom = {}
        
        # self.log_exec_thread = Thread(target=self.init_log_exec)
        # self.log_exec_thread.start()

    def load_entries(self):
        if not os.path.exists(RAFT_BASE_DIR):
            os.makedirs(RAFT_BASE_DIR)  # Create empty

        if not os.path.exists(RAFT_LOG_DB_PATH):
            self.flush_log_to_disk()  # Create empty log file

        log_shelf = shelve.open(RAFT_LOG_PATH)
        num_entries = log_shelf["SHELF_SIZE"]
        log_me(f'{log_shelf.keys()} {log_shelf["SHELF_SIZE"]}')
        self.entries = [log_shelf[str(i)] for i in range(num_entries)]
        log_me(f'Loaded {num_entries} log entries from disk')
        log_shelf.close()

    def append(self, request_type, key, value):
        print("DurLogManager append: dur_log_mgr =\n")
        log_entry = DurLogEntry(request_type, key, value)
        with self.lock:
            self.bloom[key] = 1
            log_me(f"Adding {log_entry.request_type} Entry to Durability Log")
            self.entries.append(log_entry)
            self.flush_log_to_disk()

    # Returns entry at head of queue without removing it from the queue
    def peek_head_entry(self):
        if len(self.entries) == 0:
            return None
        with self.lock:
            return self.entries[0]

    # Call this once request at head has been executed (after consensus, if relevant)
    def pop_head_entry(self):
        with self.lock:
            if len(self.entries) != 0:
                self.entries.pop(0)
            self.flush_log_to_disk()

    def package_all_log(self):
        all_key = []
        all_value = []
        with self.lock:
            if len(self.entries) == 0:
                return None

            for entry in self.entries:
                all_key.append(entry.key)
                all_value.append(entry.value)

            return DurLogEntry("MULTI_PUT", json.dumps(all_key), json.dumps(all_value))

    def flush_log_to_disk(self):
        if len(self.entries) > 0:
            sleep(0.02)
            return None

        t1 = time()
        log_file = shelve.open(RAFT_LOG_PATH)
        log_me("opened shelf")
        if len(self.entries) == 0:
            log_file["SHELF_SIZE"] = 0
        else:
            log_file[str(log_file["SHELF_SIZE"])] = self.entries[-1]
            log_file["SHELF_SIZE"] += 1
        log_file.close()
        t2 = time()
        log_me(f"flush took {t2 - t1}")

    def is_key_in_durable_log(self, key):
        with self.lock:
            return key in self.bloom
    
    def clear_entry_from_durable_log(self, key, value):
        log_entry = DurLogEntry("PUT", key, value)
        if (log_entry in self.entries):
            self.entries.remove(log_entry)
            with self.lock:
                self.flush_log_to_disk()

    def clear_all_entries(self):
        with self.lock:
            self.entries.clear()
            self.flush_log_to_disk()
            self.bloom = {}

dur_log_manager = DurLogManager()

import time
import os
import pickle
import shelve
from threading import Lock
from threading import Thread
from collections import deque

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

        # with open(RAFT_LOG_PATH, "rb") as log_file:
        #     self.entries = pickle.load(log_file)

    def init_log_exec(self):
        #  Periodically execute entries from durability log.
        while True:
            if globals.state == NodeRole.Leader:
                log_me(f"I am the leader, clearing out durability logs periodically")
                # Start executing
                entry = dur_log_manager.peek_head_entry()
                if entry is not None:
                    is_consensus, error = raft_node.serve_put_request(entry.key, entry.value)
                    if is_consensus:
                        self.sync_kv_store_with_logs()
                        dur_log_manager.pop_head_entry()
                    else:
                        error = "No consensus was reached. Try again."
                        print(error)

            time.sleep(1.5)

    def append(self, request_type, key, value):
        print("DurLogManager append: dur_log_mgr =\n")
        log_entry = DurLogEntry(request_type, key, value)
        with self.lock:
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
            self.entries.pop(0)
            self.flush_log_to_disk()

    def flush_log_to_disk(self):
        log_file = shelve.open(RAFT_LOG_PATH)
        log_me("opened shelf")
        if len(self.entries) == 0:
            log_file["SHELF_SIZE"] = 0
        else:
            log_file[str(log_file["SHELF_SIZE"])] = self.entries[-1]
            log_file["SHELF_SIZE"] += 1
        log_file.close()

        # with open(RAFT_LOG_PATH, 'wb') as file:
        #     pickle.dump(self.entries, file)

    def is_key_in_durable_log(self, key):
        for entry in self.entries:
            if entry.key == key:
                return True
        return False
    
    def clear_entry_from_durable_log(self, key, value):
        log_entry = DurLogEntry("PUT", key, value)
        if (log_entry in self.entries):
            self.entries.remove(log_entry)
            with self.lock:
                self.flush_log_to_disk()

dur_log_manager = DurLogManager()

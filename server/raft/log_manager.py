import os
import pickle
import shelve
from threading import Lock

from .config import globals
from .utils import *

RAFT_BASE_DIR = './logs/logcache'
RAFT_LOG_PATH = RAFT_BASE_DIR + '/stable_log'
RAFT_LOG_DB_PATH = RAFT_BASE_DIR + '/stable_log.db'


class LogEntry:
    def __init__(self, term, cmd_key, cmd_val, is_multi_put=False):
        self.term = term
        self.cmd_key = cmd_key
        self.cmd_val = cmd_val
        self.is_multi_put = is_multi_put

    def __str__(self):
        return f"({self.term}-{self.cmd_key}:{self.cmd_val})"


class LogManager:
    def __init__(self):
        self.lock = Lock()
        self.entries = []
        self.load_entries()  # Load entries from stable store to memory.

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

    def append(self, log_entry):
        """
        append entry to the node's replicated log. This method is to be used by the leader
        to populate its own log. Returns last log index (length - 1) if successful.
        """
        with self.lock:
            print("Adding to entries")
            self.entries.append(log_entry)
            self.flush_log_to_disk()

            return len(self.entries) - 1

    def overwrite(self, start_index, log_entry_list, previous_term):
        """
        Overwrite entries of replicated log starting from (and including) `start_index` with `log_entry_list`
        Returns false if previous log index term doesn't match and true if overwrite successful
        """
        # log_me(f"OVERWRITE: {start_index}, {str(log_entry_list)}, {previous_term}")
        if start_index > len(self.entries) or \
                (start_index > 0 and (self.entries[start_index - 1].term != previous_term)):
            return False

        with self.lock:
            self.entries[start_index:] = log_entry_list
            self.flush_many_log_to_disk(start_index, log_entry_list)

        return True

    def is_this_log_older(self, current_term, other_log_term, other_log_len):
        """
        Used to decide whether to vote for a candidate
        """
        return current_term < other_log_term or (current_term == other_log_len and len(self.entries) < other_log_len)

    def get_log_at_index(self, index):
        """
        Get the earliest uncommitted log entry or None if it doesn't exist
        """
        if index >= len(self.entries):
            return None
        return self.entries[index]

    def get_earliest_uncommitted(self):
        """
        Get the earliest uncommitted log entry or None if it doesn't exist
        """
        if len(self.entries) == 0 or globals.commit_index + 1 >= len(self.entries):
            return None
        return self.entries[globals.commit_index + 1]

    def commit_log_entry(self):
        """
        Mark the earliest uncommitted log entry as committed (increment commit_index)
        """
        if self.get_earliest_uncommitted() is None:
            raise ValueError("No valid log entry present to commit")
        globals.commit_index += 1

    def get_earliest_unapplied(self):
        """
        Get the earliest unapplied log entry or None if it doesn't exist
        """
        if len(self.entries) == 0 or globals.last_applied + 1 >= len(self.entries):
            return None
        return self.entries[globals.last_applied + 1]

    def mark_log_applied(self):
        """
        Mark the earliest unapplied log entry as applied (increment last_applied)
        """
        if self.get_earliest_unapplied() is None:
            raise ValueError("No valid log entry present to apply")
        globals.last_applied += 1

    def flush_log_to_disk(self):
        log_me("starting shelf")
        log_file = shelve.open(RAFT_LOG_PATH)
        log_me("opened shelf")
        if len(self.entries) == 0:
            log_me("empty log")
            log_file["SHELF_SIZE"] = 0
        else:
            if (len(self.entries) % 100) != 0:
                return
            log_me("not empty log")
            log_me(f"entries {self.entries}")
            log_me(f"whole {log_file}")
            log_me(f"SHELF {log_file['SHELF_SIZE']}")
            log_file[str(log_file["SHELF_SIZE"])] = self.entries[-1]
            log_me(f"set {log_file['SHELF_SIZE']} to {self.entries[-1]}")
            log_file["SHELF_SIZE"] += 1

        log_me("closing")
        log_file.close()
        log_me("all done")

    def flush_many_log_to_disk(self, start_idx, val_list):
        log_file = shelve.open(RAFT_LOG_PATH)

        for i in range(start_idx, start_idx + len(val_list)):
            log_file[str(i)] = val_list[i - start_idx]

        log_file["SHELF_SIZE"] = start_idx + len(val_list)
        log_file.close()

    def get_last_index(self):
        return len(self.entries) - 1

    def get_latest_term(self):
        if not self.entries: return -1
        return self.entries[-1].term


log_manager = LogManager()

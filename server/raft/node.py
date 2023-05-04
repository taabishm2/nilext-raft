import time

from .transport import transport
from .log_manager import *
from .stats import stats
from .dur_log_manager import dur_log_manager

# from .election import *


class RaftNode:

    def serve_put_request(self, key, value, is_multi_cmd=False):
        """Returns tuple: (success (bool), error message) TODO: Redirect to leader node."""
        log_item = LogEntry(globals.current_term, key, value, is_multi_cmd)

        index = log_manager.append(log_item)
        log_me("Finished append")

        t1 = time.time()
        is_success_on_majority = transport.append_entry_to_peers(log_item, index)
        log_me("Adding commit latency stats")
        stats.add_commit_latency(transport.peer_ips, time.time() - t1, is_success_on_majority)

        if is_success_on_majority:
            log_me(f"Updating commit index for {key}")
            globals.set_commit_index(index)
            # Clear the entry pertaining to this request if present in my durability log
            dur_log_manager.clear_entry_from_durable_log(key, value)

        log_me(f"Finished PUT {key}:{value} request ")

        return is_success_on_majority, ""


# Create raft_node singleton
raft_node = RaftNode()

import time
from os import environ
from threading import Thread

from .config import NodeRole, globals
from .dur_log_manager import dur_log_manager
from .node import raft_node


class DurLogExecutor:

    def __init__(self):
        # Start a daemon thread to watch for callbacks from leader.
        self.log_exec_thread = Thread(target=self.init_log_exec)
        self.log_exec_thread.start()

        self.init_log_exec()

        # TODO: Need to add a function that triggers the FIRST election.
        # Initially all nodes will start as followers. Wait for one timeout and start election i guess?

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

dur_log_exec = DurLogExecutor()
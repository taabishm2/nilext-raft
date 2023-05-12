import threading
import time
from os import environ

from .raft import kv_server, transport
from .raft.election import Election
from .raft.dur_log_exec import DurLogExecutor


def main():
    raft_server_thread = threading.Thread(target=transport.main)
    raft_server_thread.start()

    kv_server_thread = threading.Thread(target=kv_server.main)
    kv_server_thread.start()

    election = Election()

    # dur_log_exec = DurLogExecutor()

    # TODO: remove this (test code)
    # print(f"*** WAITING 10 secs for servers, leader={environ['IS_LEADER']} ***")
    # time.sleep(5)
    # if environ['IS_LEADER'] == "TRUE": election.trigger_election()

    kv_server_thread.join()
    raft_server_thread.join()


if __name__ == '__main__':
    main()

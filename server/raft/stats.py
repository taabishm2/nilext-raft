import time
from threading import Lock
import csv
import shelve


class Stats:

    CAPTURE_STATS = False

    def __init__(self):
        self.lock = Lock()

        self.commit_latency = []  # (time, num_peers, latency): Latency in performing commits for PUT requests
        self.kv_request_list = []  # (time, request_name): List of KV RPC calls received (for throughput)
        self.raft_request_list = []  # (time, request_name): List of RAFT RPC received (for throughput)

    def add_commit_latency(self, num_peers, latency, was_success):
        if not self.CAPTURE_STATS: return
        with self.lock:
            self.commit_latency.append((time.time(), num_peers, latency, was_success))

    def add_kv_request(self, request_name):
        if not self.CAPTURE_STATS: return
        with self.lock:
            self.kv_request_list.append((time.time(), request_name))

    def add_raft_request(self, request_name):
        if not self.CAPTURE_STATS: return
        with self.lock:
            self.raft_request_list.append((time.time(), request_name))

    def flush(self):        
        s = shelve.open("/raft-kv-store/logs/logcache/server-rpc-stats")
        # print("KYYVVVS")
        # print(self.kv_request_list)
        s["COMMIT_LAT"] = self.commit_latency
        s["KV_REQS"] = self.kv_request_list
        s["RAFT_REQS"] = self.raft_request_list
        s.close()

stats = Stats()

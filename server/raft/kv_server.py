import sys
import threading
import time
import json
from concurrent import futures

import grpc

from .config import globals, NodeRole
from .log_manager import *
from .dur_log_manager import dur_log_manager
from .node import raft_node
from .utils import *
from .stats import stats

sys.path.append('../../')
import kvstore_pb2
import kvstore_pb2_grpc

from pymemcache.client import base


class KVStoreServicer(kvstore_pb2_grpc.KVStoreServicer):
    def __init__(self):
        super().__init__()
        self.kv_store_lock = threading.Lock()
        self.client = base.Client(('localhost', 11211))
        self.sync_kv_store_with_logs()

    def sync_kv_store_with_logs(self):
        log_me(f"Syncing kvstore, from {globals.lastApplied} to {globals.commitIndex+1}")
        for entry in log_manager.entries[globals.lastApplied:(globals.commitIndex+1)]:
            with self.kv_store_lock:
                if entry.is_multi_put:
                    keys, vals = json.loads(entry.cmd_key), json.loads(entry.cmd_val)
                    for k, _ in enumerate(keys):
                        log_me(f"setting {keys[k]} and  {vals[k]}")
                        self.client.set(keys[k], vals[k])
                else:
                    log_me(f"applying {entry.cmd_key} entry.cmd_val")
                    self.client.set(entry.cmd_key, entry.cmd_val)

                globals.set_last_applied(globals.commitIndex)

    def Put(self, request, context):
        log_me(f"Put {request.key} {request.value}")
        dur_log_manager.append("PUT", request.key, request.value)

        # Code for RAFT without Nil-Ext:
        # is_consensus, error = raft_node.serve_put_request(request.key, request.value)
        # if is_consensus: self.sync_kv_store_with_logs()
        # else: error = "No consensus was reached. Try again."

        return kvstore_pb2.PutResponse()

    # Not supported with Nil-ext at the moment
    def MultiPut(self, request, context):
        stats.add_kv_request("MULTI_PUT")
        log_me(f"Servicing MultiPut {request}")

        if not globals.state == NodeRole.Leader:
            log_me("Redirecting to leader: " + str(globals.leader_name))
            return kvstore_pb2.PutResponse(error="Redirect", is_redirect=True, redirect_server=globals.leader_name)

        key_vector, val_vector = [], []
        for kv in request.put_vector:
            key_vector.append(kv.key)
            val_vector.append(kv.value)

        is_consensus, error = raft_node.serve_put_request(json.dumps(key_vector), json.dumps(val_vector), is_multi_cmd=True)

        if is_consensus:
            # This can be done in a separate thread.
            self.sync_kv_store_with_logs()
        else:
            error = "No consensus was reached. Try again."

        log_me(f"Consensus {is_consensus}, error {error}")
        return kvstore_pb2.PutResponse(error=error)

    def Get(self, request, context):
        stats.add_kv_request("GET")
        log_me(f"Get {request.key}")

        if not globals.state == NodeRole.Leader:
            log_me("Redirecting to leader: " + str(globals.leader_name))
            return kvstore_pb2.GetResponse(key_exists=False, is_redirect=True, redirect_server=globals.leader_name)

        # Can be done in a separate thread.
        self.sync_kv_store_with_logs()
        if request.key == "FLUSH_CALL_STATS":
            stats.flush()

        with self.kv_store_lock:
            cached_val = self.client.get(request.key)
            return kvstore_pb2.GetResponse(key_exists=cached_val is not None,
                                           key=request.key, value=cached_val)

    def MultiGet(self, request, context):
        stats.add_kv_request(f"MULTI_GET {request}")

        log_me(f"Servicing Multi Get request {request}")

        if not globals.state == NodeRole.Leader:
            log_me("Redirecting to leader: " + str(globals.leader_name))
            return kvstore_pb2.MultiGetResponse(is_redirect=True, redirect_server=globals.leader_name)

        # Can be done in a separate thread.
        self.sync_kv_store_with_logs()
        with self.kv_store_lock:
            key_vector = request.get_vector
            resp = kvstore_pb2.MultiGetResponse()
            for query in key_vector:
                log_me(f"i am getting {query.key}")
                cached_val = self.client.get(query.key)
                resp.get_vector.append(kvstore_pb2.GetResult(key_exists=cached_val is not None,
                                           key=query.key, value=cached_val))

            return resp


def main(port=5440):
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    kvstore_pb2_grpc.add_KVStoreServicer_to_server(KVStoreServicer(), grpc_server)
    grpc_server.add_insecure_port(f'[::]:{port}')

    log_me(f"{globals.name} KV-server listening on: {port}")
    grpc_server.start()
    grpc_server.wait_for_termination()
    log_me(f"{globals.name} KV-server terminated")


if __name__ == '__main__':
    main()
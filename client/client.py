import sys
import grpc
import random
from time import sleep

sys.path.append('../')

from time import time, sleep
import kvstore_pb2
import kvstore_pb2_grpc
import raft_pb2
import raft_pb2_grpc
from threading import Lock, Thread
import concurrent.futures

# Globals
THREAD_COUNT = 1
REQUEST_COUNT = 10
LOCK = Lock()
REQ_TIMES = []
NODE_IPS = {
    "server-1": 'localhost:5440',
    "server-2": 'localhost:5441',
    "server-3": 'localhost:5442',
    # "server-4": 'localhost:5443',
    }
NODE_DOCKER_IPS = {
    "server-1": 'server-1:4000',
    "server-2": 'server-2:4000',
    "server-3": 'server-3:4000',
    # "server-4": 'server-4:4000',
    }
NODE_LOCAL_PORT = {
    "server-1": 'localhost:4000',
    "server-2": 'localhost:4001',
    "server-3": 'localhost:4002',
    # "server-4": 'localhost:4003'
}

# Needs to be set manually.. sed. or does it need to be.
LEADER_NAME = "server-1"

def get_follower():
    for node in NODE_IPS:
        if node != LEADER_NAME:
            return node

    # All are leaders(?).
    return None

def get_all_follower_ips():
    node_ips = []
    for node, ip in NODE_IPS.items():
        if node != LEADER_NAME:
            node_ips.append(ip)
    
    return node_ips

def send_put_ip(ip, key, val):
    try:
        print(f"sending to ip {ip}")
        channel = grpc.insecure_channel(ip)
        stub = kvstore_pb2_grpc.KVStoreStub(channel)
        resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
    except Exception as e:
        print(e)

    return ip

def send_nil_ext_put(key, val):
    global NODE_IPS, LEADER_NAME

    LEADER_IP = NODE_IPS[LEADER_NAME]
    # send_put_ip(LEADER_IP, key, val)

    nodes = get_all_follower_ips()
    nodes.append(LEADER_IP)

    # supermajority = 𝑓 + ⌈𝑓 /2⌉ + 1
    ft =  len(NODE_IPS) // 2
    supermajority = ft + ft // 2 + 1
    print(f"wait for supermajority {supermajority}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Launch 10 tasks in parallel
        futures = [executor.submit(send_put_ip, ip, key, val) for ip in nodes]

        # Wait for at least super majority tasks to complete
        completed_tasks = 0
        leader_sent = False
        done_ips = []
        while not leader_sent and completed_tasks < supermajority:
            done, not_done = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                result = future.result()
                if result not in done_ips:
                    print(f"Task {result} completed")
                    completed_tasks += 1
                    done_ips.append(result)

def send_get(key):
    global NODE_IPS, LEADER_NAME

    LEADER_IP = NODE_IPS[LEADER_NAME]
    channel = grpc.insecure_channel(LEADER_IP)
    stub = kvstore_pb2_grpc.KVStoreStub(channel)

    resp = stub.Get(kvstore_pb2.GetRequest(key=key))
    print(f"GET {key} sent! Response:{resp.key_exists}, key:{resp.key}, val:{resp.value},\
         redirect:{resp.is_redirect}, leader:{resp.redirect_server}")

    if resp.is_redirect:
        LEADER_NAME = resp.redirect_server
        return send_get(key)
    else:
        return resp

def send_request_vote(term, candidate_id, logidx, logterm):
    channel = grpc.insecure_channel('localhost:4000')
    stub = raft_pb2_grpc.RaftProtocolStub(channel)

    resp = stub.RequestVote(raft_pb2.VoteRequest(term=term, candidate_id=candidate_id, last_log_index=logidx, last_log_term=logterm))
    print(f"Vote request sent! Response: {resp.term}, {resp.vote_granted}, {resp.error}")
    return resp

def send_add_node(peer_name):
    for name in NODE_IPS:
        print(f"contacting {NODE_LOCAL_PORT[name]}")
        channel = grpc.insecure_channel(NODE_LOCAL_PORT[name])
        stub = raft_pb2_grpc.RaftProtocolStub(channel)
        resp = stub.AddNode(raft_pb2.NodeRequest(peer_ip=NODE_DOCKER_IPS[peer_name]))
        print(f"Add Node for {peer_name} sent! Response error:{resp.error}")

def send_remove_node(peer_name):
    for name in NODE_IPS:
        if name == peer_name:
            continue  # skip remove node message for current node.
        print(f"Sending remove rpc > {name}")
        channel = grpc.insecure_channel(NODE_LOCAL_PORT[name])
        stub = raft_pb2_grpc.RaftProtocolStub(channel)
        resp = stub.RemoveNode(raft_pb2.NodeRequest(peer_ip=NODE_DOCKER_IPS[peer_name]))
        print(f"Remove Node for {peer_name} sent! Response error:{resp.error}")


def basic_consistency_test():
    # Send a batch of puts.
    for i in range(10):
        send_nil_ext_put(f"Key{i}", f"Val{i}")

    for i in range(10):
        send_get(f"Key{i}")


if __name__ == '__main__':
    counter = 0
    running_threads = []

    send_nil_ext_put("Key4", "Val534")
    send_get("Key4")

    print(f'Completed Client Process!')

# def send_put(key, val):
#     global NODE_IPS, LEADER_NAME

#     # supermajority = 𝑓 + ⌈𝑓 /2⌉ + 1
#     ft =  len(NODE_IPS) // 2
#     supermajority = ft + ft // 2 + 1
#     LEADER_IP = NODE_IPS[LEADER_NAME]
#     for _, ip in list(NODE_IPS.items())[:supermajority]:
#     # print(key, value)
#     # for ip in NODE_IPS[0:supermajority]:
#         channel = grpc.insecure_channel(ip)
#         stub = kvstore_pb2_grpc.KVStoreStub(channel)
#         resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
#         print(f"PUT {key}:{val} sent! Response error:{resp.error}, redirect:{resp.is_redirect}, \
#             {resp.redirect_server}")
#     # Send to leader always
#     channel = grpc.insecure_channel(LEADER_IP)
#     stub = kvstore_pb2_grpc.KVStoreStub(channel)
#     resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
#     if resp.is_redirect:
#         LEADER_NAME = resp.redirect_server
#         return send_put(key, val)
#     else:
#         return resp

# def send_multi_put(keys, vals):
#     global NODE_IPS, LEADER_NAME

#     LEADER_IP = NODE_IPS[LEADER_NAME]
#     channel = grpc.insecure_channel(LEADER_IP)
#     stub = kvstore_pb2_grpc.KVStoreStub(channel)

#     req = kvstore_pb2.MultiPutRequest()
#     for ii, _ in enumerate(keys):
#         req.put_vector.append(kvstore_pb2.PutRequest(key=keys[ii], value=vals[ii]))

#     resp = stub.MultiPut(req)
#     # print(f"redirect:{resp.is_redirect}, \
#     #     {resp.redirect_server}")
#     if resp.is_redirect:
#         LEADER_NAME = resp.redirect_server
#         return send_multi_put(keys, vals)
#     else:
#         return resp


# some stuff, maybe useful later on.

# def send_mult_get(keys):
#     global NODE_IPS, LEADER_NAME

#     LEADER_IP = NODE_IPS[LEADER_NAME]
#     channel = grpc.insecure_channel(LEADER_IP)
#     stub = kvstore_pb2_grpc.KVStoreStub(channel)

#     req = kvstore_pb2.MultiGetRequest()
#     for key in keys:
#         req.get_vector.append(kvstore_pb2.GetRequest(key=key))
    
#     # Make multi get request.
#     resp = stub.MultiGet(req)

#     if resp.is_redirect:
#         LEADER_NAME = resp.redirect_server
#         return send_mult_get(keys)
#     else:
#         return resp

# def best_effort_put(key, val):
#     global NODE_IPS, LEADER_NAME

#     for node in NODE_IPS:
#         print(f"Contacting {node}")
#         try:
#             LEADER_IP = NODE_IPS[node]
#             channel = grpc.insecure_channel(LEADER_IP)
#             stub = kvstore_pb2_grpc.KVStoreStub(channel)

#             resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
#             print(f"PUT {key}:{val} sent! Response error:{resp.error}, redirect:{resp.is_redirect}, \
#                 {resp.redirect_server}")
#             if resp.is_redirect:
#                 if LEADER_NAME != resp.redirect_server:
#                     LEADER_NAME = resp.redirect_server
#                     return send_put(key, val)
#                 else:
#                     continue
#             else:
#                 # Put succeeded.
#                 LEADER_NAME = node
#                 return None
#         except Exception as e:
#             print(f"{node} is down. Contacting another server")

# def best_effort_get(key):
#     global NODE_IPS, LEADER_NAME

#     for node in NODE_IPS:
#         print(f"Contacting {node}")
#         try:
#             LEADER_IP = NODE_IPS[node]
#             channel = grpc.insecure_channel(LEADER_IP)
#             stub = kvstore_pb2_grpc.KVStoreStub(channel)

#             resp = stub.Get(kvstore_pb2.GetRequest(key=key))
#             if resp.is_redirect:
#                 if LEADER_NAME != resp.redirect_server:
#                     LEADER_NAME = resp.redirect_server
#                     return send_get(key)
#                 else:
#                     continue
#             else:
#                 # Put succeeded.
#                 LEADER_NAME = node
#                 return resp
#         except Exception as e:
#             print(f"{node} is down. Contacting another server")
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

LEADER_NAME = "server-1"

def get_follower():
    for node in NODE_IPS:
        if node != LEADER_NAME:
            return node

    # All are leaders(?).
    return None

def random_requests():
    global REQ_TIMES

    # ADDR = f'127.0.0.1:{PORT}'
    channel = grpc.insecure_channel('localhost:5441')
    stub = kvstore_pb2_grpc.KVStoreStub(channel)

    for i in range(REQUEST_COUNT):
        # Choosing key/value pair
        thread_key = str(random.randint(1, 3))
        thread_value = str(random.randint(1, 40))

        # Choosing which request to send
        run_set_num = random.choice([True, False])
        if run_set_num:
            t1 = time()
            resp = stub.Put(kvstore_pb2.PutRequest(key=thread_key, value=thread_value))
            t2 = time()
            with LOCK:
                REQ_TIMES.append(t2 - t1)

        else:
            t1 = time()
            resp = stub.Get(kvstore_pb2.GetRequest(key=thread_key))
            print(f'[LOG] for {thread_key}, got {resp.value} {resp.key_exists}')
            t2 = time()
            with LOCK:
                REQ_TIMES.append(t2 - t1)


def send_put(key, val):
    global NODE_IPS, LEADER_NAME

    # supermajority = 𝑓 + ⌈𝑓 /2⌉ + 1
    ft =  len(NODE_IPS) // 2
    supermajority = ft + ft // 2 + 1
    LEADER_IP = NODE_IPS[LEADER_NAME]
    for _, ip in list(NODE_IPS.items())[:supermajority]:
    # print(key, value)
    # for ip in NODE_IPS[0:supermajority]:
        channel = grpc.insecure_channel(ip)
        stub = kvstore_pb2_grpc.KVStoreStub(channel)
        resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
        print(f"PUT {key}:{val} sent! Response error:{resp.error}, redirect:{resp.is_redirect}, \
            {resp.redirect_server}")
    # Send to leader always
    channel = grpc.insecure_channel(LEADER_IP)
    stub = kvstore_pb2_grpc.KVStoreStub(channel)
    resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
    if resp.is_redirect:
        LEADER_NAME = resp.redirect_server
        return send_put(key, val)
    else:
        return resp

def send_multi_put(keys, vals):
    global NODE_IPS, LEADER_NAME

    LEADER_IP = NODE_IPS[LEADER_NAME]
    channel = grpc.insecure_channel(LEADER_IP)
    stub = kvstore_pb2_grpc.KVStoreStub(channel)

    req = kvstore_pb2.MultiPutRequest()
    for ii, _ in enumerate(keys):
        req.put_vector.append(kvstore_pb2.PutRequest(key=keys[ii], value=vals[ii]))

    resp = stub.MultiPut(req)
    # print(f"redirect:{resp.is_redirect}, \
    #     {resp.redirect_server}")
    if resp.is_redirect:
        LEADER_NAME = resp.redirect_server
        return send_multi_put(keys, vals)
    else:
        return resp

def best_effort_put(key, val):
    global NODE_IPS, LEADER_NAME

    for node in NODE_IPS:
        print(f"Contacting {node}")
        try:
            LEADER_IP = NODE_IPS[node]
            channel = grpc.insecure_channel(LEADER_IP)
            stub = kvstore_pb2_grpc.KVStoreStub(channel)

            resp = stub.Put(kvstore_pb2.PutRequest(key=key, value=val))
            print(f"PUT {key}:{val} sent! Response error:{resp.error}, redirect:{resp.is_redirect}, \
                {resp.redirect_server}")
            if resp.is_redirect:
                if LEADER_NAME != resp.redirect_server:
                    LEADER_NAME = resp.redirect_server
                    return send_put(key, val)
                else:
                    continue
            else:
                # Put succeeded.
                LEADER_NAME = node
                return None
        except Exception as e:
            print(f"{node} is down. Contacting another server")

def best_effort_get(key):
    global NODE_IPS, LEADER_NAME

    for node in NODE_IPS:
        print(f"Contacting {node}")
        try:
            LEADER_IP = NODE_IPS[node]
            channel = grpc.insecure_channel(LEADER_IP)
            stub = kvstore_pb2_grpc.KVStoreStub(channel)

            resp = stub.Get(kvstore_pb2.GetRequest(key=key))
            if resp.is_redirect:
                if LEADER_NAME != resp.redirect_server:
                    LEADER_NAME = resp.redirect_server
                    return send_get(key)
                else:
                    continue
            else:
                # Put succeeded.
                LEADER_NAME = node
                return resp
        except Exception as e:
            print(f"{node} is down. Contacting another server")

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

def send_mult_get(keys):
    global NODE_IPS, LEADER_NAME

    LEADER_IP = NODE_IPS[LEADER_NAME]
    channel = grpc.insecure_channel(LEADER_IP)
    stub = kvstore_pb2_grpc.KVStoreStub(channel)

    req = kvstore_pb2.MultiGetRequest()
    for key in keys:
        req.get_vector.append(kvstore_pb2.GetRequest(key=key))
    
    # Make multi get request.
    resp = stub.MultiGet(req)

    if resp.is_redirect:
        LEADER_NAME = resp.redirect_server
        return send_mult_get(keys)
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
    # Try to get a value not written
    resp = send_get("Key0")
    # Send single put and 2 gets (one valid one invalid)
    # send_put("Key1", "Val1")
    for i in range(10):
        send_put(f"Key{i}", f"Val{i}")
    send_put("Key43", "Val534")
    send_get("Key43")

    send_put("Key6", "Val6")
    send_get("Key6")

    # send_add_node("server-4:4000")

    send_put("Key3", "Val3")
    send_get("Key1")

    send_put("Key2", "Val2")
    send_get("Key2")


if __name__ == '__main__':
    counter = 0
    running_threads = []

    # Spawn multiple threads and sent random get/put requests
    # sleep(2)
    #
    # # Start all threads
    # while counter < THREAD_COUNT:
    #     t = Thread(target=random_requests)
    #     t.start()
    #     running_threads.append(t)
    #     counter += 1
    #
    # # Wait for threads to finish running
    # for t in running_threads:
    #     t.join()

    # Send single put and 2 gets (one valid one invalid)
    # send_put("Key1", "Val1")
    send_put("Key43", "Val534")
    send_get("Key43")

    # send_put("Key6", "Val6")
    # send_get("Key6")

    # send_add_node("server-4:4000")

    # send_put("Key3", "Val3")
    # send_get("Key1")

    # send_put("Key2", "Val2")
    # send_get("Key2")

    # send_remove_node("server-4:4000")

    print(f'Completed Client Process!')
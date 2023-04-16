import sys
import grpc
import random
import numpy as np
from time import sleep

sys.path.append('../')

from time import time
import kvstore_pb2
import kvstore_pb2_grpc
import raft_pb2
import raft_pb2_grpc
from threading import Lock, Thread
from client.perf_client import *

# Globals
THREAD_COUNT = 5
REQUEST_COUNT = 10000
LOCK = Lock()
REQ_TIMES = []


def random_requests():
    global REQ_TIMES

    # ADDR = f'127.0.0.1:{PORT}'
    channel = grpc.insecure_channel('localhost:5440')
    stub = kvstore_pb2_grpc.KVStoreStub(channel)

    for i in range(REQUEST_COUNT):
        # Choosing key/value pair
        thread_key = str(random.randint(1, 3))
        thread_value = str(random.randint(1, 40))

        # Choosing which request to send
        t1 = time()
        resp = send_put(thread_key, thread_value)
        t2 = time()
        with LOCK:
            REQ_TIMES.append(t2 - t1)


if __name__ == '__main__':
    counter = 0
    running_threads = []

    # Start THREAD_COUNT number of threads
    while (counter < THREAD_COUNT):
        t = Thread(target=random_requests)
        t.start()
        running_threads.append(t)
        counter += 1

    # Wait for threads to finish running
    for t in running_threads:
        t.join()

    # Printing Summary Stats
    print(f'Put request statistics: %\np50 response time: {np.percentile(REQ_TIMES, q=50)}' +
          f' seconds\np99 response time: {np.percentile(REQ_TIMES, q=99)} seconds')

    print(f'Completed Client Process!')

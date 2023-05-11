import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

import numpy as np

import client

sys.path.append('../')


def measure_nil_ext_put(key, val):
    t1 = time()
    client.send_nil_ext_put(key, val)
    t2 = time()

    return t2 - t1

def measure_get(key):
    t1 = time()
    client.send_get(key)
    t2 = time()

    return t2 - t1

def run_put_exp():
    latencies, batch_throughputs = [], []

    points = [1, 2, 4, 8]
    points.extend([i for i in range(10, 101, 10)]) 
    for thread_count in points:
        batch = []
        print(f"Collecting PUT stats with {thread_count} threads")

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            value = f"Value-{random.randint(1, pow(10, 10))}"
            t1 = time()
            future_calls = {executor.submit(
                measure_nil_ext_put, key, value) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result())
            t2 = time()
            batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        latencies.append((thread_count, batch))

    x, y = zip(*batch_throughputs)
    latency_stats = [(np.percentile(i[1], 1), np.median(i[1]), np.percentile(i[1], 99)) for i in latencies]
    return x, y, latency_stats

def run_get_exp():
    latencies, batch_throughputs = [], []

    points = [1, 2, 4, 8]
    points.extend([i for i in range(10, 100, 10)])
    points.extend([i for i in range(100, 501, 100)]) 
    for thread_count in points:
        batch = []
        print(f"Collecting GET stats with {thread_count} threads")

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            t1 = time()
            future_calls = {executor.submit(
                measure_get, key) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result())
            t2 = time()
            batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        latencies.append((thread_count, batch))

    x, y = zip(*batch_throughputs)
    latency_stats = [(np.percentile(i[1], 1), np.median(i[1]), np.percentile(i[1], 99)) for i in latencies]
    return x, y, latency_stats

def collect_stats(run_exp):
    throughputs, latencies = [], []
    for i in range(2):
        _, thrp, lat = run_exp()
        throughputs.append(thrp)
        latencies.append(lat)

    avg_throughputs = [sum(a)/ len(a) for a in zip(*throughputs)]
    avg_lat = []
    # print(latencies)
    for l in zip(*latencies):
        avg_tuple = []
        for r in zip(*l):
            avg_tuple.append(sum(r)/len(r))
        avg_lat.append(avg_tuple)

    print("latencies", avg_lat)
    print("throughputs", avg_throughputs)

if __name__ == '__main__':
    collect_stats(run_get_exp)

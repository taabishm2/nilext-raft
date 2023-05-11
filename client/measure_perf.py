import pickle
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from matplotlib import pyplot as plt
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

    points = [1, 2, 4, 6,8]
    points.extend([i for i in range(10, 101, 3)])
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
    latency_stats = [(np.median(i[1]), np.percentile(i[1], 99)) for i in latencies]
    return x, y, latency_stats

def run_get_exp():
    latencies, batch_throughputs = [], []

    points = [1, 2, 3, 4, 6, 8]
    points.extend([i for i in range(10, 100, 3)])
    # points.extend([i for i in range(100, 201, 20)]) 
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

def collect_stats(run_exp, NUM_SERVERS=3):
    throughputs, latencies = [], []
    x_range = []
    for i in range(10):
        x_range, thrp, lat = run_exp()
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

    with open(f'plot_data/PUT-median-latency_num_clients.pickle', 'wb') as f:
        pickle.dump((x_range, [y[0] for y in avg_lat]), f)

    with open(f'plot_data/PUT-p99-latency_num_clients.pickle', 'wb') as f:
        pickle.dump((x_range, [y[1] for y in avg_lat]), f)
    
    with open(f'plot_data/PUT-throughput_num_clients.pickle', 'wb') as f:
        pickle.dump((x_range, avg_throughputs), f)

def plot_put_data():
    x_range, median_lat, p99_lat, avg_throughputs = [], [], [], []

    with open(f'plot_data/PUT-median-latency_num_clients.pickle', 'rb') as f:
        x_range, median_lat = pickle.load(f)
    with open(f'plot_data/PUT-p99-latency_num_clients.pickle', 'rb') as f:
        x_range, p99_lat = pickle.load(f)
    with open(f'plot_data/PUT-throughput_num_clients.pickle', 'rb') as f:
        x_range, avg_throughputs = pickle.load(f)

    plt.figure(dpi=200)
    plt.plot(x_range, median_lat, label="Median")
    plt.plot(x_range, p99_lat, label="p99")
    
    plt.title("Latency vs num clients")
    plt.xlabel("Num_clients")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.savefig(f'graphs/PUT-latency.png')
    plt.clf()

    plt.figure(dpi=200)
    plt.plot(x_range, avg_throughputs)
    
    plt.title("Throughput vs num clients")
    plt.xlabel("Num_clients")
    plt.ylabel("Observed Throughput (Op/sec)")
    plt.savefig(f'graphs/PUT-throughput.png')
    plt.clf()

    plt.figure(dpi=200)
    plt.plot(avg_throughputs, median_lat)
    
    plt.title("Throughput vs Latency")
    plt.xlabel("Throughput")
    plt.ylabel("Latency")
    plt.savefig(f'graphs/PUT-throughput-latency.png')
    plt.clf()

if __name__ == '__main__':
    collect_stats(run_put_exp)
    plot_put_data()

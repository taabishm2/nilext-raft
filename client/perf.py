import shelve
import subprocess

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import perf_client
import random
import time
import numpy as np
from matplotlib import pyplot as plt
import numpy as np
from collections import defaultdict
import pickle
import numpy as np
from math import factorial

NUM_SERVERS = 5


def restart_cluster(remove_logs=True):
    print(f"Restarting cluster with remove-logs = {remove_logs}")

    if remove_logs:
        result = subprocess.run(
            r'cd .. && sudo rm -rf logs/logcache/*', shell=True)
        check_shell_cmd(result, "removing logcache dir")

    result = subprocess.run(
        r'cd .. && python3 -m grpc_tools.protoc --proto_path=protos --python_out=./ --grpc_python_out=./ protos/kvstore.proto',
        shell=True)
    check_shell_cmd(result, "building kvstore.proto")

    result = subprocess.run(
        r'cd .. && python3 -m grpc_tools.protoc --proto_path=protos --python_out=./ --grpc_python_out=./ protos/raft.proto',
        shell=True)
    check_shell_cmd(result, "building raft.proto")

    try:
        # result = subprocess.run(
        #     r'cd .. && cd docker; docker compose down; docker compose kill; docker compose rm -f; cd ..; docker kill $(docker ps -qa); docker rm $(docker ps -qa)', shell=True)

        result = subprocess.run(
            r'docker kill $(docker ps -qa); docker rm $(docker ps -qa)', shell=True)

        check_shell_cmd(result, "killing docker containers")
    except:
        pass

    result = subprocess.run(
        r'cd .. && docker build -t kvstore -f ./docker/Dockerfile .', shell=True)
    check_shell_cmd(result, "building Dockerfile")

    result = subprocess.run(
        r'cd .. && docker compose -f ./docker/docker-compose.yaml up -d', shell=True)
    check_shell_cmd(result, "composing containers")

    time.sleep(5)

    result = subprocess.run(r'cd .. && sudo chmod -R a+rw logs/', shell=True)
    check_shell_cmd(result, "setting log permissions")

    print("Completed Restart")


def check_shell_cmd(result, command_action):
    if result.returncode != 0:
        raise Exception(f'[ERROR] while {command_action}: {result.stderr}')


def collect_get_lat_thrp():
    latencies, batch_throughputs = [], []

    for thread_count in range(1, 1000, 5):
        batch = []
        print(f"Testing GET with {thread_count} threads")

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            t1 = time.time()
            future_calls = {executor.submit(
                perf_client.send_get, key) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result()[0])
            t2 = time.time()
            batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        latencies.append((thread_count, batch))

    x, y = zip(*batch_throughputs)
    with open(f'data/{NUM_SERVERS}-server-GET-parallel-throughputs.pickle', 'wb') as f:
        pickle.dump((x, y), f)

    latencies = [(i[0], np.percentile(i[1], 1), np.median(i[1]), np.percentile(i[1], 99)) for i in latencies]

    with open(f'data/{NUM_SERVERS}-server-GET-parallel-min-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[1] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-GET-parallel-median-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[2] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-GET-parallel-max-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[3] for y in latencies]), f)

    print("Done")


def plot_get_latency_3_server():
    x, low, mid, high = [], [], [], []

    with open(f'data/3-server-GET-parallel-min-latency.pickle', 'rb') as f:
        x, low = pickle.load(f)
    with open(f'data/3-server-GET-parallel-median-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    with open(f'data/3-server-GET-parallel-max-latency.pickle', 'rb') as f:
        x, high = pickle.load(f)

    plt.figure(dpi=200)
    plt.plot(x, smoothen(low, 5, 3), label="1 percentile")
    plt.plot(x, smoothen(mid, 11, 6), label="Median")
    plt.plot(x, smoothen(high, 21, 8), label="99 percentile")

    plt.title("Latency vs concurrent GET request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.savefig(f'graphs/3serve-GET-parallel-latency.png')
    plt.clf()


def plot_get_latency():
    x, low, mid, high = [], [], [], []
    with open(f'data/3-server-GET-parallel-median-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, smoothen(mid, 11, 2), label="3 servers")

    x, low, mid, high = [], [], [], []
    with open(f'data/5-server-GET-parallel-median-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)

    plt.plot(x, smoothen(mid, 11, 2), label="5 servers", color='red')

    plt.title("Median latency vs concurrent GET request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.ylim(0, 0.06)
    plt.savefig(f'graphs/GET-parallel-latency.png')
    plt.clf()


def plot_get_throughput():
    fl3 = f'data/3-server-GET-parallel-throughputs.pickle'
    fl5 = f'data/5-server-GET-parallel-throughputs.pickle'

    x, y = [], []
    with open(f"{fl3}", 'rb') as f:
        x, y = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, smoothen_old(list(y)), label="3 servers")

    x, y = [], []
    with open(f"{fl5}", 'rb') as f:
        x, y = pickle.load(f)
    plt.plot(x, smoothen_old(list(y)), label="5 servers", color="red")

    plt.title("Throughput vs concurrent GET request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed throughput (req/s)")
    plt.legend()
    plt.savefig(f'graphs/GET-parallel-throughputs.png')
    plt.clf()


def collect_put_lat_thrp():
    latencies, batch_throughputs = [], []
    for thread_count in range(1, 500, 15):
        restart_cluster()
        batch = []
        print(f"Testing PUT with {thread_count} threads")
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            t1 = time.time()
            future_calls = {executor.submit(
                perf_client.send_put, key, key) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result())
            t2 = time.time()
            batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        latencies.append((thread_count, batch))

    x, y = zip(*batch_throughputs)
    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-throughputs.pickle', 'wb') as f:
        pickle.dump((x, y), f)

    latencies = [(i[0], np.percentile(i[1], 1), sum(i[1]) /
                  len(i[1]), np.percentile(i[1], 99)) for i in latencies]

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-min-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[1] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-median-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[2] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-max-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[3] for y in latencies]), f)

    print("Done")

def collect_get_overhead_from_dur_log():
    
    x, y = [], []
    
    for put_count in range(0, 1000, 100):
        batch = []
        if put_count > 0:
            with ThreadPoolExecutor(max_workers=put_count) as executor:
                key = f"KEY-{random.randint(1, pow(10, 8))}"
                future_calls = {executor.submit(
                    perf_client.send_put, key, key) for _ in range(put_count)}
                for completed_task in as_completed(future_calls):
                    batch.append(completed_task.result())
        
        last_key_v = random.randrange(pow(10,9), pow(10,15))
        key = f"KEY-{put_count}-{last_key_v}"
        val = f"VAL-{put_count}-{last_key_v}"
        
        time.sleep(1)
        
        r = perf_client.send_put(key, val, True) 
        print(f"Sent PUT {key}:{val}")

        t1 = time.time()
        resp = perf_client.send_get(key)
        t = time.time() - t1
        
        print(f"GOT {key} {resp[1].key_exists}:{resp[1].value}")
        assert resp[1].value == val
    
        x.append(put_count)
        y.append(t)
    
    plt.plot(x, y)

    plt.title("Durability log overhead")
    plt.xlabel("Durability log size")
    plt.ylabel("Read latency")
    plt.savefig(f'graphs/durability-log-read-latency.png')
    plt.clf()


def plot_put_throughput():
    fl3 = f'data/3-server-PUT-parallel-throughputs.pickle'
    fl5 = f'data/5-server-PUT-parallel-throughputs.pickle'

    x, y = [], []
    with open(f"{fl3}", 'rb') as f:
        x, y = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, y, label="3 servers")

    x, y = [], []
    with open(f"{fl5}", 'rb') as f:
        x, y = pickle.load(f)

    plt.plot(x, y, label="5 servers")

    plt.title("Throughput vs concurrent PUT request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed throughput (req/s)")
    plt.legend()
    plt.savefig(f'graphs/PUT-parallel-throughputs.png')
    plt.clf()
    
    
    
def plot_put_throughput_nilext():
    fl3 = f'data/{NUM_SERVERS}-server-nilext-PUT-parallel-throughputs.pickle'
    fl5 = f'data/{NUM_SERVERS}-server-PUT-parallel-throughputs.pickle'

    x, y = [], []
    with open(f"{fl3}", 'rb') as f:
        x, y = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, y, label="Nilext")

    x, y = [], []
    with open(f"{fl5}", 'rb') as f:
        x, y = pickle.load(f)

    plt.plot(x, y, label="Non-nilext")

    plt.title("Throughput vs concurrent PUT request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed throughput (req/s)")
    plt.legend()
    plt.savefig(f'graphs/PUT-parallel-throughputs.png')
    plt.clf()


def plot_put_latency_3_server(nilext=""):
    x, low, mid, high = [], [], [], []

    with open(f'data/{NUM_SERVERS}-server{nilext}-PUT-parallel-min-latency.pickle', 'rb') as f:
        x, low = pickle.load(f)
    with open(f'data/{NUM_SERVERS}-server{nilext}-PUT-parallel-median-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    with open(f'data/{NUM_SERVERS}-server{nilext}-PUT-parallel-max-latency.pickle', 'rb') as f:
        x, high = pickle.load(f)

    plt.figure(dpi=200)
    plt.plot(x, low, label="1 percentile")
    plt.plot(x, mid, label="Median")
    plt.plot(x, high, label="99 percentile")
    
    print(low)
    print(mid)
    print(high)

    plt.title("Latency vs concurrent PUT request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.savefig(f'graphs/{NUM_SERVERS}serve{nilext}-PUT-parallel-latency.png')
    plt.clf()


def plot_put_latency():
    x, low, mid, high = [], [], [], []
    with open(f'data/3-server-PUT-parallel-median-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, mid, label="3 servers")

    x, low, mid, high = [], [], [], []
    with open(f'data/5-server-PUT-parallel-median-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)

    plt.plot(x, mid, label="5 servers")

    plt.title("Median latency vs concurrent PUT request count")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.savefig(f'graphs/PUT-parallel-latency.png')
    plt.clf()


def collect_put_lat_thrp_nr():
    latencies, batch_throughputs = [], []
    for thread_count in range(1, 500, 10):
        batch = []
        print(f"Testing PUT with {thread_count} threads")
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            t1 = time.time()
            future_calls = {executor.submit(
                perf_client.send_put, key, key) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result())
            t2 = time.time()
            batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        latencies.append((thread_count, batch))

    x, y = zip(*batch_throughputs)
    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-throughputs_no_restart.pickle', 'wb') as f:
        pickle.dump((x, y), f)

    latencies = [(i[0], np.percentile(i[1], 1), sum(i[1]) /
                  len(i[1]), np.percentile(i[1], 99)) for i in latencies]

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-min-latency_no_restart.pickle', 'wb') as f:
        pickle.dump((x, [y[1] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-median-latency_no_restart.pickle', 'wb') as f:
        pickle.dump((x, [y[2] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-max-latency_no_restart.pickle', 'wb') as f:
        pickle.dump((x, [y[3] for y in latencies]), f)

    print("Done")


def plot_put_throughput_nr():
    fl3 = f'data/3-server-PUT-parallel-throughputs_no_restart.pickle'
    fl5 = f'data/5-server-PUT-parallel-throughputs_no_restart.pickle'

    x, y = [], []
    with open(f"{fl3}", 'rb') as f:
        x, y = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, y, label="3 servers")

    x, y = [], []
    with open(f"{fl5}", 'rb') as f:
        x, y = pickle.load(f)

    plt.plot(x, y, label="5 servers")

    plt.title("Throughput vs concurrent PUT request count (log retained)")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed throughput (req/s)")
    plt.legend()
    plt.savefig(f'graphs/PUT-parallel-throughputs-nr.png')
    plt.clf()


def plot_put_latency_3_server_nr():
    x, low, mid, high = [], [], [], []

    with open(f'data/3-server-PUT-parallel-min-latency_no_restart.pickle', 'rb') as f:
        x, low = pickle.load(f)
    with open(f'data/3-server-PUT-parallel-median-latency_no_restart.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    with open(f'data/3-server-PUT-parallel-max-latency_no_restart.pickle', 'rb') as f:
        x, high = pickle.load(f)

    plt.figure(dpi=200)
    plt.plot(x, low, label="1 percentile")
    plt.plot(x, mid, label="Median")
    plt.plot(x, smoothen(high, 11, 7), label="99 percentile")

    plt.title("Latency vs concurrent PUT request count (log retained)")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.savefig(f'graphs/3serve-PUT-parallel-latency-nr.png')
    plt.clf()


def plot_put_latency_nr():
    x, low, mid, high = [], [], [], []
    with open(f'data/3-server-PUT-parallel-median-latency_no_restart.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, mid, label="3 servers")

    x, low, mid, high = [], [], [], []
    with open(f'data/5-server-PUT-parallel-median-latency_no_restart.pickle', 'rb') as f:
        x, mid = pickle.load(f)

    plt.plot(x, mid, label="5 servers")

    plt.title("Median latency vs concurrent PUT request count (log retained)")
    plt.xlabel("Count of concurrent requests")
    plt.ylabel("Observed latency (sec)")
    plt.legend()
    plt.savefig(f'graphs/PUT-parallel-latency-nr.png')
    plt.clf()


def collect_perf_degradation():
    logs_added_inbetween, iterations = 200, 50
    put_times, get_times, throughputs = [], [], []

    for iteration in range(iterations):
        print(f"Iteration {iteration} of {iterations}")

        t1 = time.time()
        with ThreadPoolExecutor(max_workers=logs_added_inbetween) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            future_calls = {executor.submit(
                perf_client.send_put, key, key) for _ in range(logs_added_inbetween)}
            for completed_task in as_completed(future_calls):
                pass
        t2 = time.time()
        throughputs.append(logs_added_inbetween / (t2 - t1))

        write_time, read_time = 0, 0
        avg_over = 3
        for _ in range(avg_over):
            write_time += perf_client.send_put("Key", "Val")
            read_time += perf_client.send_get("Key")[0]
        put_times.append(write_time / avg_over)
        get_times.append(read_time / avg_over)

    with open(f'data/{NUM_SERVERS}-server-PUT-degrade-latency.pickle', 'wb') as f:
        pickle.dump(([i for i in range(0, iterations * logs_added_inbetween, logs_added_inbetween)],
                     put_times), f)

    with open(f'data/{NUM_SERVERS}-server-GET-degrade-latency.pickle', 'wb') as f:
        pickle.dump(([i for i in range(0, iterations * logs_added_inbetween, logs_added_inbetween)],
                     get_times), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-degrade-throughputs.pickle', 'wb') as f:
        pickle.dump(([i for i in range(0, iterations * logs_added_inbetween, logs_added_inbetween)],
                     throughputs), f)


def plot_put_degrade_lat():
    x, y = [], []
    with open(f'data/3-server-PUT-degrade-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, smoothen_old(mid), label="3 servers")

    x, y = [], []
    with open(f'data/5-server-PUT-degrade-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.plot(x, smoothen_old(mid), label="5 servers")

    plt.title("PUT Latency vs persistent log size")
    plt.xlabel("Count of entries in log")
    plt.ylabel("Observed latency (sec))")
    plt.legend()
    plt.savefig(f'graphs/PUT-degrade-latency.png')
    plt.clf()


def plot_get_degrade_lat():
    x, y = [], []
    with open(f'data/3-server-GET-degrade-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, mid, label="3 servers")

    x, y = [], []
    with open(f'data/5-server-GET-degrade-latency.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.plot(x, mid, label="5 servers")

    plt.title("GET Latency vs persistent log size")
    plt.xlabel("Count of entries in log")
    plt.ylabel("Observed latency (sec))")
    plt.legend()
    plt.savefig(f'graphs/GET-degrade-latency.png')
    plt.clf()


def plot_put_degrade_throughput():
    x, y = [], []
    with open(f'data/3-server-PUT-degrade-throughputs.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, mid, label="3 servers")

    x, y = [], []
    with open(f'data/5-server-PUT-degrade-throughputs.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.plot(x, mid, label="5 servers")

    plt.title(f"Throughput of 100 PUTs vs persistent log size")
    plt.xlabel("Count of entries in log")
    plt.ylabel("Observed throughput (req/s) for 100 PUTs")
    plt.legend()
    plt.savefig(f'graphs/PUT-degrade-throughput.png')
    plt.clf()


def collect_single_thread_throughput():
    ctr_dict = defaultdict(int)
    td = time.time()
    while time.time() - td < 200:
        key = f"key-123"
        try:
            resp = perf_client.send_put_for_val(key, key)
            if resp.error or resp.is_redirect:
                ctr_dict[int(time.time() - td)] += 0
            else:
                ctr_dict[int(time.time() - td)] += 1
        except:
            ctr_dict[int(time.time() - td)] += 0

    sorted_keys = sorted(ctr_dict.keys())
    y = [ctr_dict[key] for key in sorted_keys]

    with open(f'data/{NUM_SERVERS}-server-PUT-singlethread-throughput.pickle', 'wb') as f:
        pickle.dump((sorted_keys, y), f)

    print("Done")


def plot_put_singleT_throughput():
    x, y = [], []
    with open(f'data/3-server-PUT-singlethread-throughput.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x[:-1], mid[:-1], label="3 servers")

    x, y = [], []
    with open(f'data/5-server-PUT-singlethread-throughput.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.plot(x[:-1], mid[:-1], label="5 servers")

    plt.title(f"Throughput of single threaded PUTs vs time")
    plt.xlabel("Time elapsed (sec)")
    plt.ylabel("Observed throughput (req/s)")
    plt.legend()
    plt.ylim(0, 60)
    plt.savefig(f'graphs/PUT-singleT-throughput.png')
    plt.clf()


def collect_single_thread_throughput_leader_killed():
    leader_ip = perf_client.LEADER_NAME
    g = perf_client.send_get_wo_redirect("KEY", leader_ip)
    if g.is_redirect:
        leader_ip = g.redirect_server
    ips_logs = {"server-1": "server1", "server-2": "server2"}
    to_be_contacted = [i for i in ips_logs.keys() if i != leader_ip][0]

    ctr_dict = defaultdict(int)
    td = time.time()

    threads = 50
    while time.time() - td < 10:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_calls = {executor.submit(
                perf_client.send_get_wo_redirect, "KEY", leader_ip) for _ in range(threads)}
            for completed_task in as_completed(future_calls):
                resp = completed_task.result()
                assert resp.is_redirect == False
                ctr_dict[int((time.time() - td) * 10)] += 50

    perf_client.send_remove_node(leader_ip)

    while True:
        ctr_dict[int((time.time() - td) * 10)] += 0
        resp = perf_client.send_get_wo_redirect("KEY", to_be_contacted)
        print("Waiting to resume:", resp.is_redirect, resp.redirect_server != leader_ip)
        if resp.is_redirect == False or (resp.is_redirect and resp.redirect_server != leader_ip):
            if resp.is_redirect: to_be_contacted = resp.redirect_server
            break

    tn = time.time()
    while time.time() - tn < 10:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_calls = {executor.submit(
                perf_client.send_get_wo_redirect, "KEY", to_be_contacted) for _ in range(threads)}
            for completed_task in as_completed(future_calls):
                resp = completed_task.result()
                assert resp.is_redirect == False
                ctr_dict[int((time.time() - td) * 10)] += 50

    sorted_keys = sorted(ctr_dict.keys())
    y = [ctr_dict[key] for key in sorted_keys]

    with open(f'data/{NUM_SERVERS}-server-PUT-availability-singlethread-throughput.pickle', 'wb') as f:
        pickle.dump((sorted_keys, y), f)

    print("Done")


def plot_put_singleT_leader_killed():
    x, y = [], []
    with open(f'data/3-server-PUT-availability-singlethread-throughput.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    ax1.plot(x, mid, label='3 servers')
    ax1.legend()

    x, y = [], []
    with open(f'data/5-server-PUT-availability-singlethread-throughput.pickle', 'rb') as f:
        x, mid = pickle.load(f)

    ax2.plot(x, mid, label='5 servers')
    ax2.legend()

    plt.suptitle(f"System Availability on leader crash")
    # plt.xlabel("Time elapsed (sec)")
    # plt.ylabel("Observed throughput (req/s)")
    # plt.legend()
    plt.savefig(f'graphs/PUT-singleT-leader-killed.png')
    plt.clf()


def collect_log_recovery_time():
    # need atleast one log entry
    perf_client.send_put("AB", "CD")
    xaxis, yaxis = [], []
    for log_diff in range(10, 500, 10):
        # print("Log diff=", log_diff)

        # Since leader might change, re-fetch
        leader_ip = perf_client.LEADER_NAME
        g = perf_client.send_get_wo_redirect("K", leader_ip)
        if g.is_redirect:
            leader_ip = g.redirect_server
        ips_logs = {"server-1": "server1", "server-2": "server2", "server-3": "server3"}
        to_be_killed = [i for i in ips_logs.keys() if i != leader_ip][0]
        print(f"Leader: {leader_ip}, to be killed: {to_be_killed}")

        xaxis.append(log_diff)
        # kill to_be_killed with remove node
        perf_client.send_remove_node(to_be_killed)

        # Make 'log_diff' appends to leader
        with ThreadPoolExecutor(max_workers=log_diff) as executor:
            future_calls = {executor.submit(
                perf_client.send_put, "KEY", "VAL") for _ in range(log_diff)}
            for completed_task in as_completed(future_calls):
                pass

        leader_shelve = shelve.open(
            f"../logs/logcache/server{leader_ip[-1]}/stable_log")
        leader_log_size = leader_shelve["SHELF_SIZE"]

        # add killed node back
        dead_node_shelve = shelve.open(
            f"../logs/logcache/server{to_be_killed[-1]}/stable_log")
        init_log_size = dead_node_shelve["SHELF_SIZE"]
        dead_node_shelve.close()

        add_thread = threading.Thread(
            target=perf_client.send_add_node, args=(to_be_killed,))
        add_thread.start()

        # Re-add dead node and wait till it sees last_key
        t1 = time.time()
        while True:
            # directly open shelve log of killed node
            to = time.time()
            dead_node_shelve = shelve.open(
                f"../logs/logcache/server{to_be_killed[-1]}/stable_log")
            try:
                log_size = dead_node_shelve["SHELF_SIZE"]
            except:
                continue
            dead_node_shelve.close()
            tc = time.time()

            if log_size >= leader_log_size:
                yaxis.append(time.time() - t1)
                # print(
                #     f"took {yaxis[-1]} secs for [{log_size - init_log_size}] diff")
                break

    with open(f'data/{NUM_SERVERS}-server-dead-node-recoverytime.pickle', 'wb') as f:
        pickle.dump((xaxis, yaxis), f)

    print("Done")


def plot_log_recovery_time():
    x, y = [], []
    with open(f'data/3-server-dead-node-recoverytime.pickle', 'rb') as f:
        x, mid = pickle.load(f)
    plt.figure(dpi=200)
    plt.plot(x, mid, label="3 servers")

    # x, y = [], []
    # with open(f'data/5-server-dead-node-recoverytime.pickle', 'rb') as f:
    #     x, mid = pickle.load(f)
    # plt.figure(dpi=200)
    # plt.plot(x, mid, label="5 servers")

    plt.title(f"Log recovery time for out-of-date nodes")
    plt.xlabel("Count of entries missing in out-of-date node")
    plt.ylabel("Time to fully recover log (sec)")
    plt.legend()
    plt.savefig(f'graphs/log-recovery.png')
    plt.clf()


WORKLOAD_DURATION = 200


def _some_workload():
    t1 = time.time()
    while time.time() - t1 < WORKLOAD_DURATION:
        choice = random.randint(0, 2)

        threads = 10
        print(f"{threads} PUT threads")
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_calls = {executor.submit(
                perf_client.send_put, "KEY", "VAL") for _ in range(threads)}
            for completed_task in as_completed(future_calls):
                pass

        threads = 10
        print(f"{threads} GET threads")
        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_calls = {executor.submit(
                perf_client.send_get, "KEY") for _ in range(threads)}
            for completed_task in as_completed(future_calls):
                pass


def collect_internal_server_stats():
    leader_ip = perf_client.LEADER_NAME
    g = perf_client.send_get_wo_redirect("K", leader_ip)
    if g.is_redirect:
        leader_ip = g.redirect_server

    # run some workload for some time first
    _some_workload()
    # assumes no leadership change occurs

    # trigger flush of server stats
    perf_client.send_get("FLUSH_CALL_STATS")

    result = subprocess.run(r'cd .. && sudo chmod -R a+rw logs/', shell=True)
    check_shell_cmd(result, "setting log permissions")

    with open(f'data/{NUM_SERVERS}-server-stats-commit-latency.pickle', 'wb') as f:
        pickle.dump(shelve.open(f"../logs/logcache/server{leader_ip[-1]}/server-rpc-stats")["COMMIT_LAT"], f)

    with open(f'data/{NUM_SERVERS}-server-stats-kv-requests.pickle', 'wb') as f:
        pickle.dump(shelve.open(f"../logs/logcache/server{leader_ip[-1]}/server-rpc-stats")["KV_REQS"], f)

    with open(f'data/{NUM_SERVERS}-server-stats-raft-requests.pickle', 'wb') as f:
        pickle.dump(shelve.open(f"../logs/logcache/server{leader_ip[-1]}/server-rpc-stats")["RAFT_REQS"], f)

    print("Done")


def plot_internal_latency():
    data1 = []
    with open(f'data/3-server-stats-commit-latency.pickle', 'rb') as f:
        data1 = [i[2] for i in pickle.load(f)]

    data2 = []
    with open(f'data/5-server-stats-commit-latency.pickle', 'rb') as f:
        data2 = [i[2] for i in pickle.load(f)]

    print(data1[:10])
    print(data2[:10])
    data = [data1, data2]
    labels = ['3 servers', '5 servers']
    plt.boxplot(data, labels=labels)

    plt.title(f"Commit latency values for workload")
    plt.xlabel("Count of servers in cluster")
    plt.ylabel("Commit latency distribution on leader (sec)")
    plt.savefig(f'graphs/internal-commit-latency.png')
    plt.clf()


def plot_internal_call_distribution():
    gets, puts = 0, 0
    with open(f'data/3-server-stats-kv-requests.pickle', 'rb') as f:
        v = pickle.load(f)
        gets = len([i for i in v if i[1] == "GET"])
        puts = len([i for i in v if i[1] == "PUT"])

    hbs = 0
    with open(f'data/3-server-stats-raft-requests.pickle', 'rb') as f:
        hbs = len([i for i in pickle.load(f) if i[1] == "Heartbeat"])

    print(gets, puts, hbs)
    values = [gets, puts, hbs]
    labels = ["GET", "PUT", "Heartbeat"]
    plt.pie(values, labels=labels, autopct='%1.1f%%')

    plt.title(f"Distribution of calls in sample workload")
    plt.savefig(f'graphs/internal-call-distribution.png')
    plt.clf()


# filtered_data = smoothen(data, window_size=3, method='mean')
def smoothen_old(data, window_size=5, method='median'):
    if method not in ('mean', 'median'):
        raise ValueError("Method must be either 'mean' or 'median'")

    # Calculate the first quartile (Q1) and third quartile (Q3)
    Q1 = np.percentile(data, 25)
    Q3 = np.percentile(data, 75)

    # Calculate the interquartile range (IQR)
    IQR = Q3 - Q1

    # Define the lower and upper bounds for outliers
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    # Create a copy of the data to store the replaced values
    replaced_data = data.copy()

    # Iterate over the data and replace outliers with the local mean or median
    for i, value in enumerate(data):
        if value < lower_bound or value > upper_bound:
            window_start = max(0, i - window_size // 2)
            window_end = min(len(data), i + window_size // 2 + 1)
            window = data[window_start:window_end]

            if method == 'mean':
                replacement = np.mean(window)
            elif method == 'median':
                replacement = np.median(window)

            replaced_data[i] = replacement

    return replaced_data


def smoothen(y, window_size, order, deriv=0, rate=1):
    import numpy as np
    from math import factorial

    try:
        window_size = np.abs(int(window_size))
        order = np.abs(int(order))
    except ValueError as msg:
        raise ValueError("window_size and order have to be of type int")
    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window_size size must be a positive odd number")
    if window_size < order + 2:
        raise TypeError("window_size is too small for the polynomials order")
    order_range = range(order + 1)
    half_window = (window_size - 1) // 2
    # precompute coefficients
    b = np.mat([[k ** i for i in order_range] for k in range(-half_window, half_window + 1)])
    m = np.linalg.pinv(b).A[deriv] * rate ** deriv * factorial(deriv)
    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - np.abs(y[1:half_window + 1][::-1] - y[0])
    lastvals = y[-1] + np.abs(y[-half_window - 1:-1][::-1] - y[-1])
    y = np.concatenate((firstvals, y, lastvals))
    return np.convolve(m[::-1], y, mode='valid')

def collect_put_lat_thrp_nilext():
    latencies, batch_throughputs = [], []
    for thread_count in range(1, 500, 50):
        restart_cluster()
        batch = []
        print(f"Testing PUT with {thread_count} threads")
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            t1 = time.time()
            future_calls = {executor.submit(
                perf_client.send_put, key, key, True) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result())
            t2 = time.time()
            batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        latencies.append((thread_count, batch))
        
    nilext_latencies, nilext_batch_throughputs = [], []
    for thread_count in range(1, 500, 50):
        restart_cluster()
        batch = []
        print(f"Testing NILEXT PUT with {thread_count} threads")
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            key = f"KEY-{random.randint(1, pow(10, 10))}"
            t1 = time.time()
            future_calls = {executor.submit(
                perf_client.send_put, key, key, False) for _ in range(thread_count)}
            for completed_task in as_completed(future_calls):
                batch.append(completed_task.result())
            t2 = time.time()
            nilext_batch_throughputs.append((thread_count, thread_count / (t2 - t1)))
        nilext_latencies.append((thread_count, batch))

    x, y = zip(*batch_throughputs)
    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-throughputs.pickle', 'wb') as f:
        pickle.dump((x, y), f)

    latencies = [(i[0], np.percentile(i[1], 1), sum(i[1]) /
                  len(i[1]), np.percentile(i[1], 99)) for i in latencies]

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-min-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[1] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-median-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[2] for y in latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-PUT-parallel-max-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[3] for y in latencies]), f)

    # # # Nilext

    x, y = zip(*nilext_batch_throughputs)
    with open(f'data/{NUM_SERVERS}-server-nilext-PUT-parallel-throughputs.pickle', 'wb') as f:
        pickle.dump((x, y), f)

    nilext_latencies = [(i[0], np.percentile(i[1], 1), sum(i[1]) /
                  len(i[1]), np.percentile(i[1], 99)) for i in nilext_latencies]

    with open(f'data/{NUM_SERVERS}-server-nilext-PUT-parallel-min-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[1] for y in nilext_latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-nilext-PUT-parallel-median-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[2] for y in nilext_latencies]), f)

    with open(f'data/{NUM_SERVERS}-server-nilext-PUT-parallel-max-latency.pickle', 'wb') as f:
        pickle.dump((x, [y[3] for y in nilext_latencies]), f)

    print("Done")


if __name__ == "__main__":
    # restart_cluster()
    # collect_get_lat_thrp()
    # # plot_get_latency_3_server()

    # restart_cluster()
    # collect_put_lat_thrp()
    # # plot_put_latency_3_server()

    # restart_cluster()
    # collect_put_lat_thrp_nilext()
    # plot_put_latency_3_server()
    # plot_put_latency_3_server("-nilext")
    # plot_put_throughput_nilext()

    # restart_cluster()
    # collect_put_lat_thrp_nr()
    # # plot_put_latency_3_server_nr()

    # restart_cluster()
    # collect_perf_degradation()

    # restart_cluster()
    # collect_single_thread_throughput()

    # restart_cluster()
    # collect_single_thread_throughput_leader_killed()

    # restart_cluster()
    # collect_log_recovery_time()

    # restart_cluster()
    # collect_internal_server_stats()

    # FOR 5 server only
    # restart_cluster()
    # collect_trpt_with_varying_livenodes()

    # plot_get_latency_3_server()
    # plot_get_latency()
    # plot_get_throughput()
    # plot_put_throughput()
    # plot_put_latency_3_server()
    # plot_put_latency()
    # plot_put_throughput_nr()
    # plot_put_latency_3_server_nr()
    # plot_put_latency_nr()
    # plot_put_degrade_lat()
    # plot_get_degrade_lat()
    # plot_put_degrade_throughput()
    # plot_put_singleT_throughput()
    # plot_put_singleT_leader_killed()

    # plot_log_recovery_time()
    # plot_internal_latency()
    # plot_internal_call_distribution()
    
    
    restart_cluster()
    collect_get_overhead_from_dur_log()

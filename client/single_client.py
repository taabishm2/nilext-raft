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

def nil_ext_put(key, val):
    t1 = time()
    client.send_nil_ext_put(key, val)
    t2 = time()

    return t2 - t1

if __name__ == "__main__":
    lat = []
    time1 = time()
    for i in range(100):
        a = nil_ext_put("1", "1")
        lat.append(a)
    time2 = time()

    latency_stats = [np.median(lat), np.percentile(lat, 99)]
    print("latency stats", latency_stats)
    print("throughput", 100.0 / (time2 - time1))
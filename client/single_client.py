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
    for i in range(20):
        a = nil_ext_put("1", "1")
        lat.append(a)

    latency_stats = [np.median(lat), np.percentile(lat, 99)]
    print(latency_stats)
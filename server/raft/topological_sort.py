import networkx as nx
from time import time

def get_ordered_durability_logs():
    t = time() 
    n = 5000
    e = []
    for i in range(n):
        for j in range(i):
            e.append((i, j))

    # create a directed acyclic graph
    graph = nx.DiGraph()
    graph.add_edges_from(e)

    # perform topological sort
    topological_order = list(nx.topological_sort(graph))

    # print(topological_order)
    dur = time() - t

    return topological_order, dur

_, t = get_ordered_durability_logs()
print(t)
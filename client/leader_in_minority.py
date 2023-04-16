import client
from time import *

def test1():
    # Leader in minority case.
    # 
    # Remove leader node. Observe that PUT fails because of no-consensus.
    # After adding the same node back, it should become a follower.
    # 
    print("======================================================")

    client.send_put("Partition_Key1", "Partition_Val1")
    resp = client.send_get("Partition_Key1")
    print(f"Got key=Partition_Key1, exists?={resp.key_exists}, val={resp.value}")
    print(f"I think the leader is {client.LEADER_NAME}\n\n")

    partitioned_leader = client.LEADER_NAME
    client.send_remove_node(partitioned_leader)

    print(f"\nRemoved leader from cluster, haha.")

    print("\n\n\n")
    sleep(10)

    client.best_effort_put("Partition_Key2", "Partition_Val2")

    print(f"Put key=Partition_Key2, value=Partition_Val2")
    print(f"Hmm, I think, the current leader is {client.LEADER_NAME}")

    print("\n\n\n")
    sleep(10)

    client.send_add_node(partitioned_leader)

    print("\n\n\n")
    sleep(10)

    resp = client.send_get("Partition_Key1")
    print(f"Got key=Partition_Key1, exists?={resp.key_exists}, val={resp.value}")
    resp = client.send_get("Partition_Key2")
    print(f"Got key=Partition_Key2, exists?={resp.key_exists}, val={resp.value}")
    print(f"I think, the current leader is {client.LEADER_NAME}")

    print("Leader in minority parition test done!")
    
    print("\n\n\n")

def test2():
    # Leader in majority.
    # 
    # Remove a follower node. Observe that PUT, GET succeeds.
    # Follower should keep triggering election with no vain.
    # After adding the same node back, it should become a follower.
    # 
    print("======================================================")

    client.send_put("Key3", "Val3")
    client.send_get("Key3")

    print(f"I think, the current leader is {client.LEADER_NAME}")
    follower = client.get_follower()
    print(f"Removing follower {follower}")

    client.send_remove_node(follower)

    print("\n\n\n")
    sleep(10)

    # should succeed.
    client.best_effort_put("Key2", "Val2")
    print(f"I think, the current leader is {client.LEADER_NAME}")

    print("\n\n\n")
    sleep(10)

    # Add the node back.
    # The node should become the leader.
    client.send_add_node(follower)

    print("\n\n\n")
    sleep(10)

    client.send_get("Key2")
    print(f"I think, the current leader is {client.LEADER_NAME}")
    print("\n\n\n")

    print("Leader in majority parition test done!")

    print("======================================================")


if __name__ == '__main__':
    test1()
    # test2()
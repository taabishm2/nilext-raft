import client
from time import *

def durability_test():
    # 
    # Commit is persisted across leader crashes
    # 
    client.send_put("KeyDurable", "ValDurable")
    print(f"PUT key=KeyDurable, value=ValDurable")
    resp = client.send_get("KeyDurable")
    assert resp.key_exists is True, "Written Key{i} not found in db"
    print(f"GOT key=KeyDurable, value={resp.value}")

    print(f"\n\nRemoving the leader node {client.LEADER_NAME} from cluster")
    client.send_remove_node(client.LEADER_NAME)
    
    resp = client.best_effort_get("KeyDurable")
    assert resp.key_exists is True, "Key is not persisted across crash."
    print(f"\n\nGOT key=KeyDurable, value={resp.value}")
    print(f"Durabilty test passed!! :)\n\n")

durability_test()
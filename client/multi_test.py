'''
Simple file that tests functionality of multi-opeartions.
'''

import client
from time import *

def test1():
    # Testing multi-get.
    client.send_put("Multi_Key1", "Val1")
    client.send_put("Multi_Key2", "Val2")
    print("\n\nPerforming multi-get operation\n")
    resp = client.send_mult_get(["Multi_Key1", "Multi_Key2", "Multi_Key3"])
    for v in resp.get_vector:
        print(f"Got key={v.key}, exists?={v.key_exists} value={v.value}")

    # # Testing multi-put.
    print("\nPerforming Multi put operation")
    client.send_multi_put(["Multi_Key8",  "Multi_Key9"], ["Multi_Val8", "Multi_Val9"])
    resp = client.send_mult_get(["Multi_Key8", "Multi_Key9"])
    print("\nPUT Multi_Key8, Multi_Key9 Done")

    print("\nPerforming multi-get operation\n")
    for v in resp.get_vector:
        print(f"Got key={v.key}, exists?={v.key_exists} value={v.value}")
    print("\n\n")

if __name__ == '__main__':
    test1()
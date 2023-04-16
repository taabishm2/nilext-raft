import time
from os import environ
from threading import Thread

from .config import NodeRole, globals
from .utils import *
from .transport import transport
from .log_manager import log_manager
from concurrent.futures import ThreadPoolExecutor, as_completed


class Election:

    def __init__(self):
        # Start a daemon thread to watch for callbacks from leader.
        self.timeout_thread = None
        self.init_heartbeat()
        self.init_timeout()

        # TODO: Need to add a function that triggers the FIRST election.
        # Initially all nodes will start as followers. Wait for one timeout and start election i guess?

    def init_heartbeat(self):
        while True:
            """Initiate periodic heartbeats to the follower nodes if node is leader"""
            if globals.state != NodeRole.Leader: return

            log_me(f"I think i am the leader for {globals.current_term}, sending heartbeats to peers")
            # send heartbeat to follower peers
            for peer in transport.peer_ips:
                Thread(target=self.send_heartbeat, args=(peer,)).start()
            time.sleep(globals.HB_TIME / 1000)

    def send_heartbeat(self, peer: str):
        """SEND heartbeat to the peers and get response if LEADER"""
        # while True:
        try:
            # while globals.state == NodeRole.Leader:
                # start = time.time()
            response = transport.send_heartbeat(peer=peer)
            if response:
                # Peer has higher term. Relinquish leadership
                if response.term > globals.current_term:
                    globals.current_term = response.term
                    globals.state = NodeRole.Follower
                    self.init_timeout()
                    log_me(f'Wait, I got a heart beat from {peer} with term {response.term}, I am gonna step down as leader :(')
                # delta = time.time() - start
                # time.sleep((globals.HB_TIME - delta) / 1000)
            log_me(f'♥ > {peer} {response.is_success} {response.term} 🥹')
        except Exception as e:
            log_me(f'💔 > {peer} Failed: {str(e)} 🥹')
            # time.sleep(globals.HB_TIME * 1.5 / 1000)

    def timeout_loop(self):
        '''
        if this node is not the leader, wait for the leader
        to send the heartbeat. If heartbeat is not received by the follower,
        within some unit time then start the election. This loop will
        run endlessly
        '''
        while globals.state != NodeRole.Leader:
            delta = globals.curr_rand_election_timeout - time.time()
            if delta < 0:
                log_me("Starting an election as heartbeat from leader timed out")
                self.trigger_election()
            else:
                time.sleep(delta)
        log_me("I am elected as leader")

    def init_timeout(self):
        """Checks for missed heartbeats from the leader and start the election"""
        if environ['IS_UNRESPONSIVE'] == "TRUE":
            log_me("Node was configured to be UNRESPONSIVE, will wait before starting timeout loop")
            time.sleep(globals.unresponsive_time)
        try:
            rand_timeout = random_timeout(globals.LOW_TIMEOUT, globals.HIGH_TIMEOUT)
            globals.curr_rand_election_timeout = time.time() + rand_timeout
            if self.timeout_thread and self.timeout_thread.is_alive():
                return
            self.timeout_thread = Thread(target=self.timeout_loop)
            self.timeout_thread.start()
        except Exception as e:
            raise e

    def trigger_election(self):
        if globals.state == NodeRole.Leader: return
        log_me(f"{globals.name} triggered an election with term {globals.current_term + 1}!")
        globals.current_term += 1
        globals.state = NodeRole.Candidate
        globals.voted_for = globals.name
        globals.flush_config_to_disk()

        votes_received = 0
        num_peers = len(transport.peer_ips)
        with ThreadPoolExecutor(max_workers=num_peers) as executor:
            future_rpcs = {executor.submit(self.request_vote, peer) for peer in transport.peer_ips}
            for completed_task in as_completed(future_rpcs):
                try:
                    votes_received += completed_task.result()
                except Exception as exc:
                    log_me(str(exc))
                    # Split vote TODO: check exception is actually timeout before new election
                    # if time.time() - election_start > globals.election_timeout:
                    log_me(f"{globals.name} observed a split vote")
                    time.sleep(random_timeout(globals.LOW_TIMEOUT, globals.HIGH_TIMEOUT))
                    # If someone else became leader in the meantime, exit out
                    if globals.state != NodeRole.Candidate: return
                    self.trigger_election()

        # Got majority votes: become leader
        if votes_received >= num_peers // 2 and globals.state == NodeRole.Candidate:
            globals.state = NodeRole.Leader
            log_me(f"{globals.name} became leader!")
            globals.leader_name = globals.name
            self.init_heartbeat()
        else:
            # If I am not elected, I will try election after sometime.
            log_me("Shoot, I am not elected, I am gonna sleep.")
            rand_timeout = random_timeout(globals.LOW_TIMEOUT, globals.HIGH_TIMEOUT)
            time.sleep(rand_timeout)

    def request_vote(self, peer):
        log_me(f'[Requesting vote from] {peer}')
        response = None
        try:
            response = transport.request_vote(peer=peer)
            if response is not None and response.vote_granted:
                log_me(f"{globals.name} received vote from: {peer}")
            else:
                log_me(f"{globals.name} denied vote by: {peer}")
        except Exception as e:
            log_me(str(e))
            pass
        return response is not None and response.vote_granted

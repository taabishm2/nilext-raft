"""
This file contains the transport class that handles communication
between logs nodes.
"""

import os
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep, time

import grpc
import raft_pb2
import raft_pb2_grpc

from .config import NodeRole, globals, request_vote_rpc_lock

from .log_manager import LogEntry, log_manager
# from .dur_log_manager import dur_log_manager
from .utils import *
from .stats import stats


##################### Helper Utils ##################################

def to_grpc_log_entry(entry: LogEntry):
    log_entry = raft_pb2.LogEntry(
        log_term=int(entry.term),
        command=raft_pb2.WriteCommand(
            key=entry.cmd_key,
            value=entry.cmd_val,
        )
    )

    return log_entry


def from_grpc_log_entry(entry):
    write_command = entry.command
    log_entry = LogEntry(entry.log_term,
                         write_command.key, write_command.value)

    return log_entry


#####################################################################

class RaftProtocolServicer(raft_pb2_grpc.RaftProtocolServicer):

    def AddNode(self, request, context):
        stats.add_raft_request("AddNode")
        log_me(f"Received an add node request for ip: {request.peer_ip}")
        if request.peer_ip == globals.ip_port:
            log_me(f"ERROR: can't add myself duh")
            return raft_pb2.NodeResponse(error="Self-Node add request!")
        if request.peer_ip in transport.peer_ips:
            log_me(f"ERROR: Received add for a node already in cluster")
            return raft_pb2.NodeResponse(error="Node already in cluster!")
        transport.peer_ips.append(request.peer_ip)
        log_me(f"added {request.peer_ip}.....new size= {len(transport.peer_ips)}")
        channel = grpc.insecure_channel(request.peer_ip)
        transport.peer_stubs[request.peer_ip] = raft_pb2_grpc.RaftProtocolStub(channel)

        return raft_pb2.NodeResponse(error="Node added successfully!")

    def RemoveNode(self, request, context):
        stats.add_raft_request("RemoveNode")
        log_me(f"Received a remove node request for ip: {request.peer_ip}")
        if request.peer_ip == globals.ip_port:
            log_me(f"ERROR: can't remove myself duh")
            return raft_pb2.NodeResponse(error="Self-Node remove request!")
        if request.peer_ip not in transport.peer_ips:
            log_me(f"ERROR: Received remove node  {request.peer_ip}. Node not part of cluster")
            return raft_pb2.NodeResponse(error="Node not in cluster!")
        transport.peer_ips.remove(request.peer_ip)
        del transport.peer_stubs[request.peer_ip]
        log_me(f"remove {request.peer_ip}.....new size= {len(transport.peer_ips)}")
        return raft_pb2.NodeResponse(error=f"Node connection to {request.peer_ip} removed successfully from {globals.name}!")

    def RequestVote(self, request, context):
        stats.add_raft_request("RequestVote")
        with request_vote_rpc_lock:
            return self.handle_request_vote(request)

    def handle_request_vote(self, request):
        if self.deny_vote(request):
            log_me(f"Umm, I am not gonna vote for you {request.candidate_id}")
            return raft_pb2.VoteResponse(term=globals.current_term, vote_granted=False)
        if globals.current_term < request.last_log_term:
            globals.state = NodeRole.Follower
        globals.current_term = max(globals.current_term, request.term)
        globals.voted_for = request.candidate_id
        log_me(f"Voted for {request.candidate_id}")

        return raft_pb2.VoteResponse(term=globals.current_term, vote_granted=True)

    def deny_vote(self, request):
        if (f"{request.candidate_id}:4000") not in transport.peer_ips:
            log_me(f"WARN: Received vote request from node {request.candidate_id}:4000 outside the cluster. Denying it!")
            return True
        log_me(f"{request.candidate_id}, {request.term} and {request.last_log_index} wherehas {log_manager.get_latest_term()} and {log_manager.get_last_index()}")
        log_me(f"{request.candidate_id} vote condition 1:{globals.current_term} ==== {request.term} === {globals.current_term > request.term}")
        log_me(f"{request.candidate_id} vote condition 2: {globals.current_term == request.term and globals.voted_for is not None}")
        log_me(f"{request.candidate_id} vote condition 3: log_manager.get_latest_term() {log_manager.get_latest_term()} request.last_log_term== {request.last_log_term} ===== {log_manager.get_latest_term() > request.last_log_term}")
        log_me(f"{request.candidate_id} vote condition 4: log_manager.get_last_index() = {log_manager.get_last_index()} = ={log_manager.get_latest_term() == request.last_log_term and log_manager.get_last_index() > request.last_log_index}")
        return (globals.current_term > request.term or
                globals.current_term == request.term and globals.voted_for is not None or
                log_manager.get_latest_term() > request.last_log_term or
                log_manager.get_latest_term() == request.last_log_term and log_manager.get_last_index() > request.last_log_index)

    def AppendEntries(self, request, context):
        if (f"{request.leader_id}:4000") not in transport.peer_ips:
            log_me(f"WARN: Received AppendEntry/heartbeat from node {request.leader_id} outside the cluster. Ignoring it!")
            return raft_pb2.AEResponse(is_success=False, term=globals.current_term)
        
        if globals.current_term > request.term:
            log_me(f"WARN: Received AppendEntry/heartbeat from a older node {request.leader_id}. Ignoring it!")
            return raft_pb2.AEResponse(is_success=False, term=globals.current_term)
        if not request.is_heart_beat: log_me(f"AppendEntries from {request.leader_id}")

        # TODO: if RPC term is valid, update globals.leader_name and globals.term (in case leadership changed)
        if request.is_heart_beat:
            stats.add_raft_request("Heartbeat")
            self.heartbeat_handler(request=request)
            if request.start_index == -1:
                 # Request is a plain heartbeat and has no log entries to be appended. Send the response.
                return raft_pb2.AEResponse(term=globals.current_term, is_success=True)

        stats.add_raft_request("AppendEntry")
        start_index, prev_term = request.start_index, request.prev_log_term
        log_entries = [from_grpc_log_entry(entry) for entry in request.entries]

        # Try to append entry at given index.
        if not log_manager.overwrite(start_index, log_entries, prev_term):
            log_me(f"AppendEntries request from {request.leader_id} failed")
            return raft_pb2.AEResponse(is_success=False, error="Append Entries overwrite failed")

        # AppendEntries RPC success.
        log_me(f"AppendEntries request success from {request.leader_id}, starting with {request.start_index}")

        # Clear the entry pertaining to this request if present in my durability log
        # dur_log_manager.clear_entry_from_durable_log(request.key, request.value)

        if globals.current_term <= request.term:
            # Update commit index sent by the leader
            globals.commitIndex = request.commit_index
            # Update my term to leader's term
            globals.current_term = max(request.term, globals.current_term)

        return raft_pb2.AEResponse(is_success=True)

    def heartbeat_handler(self, request):
        """
        Handler function for FOLLOWER node to validate heartbeat RECEIVED from leader

        :param request: AERequest req for heartbeat data sent by the leader node
        :returns: term and latest commit_id of this (follower) node
        """
        # TODO: In case this node is a candidate or leader,
        # 1. it should become a follower once again.
        # 2. stop it's previous role duties.
        try:
            term = request.term
            if globals.current_term <= term:
                # Got heartbeat from a leader with valid term
                rand_timeout = random_timeout(globals.LOW_TIMEOUT, globals.HIGH_TIMEOUT)
                globals.curr_rand_election_timeout = time() + rand_timeout
                # Set new leader's name.
                globals.set_leader_name(request.leader_id)
                globals.state = NodeRole.Follower

                # Update my term to leader's term
                globals.current_term = max(term, globals.current_term)
                log_me(f'{globals.leader_name} > ♥, term {globals.current_term} state {globals.state}')

            # return raft_pb2.AEResponse(term=globals.current_term, is_success=True)

        except Exception as e:
            raise e


class Transport:
    def __init__(self):
        self.peer_ips = os.environ['PEER_IPS'].split(",")
        # create a dictionary to store the peer IPs and their stubs
        self.peer_stubs = {ip: raft_pb2_grpc.RaftProtocolStub(grpc.insecure_channel(ip)) for ip in self.peer_ips}
        log_me("Peer stubs initialised!!!")

    def send_heartbeat(self, peer):
        """ If this node is leader, send heartbeat to the follower at address `peer`"""
        peer_stub = self.peer_stubs[peer]
        last_idx = log_manager.get_last_index()
        if last_idx <= 0 or log_manager.get_log_at_index(last_idx) is None:
            request = raft_pb2.AERequest(
                leader_id=globals.name,
                term=globals.current_term,
                start_index=-1,
                is_heart_beat=True)
            response = self.peer_stubs[peer].AppendEntries(request)
        else:
            success, response = self.push_append_entry(peer, last_idx, [log_manager.get_log_at_index(last_idx)], True, globals.current_term)
            # Heart beat doesn't update commitIndex of the leader.

        return response

    # AppendEntries RPC
    def append_entry_to_peers(self, entry, index):
        success_count = 0
        # Use thread pool to submit rpcs to peers.
        num_peers = len(self.peer_stubs)
        with ThreadPoolExecutor(max_workers=num_peers) as executor:
            future_rpcs = {executor.submit(self.push_append_entry, peer, index, [entry], False, globals.current_term) for peer in transport.peer_ips}
            for completed_task in as_completed(future_rpcs):
                try:
                    is_complete, _ = completed_task.result()
                    log_me(f"Response received {completed_task.result()}")
                    success_count += is_complete
                    if success_count >= num_peers // 2:
                        return True
                except Exception as exc:
                    # Unresponsive clients, Internal errors...
                    log_me(f'generated an exception: {exc}')

        log_me(f"AppendEntries RPC success from {success_count} replicas")

        # Return whether append entries is successful on a majority of peers (
        # excluding the leader node).
        return success_count >= num_peers // 2

    def push_append_entry(self, peer_ip, index, entries: list[LogEntry], is_heartbeat=False, curr_term=None):
        if not is_heartbeat: log_me(f"Sending AppendEntry to {peer_ip} with index:{index}")
        # Trivial failure case.
        # TODO: This index <= 0 is incorrect for first log entry
        if index < 0 or len(entries) == 0:
            return 0, raft_pb2.AEResponse(is_success=False, term=globals.current_term)

        prev_index = index - 1
        prev_log_entry = log_manager.get_log_at_index(prev_index)

        # Prepare appendRPC request.
        request = raft_pb2.AERequest(
            term=curr_term,
            leader_id=globals.name,
            start_index=index,
            prev_log_index=prev_index,
            prev_log_term=prev_log_entry.term,
            is_heart_beat=is_heartbeat,
            commit_index=globals.commitIndex
        )

        for entry in entries:
            log_entry_grpc = to_grpc_log_entry(entry)
            request.entries.append(log_entry_grpc)

        # Call appendEntries RPC with 5 second timeout.
        resp = self.peer_stubs[peer_ip].AppendEntries(request, timeout=5)

        if not resp.is_success:
            if resp.term > globals.current_term:
                return 0, raft_pb2.AEResponse(is_success=False, term=resp.term)
            log_me(f"Log mismatch for {peer_ip}, going to index:{index - 1}")
            entries[1:] = entries
            entries[0] = prev_log_entry
            # Retry with updated entries list.
            return self.push_append_entry(peer_ip, index - 1, entries, is_heartbeat, curr_term)

        return 1, resp

    def request_vote(self, peer):
        request = raft_pb2.VoteRequest(term=globals.current_term, candidate_id=globals.name,
                                       last_log_index=log_manager.get_last_index(),
                                       last_log_term=log_manager.get_latest_term())
        response = self.peer_stubs[peer].RequestVote(request, timeout=globals.election_timeout)
        log_me(f"VoteRequest response from {peer} is {response.vote_granted}")
        return response
    
    # def add_node(self, peer)


def from_grpc_log_entry(entry):
    write_command = entry.command
    return LogEntry(entry.log_term, write_command.key, write_command.value)


def main(port=4000):
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))

    servicer = RaftProtocolServicer()
    raft_pb2_grpc.add_RaftProtocolServicer_to_server(servicer, grpc_server)
    grpc_server.add_insecure_port(f'[::]:{port}')

    log_me(f"{globals.name} GRPC server listening on: {port}")
    grpc_server.start()
    grpc_server.wait_for_termination()
    log_me(f"{globals.name} GRPC server terminated")


transport = Transport()

import enum
import pickle
from os import environ, getenv, path, makedirs
from random import randrange
import time
from threading import Lock

from .utils import *

RAFT_BASE_DIR = './logs/logcache'
RAFT_CONFIG_FILE_PATH = RAFT_BASE_DIR + '/config'


class Globals():
    def __init__(self):
        if path.exists(RAFT_CONFIG_FILE_PATH):
            self.load()

            #  As long as we use kv store (without db),
            # we need to set self.lastApplied = 0.
            # TODO: remove it when you use a persistent database.
            self.lastApplied = 0
            self.state = NodeRole.Follower
            self.is_unresponsive = False
            if getenv('IS_UNRESPONSIVE', False) == 'TRUE':
                self.is_unresponsive = True
                self.curr_rand_election_timeout = time.time() + 5
            log_me(f"is_unresponsive? {self.is_unresponsive} {self.curr_rand_election_timeout}")

            self.curr_rand_election_timeout = 0

            log_me(f"My global config is {self.__dict__}")
            return

        # Persistent state on all servers. Updated on stable storage before responding to RPCs
        # TODO: Make these persistent
        self.current_term = 0  # latest term server has seen
        self.voted_for = None  # candidateId that received vote in current term

        # Volatile state on all servers
        self.commitIndex = 0  # index of highest log entry known to be committed
        self.lastApplied = 0  # index of highest log entry applied to state machine

        # Volatile state on leaders. Reinitialized after election
        self.nextIndex = []  # for each server, index of the next log entry to send to that server
        self.matchIndex = []  # for each server, index of highest log entry known to be replicated on server

        # Raft-node state
        self.name = environ['NAME']
        self.ip_port = self.name + f':4000' # The ip_port in which server communicates with raft peers.
        # TODO: Remove this after election is setup.
        self.state = NodeRole.Follower
        if environ['IS_LEADER'] == "TRUE":
            self.state = NodeRole.Leader

        self.is_unresponsive = False

        # Other state
        self.leader_name = None

        self.election_timeout = 150
        self.curr_rand_election_timeout = 0
        # if getenv('IS_UNRESPONSIVE', False) == 'TRUE':
        #     self.is_unresponsive = True
        #     self.curr_rand_election_timeout = time.time() + 5
        # log_me(f"is_unresponsive? {self.is_unresponsive} {self.curr_rand_election_timeout}")

        # Syntax: os.getenv(key, default).
        # Heartbeat timeout T= 250ms. Random timeout in range [T, 2T] unless specified in the env vars
        self.LOW_TIMEOUT = int(getenv('LOW_TIMEOUT', 2000))
        self.HIGH_TIMEOUT = int(getenv('HIGH_TIMEOUT', 4000))
        self.unresponsive_time = self.LOW_TIMEOUT / 2000.0

        # REQUESTS_TIMEOUT = 50
        # Heartbeat is sent every 500ms
        self.HB_TIME = int(getenv('HB_TIME', 500))

        self.heartbeat_retry_limit = 3

        log_me("Global config initialized")

        # MAX_LOG_WAIT = int(getenv('MAX_LOG_WAIT', 150))

    def load(self):
        config_file = open(RAFT_CONFIG_FILE_PATH, 'rb')
        tmp_dict = pickle.load(config_file)
        config_file.close()

        self.__dict__.update(tmp_dict)

    def set_commit_index(self, val):
        log_me(f"Updating commit-index config to: {val}")
        self.commitIndex = val
        self.flush_config_to_disk()

    def set_last_applied(self, val):
        log_me(f"Updating last-applied config to: {val}")
        self.lastApplied = val
        self.flush_config_to_disk()

    def set_leader_name(self, val):
        self.leader_name = val

    def flush_config_to_disk(self):
        config_file = open(RAFT_CONFIG_FILE_PATH, 'wb')
        log_me(f"Persisting {self.__dict__}")
        pickle.dump(self.__dict__, config_file)
        log_me("Finished config dump")
        config_file.close()
        log_me("Closed config file")


class NodeRole(enum.Enum):
    Follower = 1
    Candidate = 2
    Leader = 3


globals = Globals()
request_vote_rpc_lock = Lock()

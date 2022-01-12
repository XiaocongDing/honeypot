from gevent.queue import Queue

from attack_session import AttackSession
from databus import Databus

class SessionManager:
    def __init__(self):
        self._sessions = []
        self._databus = Databus()
        self.log_queue = Queue()
    
    def _find_sessions(self, protocol, source_ip):
        for session in self._sessions:
            if session.protocol == protocol:
                if session.source_ip == source_ip:
                    return session
        return None

    def get_session(self, protocol, source_ip, source_port):
        # around here we would inject dependencies into the attack session
        attack_session = self._find_sessions(protocol, source_ip)
        if not attack_session:
            attack_session = AttackSession(protocol, source_ip, source_port, self._databus, self.log_queue)
            self._sessions.append(attack_session)
        return attack_session

    def get_session_count(self, protocol=None):
        count = 0
        if protocol:
            for session in self._sessions:
                if session.protocol == protocol:
                    count += 1
        else:
            count = len(self._sessions)
        return count

    def purge_session(self):
        self.log_queue = Queue()

    def initialize_databus(self, config_file):
        self._databus.initialize(config_file)
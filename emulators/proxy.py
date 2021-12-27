import logging
from gevent import select
from gevent import socket as _socket
import codecs
import gevent
from gevent.socket import socket
from gevent.ssl import wrap_socket
from gevent.server import StreamServer
import abc
import conpot.core as conpot_core

logger = logging.getLogger(__name__)

class ProxyDecoder(abc.ABC):
    
    @abc.abstractmethod
    def decode_in(self, data):
        """Decode data"""

class Proxy(object):
    def __init__(self, name, proxy_host, proxy_port, decoder=None, keyfile=None, certfile=None):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.name = name
        self.proxy_id = self.name.lower().replace(' ', '_')
        self.host = None
        self.port = None
        self.keyfile = keyfile
        self.certfile = certfile

    def get_server(self, host, port):
        self.host = host
        connection = (host, port)
        if self.keyfile and self.certfile:
            server = StreamServer(connection, self.handle, keyfile = self.keyfile, certfile = self.certfile)
        else:
            server = StreamServer(connection, self.handle)
        return server
    
    def handle(self, sock, address):
        
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
    
    @abc.abstractmethod
    def decode_out(self, data):
        """Decode data that goes out from the proxied device to the connected"""

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
        if decoder:
            try:
                namespace, _classname = decoder.rsplit('.', 1)
                module = __import__(namespace, fromlist = [_classname])
                _class = getattr(module, _classname)
                self.decode = _class()
                assert isinstance(self.decoder, ProxyDecoder)
            except AssertionError:
                logger.fatal('Invalid decoder: decoder an Instance of ProxyDecoder')

    def get_server(self, host, port):
        self.host = host
        connection = (host, port)
        if self.keyfile and self.certfile:
            server = StreamServer(connection, self.handle, keyfile = self.keyfile, certfile = self.certfile)
        else:
            server = StreamServer(connection, self.handle)
        return server
    
    def handle(self, sock, address):
        session = conpot_core.get_session(self.proxy_id, address[0], address[1])
        logger.info(
            'New connection from %s:%s on %s proxy. (%s)',
            address[0], address[1], self.proxy_id, session.id)
        proxy_socket = socket()

        if self.keyfile and self.certfile:
            proxy_socket = wrap_socket(proxy_socket, self.keyfile, self.certfile)

        try:
            proxy_socket.connect((self.proxy_host, self.proxy_port))
        except _socket.error:
            logger.exception('Error while connecting to proxied service at ({}, {})'.format(self.proxy_host,
                             self.proxy_port))
            self._close([proxy_socket, sock])
            return

        sockets = [proxy_socket, sock]
        while len(sockets) == 2:
            gevent.sleep(0)
            sockets_read, _, sockets_err = select.select(sockets, [], sockets, 10)

            if len(sockets_err) > 0:
                self._close([proxy_socket, sock])
                break

            for s in sockets_read:
                socket_close_reason = 'socket closed'
                try:
                    data = s.recv(1024)
                except _socket.error as socket_err:
                    data = []
                    socket_close_reason = str(socket_err)
                if len(data) is 0:
                    self._close([proxy_socket, sock])
                    if s is proxy_socket:
                        logging.warning(
                            'Closing proxied socket while receiving (%s, %s): %s.',
                            self.proxy_host, self.proxy_port, socket_close_reason)
                        sockets = []
                        break
                    elif s is sock:
                        logging.warning(
                            'Closing connection to remote while receiving from remote (%s, %s): %s',
                            socket_close_reason, address[0], address[1])
                        sockets = []
                        break
                    else:
                        assert False

                try:
                    if s is proxy_socket:
                        self.handle_out_data(data, sock, session)
                    elif s is sock:
                        self.handle_in_data(data, proxy_socket, session)
                    else:
                        assert False
                except _socket.error as socket_err:
                    if s is proxy_socket:
                        destination = 'proxied socket'
                    else:
                        destination = 'remote connection'
                    logger.warning('Error while sending data to %s: %s.', destination, str(socket_err))
                    sockets = []
                    break

        session.set_ended()
        proxy_socket.close()
        sock.close()

    def handle_in_data(self, data, sock, session):
        # convert the data from bytes to hex string
        hex_data = codecs.encode(data, 'hex_codec')
        session.add_event({'raw_request': hex_data, 'raw_response': ''})
        logger.debug('Received %s bytes from outside to proxied service: %s', len(data), hex_data)
        if self.decoder:
            # TODO: data could be chunked, proxy needs to handle this
            decoded = self.decoder.decode_in(data)
            logger.debug('Decoded request: %s', decoded)
            session.add_event({'request': decoded, 'raw_response': ''})
        sock.send(data)

    def handle_out_data(self, data, sock, session):
        hex_data = codecs.encode(data, 'hex_codec')
        session.add_event({'raw_request': '', 'raw_response': hex_data})
        logger.debug('Received %s bytes from proxied service: %s', len(data), hex_data)
        if self.decoder:
            # TODO: data could be chunked, proxy needs to handle this
            decoded = self.decoder.decode_out(data)
            logger.debug('Decoded response: %s', decoded)
            session.add_event({'request': '', 'raw_response': decoded})
        sock.send(data)

    def _close(self, sockets):
        for s in sockets:
            s.close()

    def stop(self):
        # TODO: Keep active sockets in list and close them on stop()
        return
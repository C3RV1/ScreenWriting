import dataclasses
import logging
import struct
import threading
import ssl
import typing

from common.EndpointConstructors import EndpointID, EndpointConstructor


@dataclasses.dataclass
class Endpoint:
    callback: typing.Callable
    constructor: type[EndpointConstructor]


class EndpointCallbackSocket:
    def __init__(self, sock: ssl.SSLSocket, on_close: typing.Callable = None):
        self.sock = sock
        self.sock.setblocking(0)
        self.pending_data = b""
        self.endpoints: dict[EndpointID, Endpoint] = {}
        self.on_close: typing.Callable = on_close
        self.sock_lock = threading.RLock()
        self.closed = False

    def set_endpoint(self, endpoint: Endpoint):
        self.endpoints[endpoint.constructor.ENDPOINT_ID] = endpoint

    def remove_endpoint(self, endpoint_constructor: type[EndpointConstructor]):
        self.endpoints.pop(endpoint_constructor.ENDPOINT_ID, None)

    def continuous_recv(self, size) -> bytes:
        data = self.pending_data
        while len(data) < size and not self.closed:
            data += self.sock.recv(4096)
        self.pending_data = data[size:]
        return data[:size]

    def throw_recv(self, size) -> None:
        while size > len(self.pending_data):
            try:
                self.pending_data += self.sock.recv(4096)
            except ssl.SSLWantReadError:
                pass
        self.pending_data = self.pending_data[size:]

    def waiting_header(self) -> bool:
        try:
            data = self.sock.recv(8)
            self.pending_data += data
            if len(data) == 0:
                return False
        except ssl.SSLWantReadError:
            return False
        except OSError:
            self.close()
            return False
        return len(self.pending_data) >= 8

    def do_receive(self):
        with self.sock_lock:
            if self.closed:
                return
            if not self.waiting_header():
                return
            try:
                msg_header = self.continuous_recv(8)
                endpoint_id, msg_size = struct.unpack("!II", msg_header)
                if endpoint_id not in self.endpoints:
                    logging.warning(f"Endpoint {endpoint_id} not found.")
                    self.throw_recv(msg_size)
                    return

                endpoint = self.endpoints[endpoint_id]
                if msg_size > endpoint.constructor.MAX_DATA_SIZE > -1:
                    logging.warning(f"Exceeded endpoint {endpoint_id} size ({msg_size}, "
                                    f"max {endpoint.constructor.MAX_DATA_SIZE})")
                    self.throw_recv(msg_size)
                    return

                msg = self.continuous_recv(msg_size)
                endpoint_constructed = endpoint.constructor.from_msg(msg)
                if endpoint_constructed is not None:
                    endpoint.callback(endpoint_constructed)
                else:
                    logging.warning(f"Endpoint {endpoint} couldn't be parsed.")
            except Exception:
                logging.exception("Exception while performing receive.")
                self.close()

    def send_endp(self, constructed: EndpointConstructor):
        if self.closed:
            return
        with self.sock_lock:
            try:
                msg = constructed.to_bytes()
                msg_header = struct.pack("!II", constructed.ENDPOINT_ID, len(msg))
                self.sock.sendall(msg_header + msg)
            except Exception:
                logging.exception("Exception while sending to endpoint.")
                self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        with self.sock_lock:
            self.sock.close()
            if self.on_close:
                self.on_close()

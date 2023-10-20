import dataclasses
import logging
import socket
import struct
import threading

import select
import ssl
import typing

from common.EndpointID import EndpointID


@dataclasses.dataclass
class Endpoint:
    callback: typing.Callable
    max_data_size: int = 4096


class EndpointCallbackSocket:
    def __init__(self, sock: ssl.SSLSocket, on_close: typing.Callable = None):
        self.sock = sock
        self.sock.setblocking(0)
        self.pending_data = b""
        self.endpoints: dict[EndpointID, Endpoint] = {}
        self.on_close: typing.Callable = on_close
        self.sock_lock = threading.Lock()
        self.closed = False

    def set_endpoint(self, endpoint_id: EndpointID, endpoint: Endpoint):
        self.endpoints[endpoint_id] = endpoint

    def remove_endpoint(self, endpoint_id: EndpointID):
        self.endpoints.pop(endpoint_id, None)

    def continuous_recv(self, size) -> bytes:
        data = self.pending_data
        while len(data) < size and not self.closed:
            data += self.sock.recv(4096)
        self.pending_data = data[size:]
        return data[:size]

    def throw_recv(self, size) -> None:
        while size > len(self.pending_data):
            self.pending_data = self.sock.recv(4096)
            size -= len(self.pending_data)
        self.pending_data = self.pending_data[size:]

    def waiting_header(self) -> bool:
        try:
            data = self.sock.recv(8)
            self.pending_data += data
            if len(data) == 0:
                self.close()
                return False
        except ssl.SSLWantReadError:
            return False
        except OSError:
            self.close()
            return False
        return len(self.pending_data) >= 8

    def do_receive(self):
        try:
            if self.closed:
                return
            if not self.waiting_header():
                return
            self.sock_lock.acquire()
            msg_header = self.continuous_recv(8)
            endpoint_id, msg_size = struct.unpack("II", msg_header)
            if endpoint_id not in self.endpoints:
                logging.warning(f"Endpoint {endpoint_id} not found.")
                self.throw_recv(msg_size)
                self.sock_lock.release()
                print("RELEASED")
                return

            endpoint = self.endpoints[endpoint_id]
            if msg_size > endpoint.max_data_size > -1:
                logging.warning(f"Exceeded endpoint {endpoint_id} size ({msg_size}, max {endpoint.max_data_size})")
                self.throw_recv(msg_size)
                self.sock_lock.release()
                print("RELEASED")
                return

            msg = self.continuous_recv(msg_size)
            self.sock_lock.release()
            print("RELEASED")
            print("Handling endpoint")
            endpoint.callback(msg)
        except Exception:
            logging.exception("Disconnected?")
            if self.sock_lock.locked():
                self.sock_lock.release()
            self.close()

    def do_send(self, endpoint_id: EndpointID, msg: bytes = b""):
        if self.closed:
            return
        self.sock_lock.acquire()
        try:
            msg_header = struct.pack("II", endpoint_id, len(msg))
            self.sock.sendall(msg_header + msg)
            self.sock_lock.release()
        except Exception:
            logging.exception("Disconnected?")
            self.sock_lock.release()
            self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.sock.close()
        print("CLOSING")
        if self.on_close:
            self.on_close()

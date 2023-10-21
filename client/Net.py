import ssl
import os
from client.Config import ClientConfig
import base64
import socket
import typing

from common.EndpointConstructors import *
from common.EndpointCallbackSocket import EndpointCallbackSocket


class Net:
    def __init__(self):
        self.ssl_context: typing.Optional[ssl.SSLContext] = None
        self.sock: typing.Optional[EndpointCallbackSocket] = None

    def connect_to_server(self, hostname: str, confirm_trust: typing.Callable):
        hostname_b64 = base64.urlsafe_b64encode(hostname.encode("ascii")).decode("ascii")
        hostname_cert_path = os.path.join(ClientConfig.crt_folder_path, hostname_b64 + ".pem")
        new_host = False

        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if os.path.isfile(hostname_cert_path):
            self.ssl_context.load_verify_locations(hostname_cert_path)
            self.ssl_context.check_hostname = True
            self.ssl_context.verify_mode = ssl.CERT_REQUIRED
        else:
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
            new_host = True

        sock = ssl.wrap_socket(socket.socket(socket.AF_INET))
        try:
            sock.connect((hostname, ClientConfig.CONNECT_PORT))
        except TimeoutError:
            return False

        self.sock = EndpointCallbackSocket(sock)

        if new_host:
            trusted = False
            if confirm_trust:
                trusted = confirm_trust(hostname)
            if not trusted:
                self.sock.send_endp(Close())
                self.sock.close()
                return False
            der_cert = sock.getpeercert(binary_form=True)
            pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
            try:
                os.mkdir(os.path.dirname(hostname_cert_path))
            except FileExistsError:
                pass
            with open(hostname_cert_path, "w") as f:
                f.write(pem_cert)
        return True

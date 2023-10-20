import datetime
import hashlib
import io
import logging
import ssl
import struct
import threading
import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server import Net
from common.EndpointCallbackSocket import EndpointCallbackSocket, Endpoint
from common.EndpointID import *
from common.User import User
from server.ServerProject import ServerProject, Folder


class ClientHandler(threading.Thread):
    def __init__(self, sock: ssl.SSLSocket, sock_addr, master: 'Net'):
        super().__init__()
        self.sock = EndpointCallbackSocket(sock, on_close=self.close)
        self.setup_initial_endpoints()
        self.sock_addr = sock_addr
        self.master: 'Net' = master

        self.user = None
        self.open_project: typing.Optional[ServerProject] = None
        self.open_real_time_documents = {}

        self.exit_flag = threading.Event()

        self.last_alive = datetime.datetime.now(datetime.timezone.utc)

    def check_alive(self):
        if datetime.datetime.now(datetime.timezone.utc) - self.last_alive > datetime.timedelta(seconds=7):
            self.close()
            return
        self.sock.send_endp(AreYouAlive())

    def confirmed_alive(self, _msg):
        self.last_alive = datetime.datetime.now(datetime.timezone.utc)

    def setup_initial_endpoints(self):
        self.sock.set_endpoint(Endpoint(self.close, Close))
        self.sock.set_endpoint(Endpoint(self.confirmed_alive, IAmAlive))
        self.sock.set_endpoint(Endpoint(self.ping, Ping))
        self.sock.set_endpoint(Endpoint(self.login, LoginRequest))

    def setup_endpoints_logged_in(self):
        self.sock.remove_endpoint(LoginResult)
        self.sock.set_endpoint(Endpoint(self.create_project, CreateProject))
        self.sock.set_endpoint(Endpoint(self.delete_project, DeleteProject))
        self.sock.set_endpoint(Endpoint(self.rename_project, RenameProject))

    def login(self, login_request: LoginRequest):
        user = User()
        if not user.load_from_database(self.master.database, login_request.username):
            self.sock.send_endp(LoginResult(LoginErrorCode.INVALID_CREDENTIALS, []))
            return

        entered_hash = hashlib.sha256(user.password_salt + login_request.password).hexdigest()
        if entered_hash != user.password_hash:
            self.sock.send_endp(LoginResult(LoginErrorCode.INVALID_CREDENTIALS, []))
            return

        self.user = user
        self.setup_endpoints_logged_in()

        project_names: list[tuple[str, str]] = self.master.get_project_list()
        self.sock.send_endp(LoginResult(LoginErrorCode.SUCCESSFUL, project_names))

    def send_server_wide_error(self, explanation: str):
        explanation = explanation.encode("utf-8")
        msg = struct.pack("H", len(explanation)) + explanation
        self.sock.send_endp(EndpointID.ERROR_FULFILLING_SERVER_REQUEST, msg)

    def create_project(self, msg: CreateProject):
        if len(msg.name) > self.master.config.MAX_PROJECT_NAME_LENGTH:
            self.sock.send_endp(ServerScopeRequestError("Project name too long."))
            return

        if ServerProject.exists_project(self.master.database, msg.name):
            self.sock.send_endp(ServerScopeRequestError("Project already exists."))
            return

        project = ServerProject(msg.name, Folder.new(), {})
        project.save_to_database(self.master.database)
        self.master.broadcast_created_project(project)

    def delete_project(self, msg: DeleteProject):
        project = self.master.get_project_by_id(msg.id)
        if project is None:
            self.sock.send_endp(ServerScopeRequestError("Project doesn't exist."))
            return
        self.master.remove_project(project)

    def rename_project(self, msg: RenameProject):
        if msg.new_name > self.master.config.MAX_PROJECT_NAME_LENGTH:
            self.sock.send_endp(ServerScopeRequestError("Project name too long."))
            return

        project = self.master.get_project_by_id(msg.id)
        if project is None:
            self.sock.send_endp(ServerScopeRequestError("Project doesn't exist."))
            return

        project.name = msg.new_name
        self.master.broadcast_rename_project(project)

    def ping(self, _data: bytes):
        print(f"Client {self.sock_addr} sent a ping!")
        self.sock.send_endp(Pong())

    def run(self) -> None:
        while not self.exit_flag.is_set():
            self.sock.do_receive()
        self.close()

    def close(self, _msg=b""):
        self.sock.send_endp(Close())
        self.sock.close()
        self.exit_flag.set()
        self.master.close_client(self)

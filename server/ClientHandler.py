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
        self.sock.do_send(EndpointID.ARE_U_ALIVE, AreYouAlive())

    def confirmed_alive(self, _msg):
        self.last_alive = datetime.datetime.now(datetime.timezone.utc)

    def setup_initial_endpoints(self):
        self.sock.set_endpoint(
            EndpointID.CLOSE, Endpoint(self.close, Close, max_data_size=0)
        )
        self.sock.set_endpoint(
            EndpointID.I_AM_ALIVE, Endpoint(self.confirmed_alive, IAmAlive, max_data_size=0)
        )
        self.sock.set_endpoint(
            EndpointID.PING, Endpoint(self.ping, Ping, max_data_size=0)
        )
        self.sock.set_endpoint(
            EndpointID.LOGIN, Endpoint(self.login, LoginRequest, max_data_size=128)
        )

    def setup_endpoints_logged_in(self):
        self.sock.remove_endpoint(EndpointID.LOGIN_RESULT)
        self.sock.set_endpoint(
            EndpointID.CREATE_PROJECT,
            Endpoint(self.create_project, max_data_size=128)
        )
        self.sock.set_endpoint(
            EndpointID.DELETE_PROJECT,
            Endpoint(self.delete_project, max_data_size=24)
        )
        self.sock.set_endpoint(
            EndpointID.DELETE_PROJECT,
            Endpoint(self.rename_project, max_data_size=128)
        )

    def login(self, login_request: LoginRequest):
        user = User()
        if not user.load_from_database(self.master.database, login_request.username):
            self.sock.do_send(EndpointID.LOGIN_RESULT, LoginResult(LoginErrorCode.INVALID_CREDENTIALS))
            return

        entered_hash = hashlib.sha256(user.password_salt + login_request.password).hexdigest()
        if entered_hash != user.password_hash:
            self.sock.do_send(EndpointID.LOGIN_RESULT, LoginResult(LoginErrorCode.INVALID_CREDENTIALS))
            return

        self.user = user
        self.setup_endpoints_logged_in()

        error_code = LoginErrorCode.SUCCESSFUL
        project_names: list[tuple[str, str]] = self.master.get_project_list()
        msg = struct.pack("BB", error_code, len(project_names))
        for project_name, project_id in project_names:
            encoded_project_name = project_name.encode("utf-8")
            msg += struct.pack("B", len(encoded_project_name)) + encoded_project_name
            msg += project_id.encode("ascii")  # 24 hex characters

        self.sock.do_send(EndpointID.LOGIN_RESULT, msg)

    def send_server_wide_error(self, explanation: str):
        explanation = explanation.encode("utf-8")
        msg = struct.pack("H", len(explanation)) + explanation
        self.sock.do_send(EndpointID.ERROR_FULFILLING_SERVER_REQUEST, msg)

    def create_project(self, msg: bytes):
        if len(msg) < 1:
            self.send_server_wide_error("Bad create project request.")
            return
        rdr = io.BytesIO(msg)
        project_name_length = struct.unpack("B", rdr.read(1))[0]
        if project_name_length > self.master.config.MAX_PROJECT_NAME_LENGTH:
            self.send_server_wide_error("Project name too long.")
            return
        if len(msg) != 1 + project_name_length:
            self.send_server_wide_error("Bad create project request.")
            return
        project_name = rdr.read(project_name_length).decode("utf-8")

        if ServerProject.exists_project(self.master.database, project_name):
            self.send_server_wide_error("Project already exists.")
            return

        project = ServerProject(project_name, Folder.new(), {}, self.master.config)
        project.save_to_database(self.master.database)
        self.master.broadcast_created_project(project)

    def delete_project(self, msg: bytes):
        if len(msg) < 24:
            self.send_server_wide_error("Bad delete project request.")
            return
        rdr = io.BytesIO(msg)
        project_id = rdr.read(24).decode("ascii")

        project = self.master.get_project_by_id(project_id)

        if project is None:
            self.send_server_wide_error("Project doesn't exist.")
            return

        self.master.remove_project(project)

    def rename_project(self, msg: bytes):
        if len(msg) < 25:
            self.send_server_wide_error("Bad rename project request.")
            return
        rdr = io.BytesIO(msg)
        project_id = rdr.read(24).decode("ascii")
        new_name_length = struct.unpack("B", rdr.read(1))[0]
        if new_name_length > self.master.config.MAX_PROJECT_NAME_LENGTH:
            self.send_server_wide_error("Project name too long.")
            return
        if len(msg) != 25 + new_name_length:
            self.send_server_wide_error("Bad rename project request.")
            return
        new_name = rdr.read(new_name_length).decode("utf-8")

        project = self.master.get_project_by_id(project_id)

        if project is None:
            self.send_server_wide_error("Project doesn't exist.")
            return

        project.name = new_name
        self.master.broadcast_rename_project(project)

    def ping(self, _data: bytes):
        print(f"Client {self.sock_addr} sent a ping!")
        self.sock.do_send(EndpointID.PONG, Pong())

    def run(self) -> None:
        while not self.exit_flag.is_set():
            self.sock.do_receive()
        self.close()

    def close(self, _msg=b""):
        self.sock.do_send(EndpointID.CLOSE, Close())
        self.sock.close()
        self.exit_flag.set()
        self.master.close_client(self)

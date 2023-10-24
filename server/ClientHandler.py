import datetime
import hashlib
import ssl
import threading
import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server import Net
from common.EndpointCallbackSocket import EndpointCallbackSocket, Endpoint
from common.LoginEndpoints import *
from common.ServerEndpoints import *
from common.ProjectEndpoints import *
from common.ScriptEndpoints import *
from server.ServerUser import ServerUser
from server.ServerProject import ServerProject, Folder
from server.Config import ServerConfig
from server.RealTimeDocument import RealTimeUser


class ClientHandler(threading.Thread):
    def __init__(self, sock: ssl.SSLSocket, sock_addr, master: 'Net.Net'):
        super().__init__()
        self.sock = EndpointCallbackSocket(sock, on_close=self.close)
        self.setup_initial_endpoints()
        self.sock_addr = sock_addr
        self.master: 'Net.Net' = master

        self.user = None
        self.current_project: typing.Optional[ServerProject] = None
        self.current_real_time_users: dict[str, RealTimeUser] = {}

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
        self.sock.remove_endpoint(LoginRequest)
        self.sock.set_endpoint(Endpoint(self.create_project, CreateProject))
        self.sock.set_endpoint(Endpoint(self.delete_project, DeleteProject))
        self.sock.set_endpoint(Endpoint(self.rename_project, RenameProject))
        self.sock.set_endpoint(Endpoint(self.open_project, OpenProject))

    def setup_endpoints_opened_project(self):
        self.sock.remove_endpoint(CreateProject)
        self.sock.remove_endpoint(DeleteProject)
        self.sock.remove_endpoint(RenameProject)
        self.sock.remove_endpoint(OpenProject)

        self.sock.set_endpoint(Endpoint(self.join_document, JoinDoc))
        self.sock.set_endpoint(Endpoint(self.patch_script, PatchScript))

    def login(self, login_request: LoginRequest):
        user = ServerUser.load_from_database(self.master.database, login_request.username)
        if user is None:
            self.sock.send_endp(LoginResult(LoginErrorCode.INVALID_CREDENTIALS, [], None))
            return

        entered_hash = hashlib.sha256(user.password_salt + login_request.password).hexdigest()
        if entered_hash != user.password_hash:
            self.sock.send_endp(LoginResult(LoginErrorCode.INVALID_CREDENTIALS, [], None))
            return

        self.user = user
        self.setup_endpoints_logged_in()

        project_names: list[tuple[str, str]] = self.master.get_project_list()
        self.sock.send_endp(LoginResult(LoginErrorCode.SUCCESSFUL, project_names, user))

    def create_project(self, msg: CreateProject):
        if len(msg.name) > ServerConfig.MAX_PROJECT_NAME_LENGTH:
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
        if len(msg.name) > ServerConfig.MAX_PROJECT_NAME_LENGTH:
            self.sock.send_endp(ServerScopeRequestError("Project name too long."))
            return

        project = self.master.get_project_by_id(msg.id)
        if project is None:
            self.sock.send_endp(ServerScopeRequestError("Project doesn't exist."))
            return

        project.name = msg.name
        self.master.broadcast_rename_project(project)

    def open_project(self, msg: OpenProject):
        project = self.master.open_project_by_id(msg.id, self)

        if project is None:
            self.sock.send_endp(ServerScopeRequestError("Project couldn't be opened."))
            return

        self.current_project = project
        self.sock.send_endp(SyncProject(project, [c.user for c in project.opened_users]))
        self.setup_endpoints_opened_project()

    def join_document(self, msg: JoinDoc):
        if msg.id in self.current_real_time_users:
            self.sock.send_endp(ProjectScopeRequestError("Document already open."))
            return

        open_rtu = self.master.open_realtime_document_by_id(self, msg.id)
        if open_rtu is None:
            self.sock.send_endp(ProjectScopeRequestError("Error opening realtime document."))
            return

        self.current_real_time_users[open_rtu.rtd.file_id] = open_rtu

    def patch_script(self, msg: PatchScript):
        print("Got patch from client!")
        if msg.document_id not in self.current_real_time_users:
            self.sock.send_endp(ScriptScopeRequestError("Document not opened."))
            return

        open_rtu = self.current_real_time_users[msg.document_id]
        open_rtu.uploaded_patch(msg.patch, msg.branch_id, msg.document_timestamp)

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

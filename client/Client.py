import threading
from typing import Optional

from client.Net import Net
from client.gui.LoginForm import LoginForm
from client.gui.ProjectOpener import ProjectOpener
from client.gui.ProjectCreator import ProjectCreator
from PySide6 import QtWidgets, QtCore
from common.EndpointCallbackSocket import Endpoint
from common.EndpointConstructors import *
import qdarktheme


def confirm_trusted(hostname):
    trusted = QtWidgets.QMessageBox.question(
        None,
        "Trust Server?",
        "It seems it's the first time you connect to "
        f"{hostname}. Do you trust this site?\n"
        f"\n"
        f"If you click Yes, the certificate will be saved "
        f"so that you don't have to answer this question again."
    )
    return trusted == QtWidgets.QMessageBox.StandardButton.Yes


class ClientState(enum.Enum):
    BOOT = 0
    LOGGING_IN = 1
    OPENING_PROJECT = 2
    CREATING_PROJECT = 3


class Client:
    def __init__(self):
        super().__init__()
        self.net = Net()
        self.running = True
        self.recv_timer = QtCore.QTimer()
        self.recv_timer.setInterval(100)
        qdarktheme.setup_theme('dark')

        self.login_form: Optional[LoginForm] = None
        self.project_opener: Optional[ProjectOpener] = None
        self.project_creator: Optional[ProjectCreator] = None
        self.logged_in_user: Optional[User] = None

        self.state = ClientState.BOOT

        self.project_list = {}

    def alive_endpoint(self, _msg: AreYouAlive):
        self.net.sock.send_endp(IAmAlive())

    def close_endpoint(self, _msg: Close):
        self.running = False

    def login_response(self, login_result: LoginResult):
        self.net.sock.remove_endpoint(LoginResult)
        if login_result.error_code == LoginErrorCode.INVALID_CREDENTIALS:
            QtWidgets.QMessageBox.critical(
                self.login_form,
                "Invalid credentials",
                "The credentials entered where invalid."
            )
            return
        elif login_result.error_code != LoginErrorCode.SUCCESSFUL:
            QtWidgets.QMessageBox.critical(
                self.login_form,
                "Error logging in",
                f"The server returned error code {login_result.error_code}."
            )
            return
        self.logged_in_user = login_result.user
        self.project_list = {}
        for project_name, project_id in login_result.project_list:
            self.project_list[project_id] = project_name
        self.net.sock.set_endpoint(Endpoint(self.created_project, CreatedProject))
        self.net.sock.set_endpoint(Endpoint(self.deleted_project, DeletedProject))
        self.net.sock.set_endpoint(Endpoint(self.renamed_project, RenamedProject))
        self.net.sock.set_endpoint(Endpoint(self.server_scope_request_error, ServerScopeRequestError))
        self.enter_state(ClientState.OPENING_PROJECT)

    def do_login(self):
        username = self.login_form.username_input.text()
        password = self.login_form.password_input.text()
        self.net.sock.send_endp(LoginRequest(username, password.encode("utf-8")))

    def run(self, hostname):
        if not self.net.connect_to_server(hostname, confirm_trusted):
            QtWidgets.QMessageBox.critical(
                None,
                "Couldn't connect to server.",
                f"It was impossible to connect to to the host {hostname}."
            )
            return
        self.recv_timer.timeout.connect(self.net.sock.do_receive)
        self.recv_timer.start()
        self.enter_state(ClientState.LOGGING_IN)

    def server_scope_request_error(self, msg: ServerScopeRequestError):
        QtWidgets.QMessageBox.critical(
            None,
            "Error!",
            msg.message
        )

    def created_project(self, msg: CreatedProject):
        self.project_list[msg.id] = msg.name
        if self.project_opener:
            self.project_opener.add_project(msg.name, msg.id)

    def deleted_project(self, msg: DeletedProject):
        self.project_list.pop(msg.id)
        if self.project_opener:
            self.project_opener.remove_project(msg.id)

    def renamed_project(self, msg: RenamedProject):
        self.project_list[msg.id] = msg.name
        if self.project_opener:
            self.project_opener.rename_project(msg.id, msg.name)

    def open_project_creator(self):
        self.enter_state(ClientState.CREATING_PROJECT)

    def create_project(self):
        project_name = self.project_creator.project_name.text()
        self.net.sock.send_endp(CreateProject(project_name))
        self.enter_state(ClientState.OPENING_PROJECT)

    def remove_project(self, id_):
        self.net.sock.send_endp(DeleteProject(id_))

    def rename_project(self, id_, new_name):
        self.net.sock.send_endp(RenameProject(id_, new_name))

    def enter_state(self, state: ClientState):
        self.leave_state()
        self.state = state
        if self.state == ClientState.LOGGING_IN:
            self.net.sock.set_endpoint(Endpoint(self.close_endpoint, Close))
            self.net.sock.set_endpoint(Endpoint(self.alive_endpoint, AreYouAlive))
            self.net.sock.set_endpoint(Endpoint(self.login_response, LoginResult))
            self.login_form = LoginForm(self.do_login)
            self.login_form.show()
        elif self.state == ClientState.OPENING_PROJECT:
            if self.project_opener is None:
                self.project_opener = ProjectOpener(self.logged_in_user, self.open_project_creator,
                                                    self.remove_project, self.rename_project,
                                                    self.project_list)
            if self.project_opener.isHidden():
                self.project_opener.show()
        elif self.state == ClientState.CREATING_PROJECT:
            self.project_creator = ProjectCreator(lambda: self.enter_state(ClientState.OPENING_PROJECT),
                                                  self.create_project)
            self.project_creator.show()

    def leave_state(self):
        if self.state == ClientState.LOGGING_IN:
            self.net.sock.remove_endpoint(LoginResult)
            self.login_form.deleteLater()
        elif self.state == ClientState.CREATING_PROJECT:
            self.project_creator.deleteLater()

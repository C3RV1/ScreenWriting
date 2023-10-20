import threading

from client.Net import Net
from client.gui.LoginForm import LoginForm
from PySide6 import QtWidgets
from common.EndpointCallbackSocket import Endpoint
from common.EndpointID import *
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


class Client:
    def __init__(self):
        super().__init__()
        self.net = Net()
        self.running = True
        self.recv_thread = None
        qdarktheme.setup_theme('dark')

        self.login_form: LoginForm = LoginForm(self.do_login)

    def alive_endpoint(self, _msg: AreYouAlive):
        self.net.sock.send_endp(IAmAlive())

    def close_endpoint(self, _msg: Close):
        self.running = False

    def socket_thread(self):
        while self.running:
            self.net.sock.do_receive()

    def do_login(self):
        def login_response(login_result: LoginResult):
            self.net.sock.remove_endpoint(LoginResult)
            print(login_result.error_code)

        username = self.login_form.username_input.text()
        password = self.login_form.password_input.text()
        self.net.sock.set_endpoint(Endpoint(login_response, LoginResult))
        self.net.sock.send_endp(LoginRequest(username, password))

    def run(self, hostname):
        if not self.net.connect_to_server(hostname, confirm_trusted):
            QtWidgets.QMessageBox.critical(
                None,
                "Couldn't connect to server.",
                f"It was impossible to connect to to the host {hostname}."
            )
            return

        self.recv_thread = threading.Thread(target=self.socket_thread)
        self.recv_thread.start()

        self.net.sock.set_endpoint(Endpoint(self.close_endpoint, Close))
        self.net.sock.set_endpoint(Endpoint(self.alive_endpoint, AreYouAlive))
        self.login_form.show()

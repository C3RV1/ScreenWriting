from PySide6 import QtWidgets


class LoginForm(QtWidgets.QWidget):
    def __init__(self, on_submit):
        super().__init__()
        self.setWindowTitle("Login to Screenwriter")
        self.form_layout = QtWidgets.QFormLayout()
        self.setLayout(self.form_layout)

        self.username_input = QtWidgets.QLineEdit()
        self.form_layout.addRow("Username", self.username_input)

        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(self.password_input.EchoMode.Password)
        self.form_layout.addRow("Password", self.password_input)

        self.submit_button = QtWidgets.QPushButton("Login")
        self.submit_button.clicked.connect(on_submit)
        self.form_layout.addRow(self.submit_button)

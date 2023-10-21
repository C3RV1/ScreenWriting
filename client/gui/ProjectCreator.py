from PySide6 import QtWidgets, QtGui


class ProjectCreator(QtWidgets.QWidget):
    def __init__(self, on_close, on_create):
        super().__init__()
        self.on_close = on_close

        self.form_layout = QtWidgets.QFormLayout()
        self.setLayout(self.form_layout)

        self.title = QtWidgets.QLabel("Create Project")
        self.title.font().setPointSize(32)
        self.form_layout.addRow(self.title)

        self.project_name = QtWidgets.QLineEdit()
        self.form_layout.addRow("Project Name", self.project_name)

        self.create_button = QtWidgets.QPushButton("Create")
        self.create_button.clicked.connect(on_create)
        self.form_layout.addRow(self.create_button)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        super().closeEvent(event)
        if self.on_close:
            self.on_close()

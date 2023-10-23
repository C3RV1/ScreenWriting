from PySide6 import QtWidgets, QtGui, QtCore
from common.User import User


class ProjectRename(QtWidgets.QWidget):
    def __init__(self, id_, on_rename):
        super().__init__()
        self.id_ = id_
        self.on_rename = on_rename

        self.form_layout = QtWidgets.QFormLayout()
        self.setLayout(self.form_layout)

        self.new_name = QtWidgets.QLineEdit()
        self.form_layout.addRow("New Name", self.new_name)

        self.submit_button = QtWidgets.QPushButton("Rename")
        self.submit_button.clicked.connect(self.do_rename)
        self.form_layout.addRow(self.submit_button)

    def do_rename(self):
        self.on_rename(self.id_, self.new_name.text())


class ProjectInList(QtWidgets.QWidget):
    EDIT_ICON = None

    def __init__(self, parent, name, id_, on_remove, on_rename, on_open):
        super().__init__(parent)

        self.id_ = id_
        self.on_remove = on_remove
        self.on_rename = on_rename
        self.on_open = on_open

        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)

        self.project_name = QtWidgets.QLabel(name, parent=self)
        self.h_layout.addWidget(self.project_name)

        if ProjectInList.EDIT_ICON is None:
            palette = self.palette()
            create_icon = QtGui.QPixmap("client/icons/edit.svg")
            mask = create_icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
            create_icon.fill(palette.light().color())
            create_icon.setMask(mask)
            ProjectInList.EDIT_ICON = QtGui.QIcon(create_icon)

        self.rename_project = QtWidgets.QPushButton(parent=self)
        self.rename_project.clicked.connect(self.do_rename)
        self.rename_project.setIcon(ProjectInList.EDIT_ICON)
        self.h_layout.addWidget(self.rename_project)

        self.h_layout.addStretch()

        self.open_project = QtWidgets.QPushButton("Open", parent=self)
        self.open_project.clicked.connect(self.do_open)
        self.h_layout.addWidget(self.open_project)

        self.delete_project = QtWidgets.QPushButton(parent=self)
        self.delete_project.clicked.connect(self.do_remove)
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogDiscardButton)
        self.delete_project.setIcon(icon)
        self.h_layout.addWidget(self.delete_project)

        self.project_renamer = None

    def do_rename(self):
        self.project_renamer = ProjectRename(self.id_, self.on_rename)
        self.project_renamer.show()

    def do_remove(self):
        are_you_sure = QtWidgets.QMessageBox.question(
            self, "Remove project?",
            "Are you sure you want to remove this project entirely? This action cannot be undone."
        )
        if are_you_sure != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.on_remove(self.id_)

    def do_open(self):
        self.on_open(self.id_)


class ProjectOpener(QtWidgets.QWidget):
    def __init__(self, user: User, on_create, on_remove, on_rename, on_open, project_list: dict[str, str]):
        super().__init__()
        self.setWindowTitle("Projects")
        self.on_remove = on_remove
        self.on_rename = on_rename
        self.on_open = on_open

        self.v_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.v_layout)

        self.top_layout = QtWidgets.QHBoxLayout()
        self.v_layout.addLayout(self.top_layout)

        self.user_visible_name = QtWidgets.QLabel(user.visible_name)
        self.user_visible_name.font().setPointSize(24)
        self.top_layout.addWidget(self.user_visible_name)

        self.top_layout.addStretch()

        palette = self.palette()
        create_icon = QtGui.QPixmap("client/icons/add.svg")
        mask = create_icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
        create_icon.fill(palette.light().color())
        create_icon.setMask(mask)

        self.create_project = QtWidgets.QPushButton()
        self.create_project.clicked.connect(on_create)
        self.create_project.setIcon(QtGui.QIcon(create_icon))
        self.create_project.setStyleSheet(
            """QToolTip {
                color: black;
                }
            """
        )
        self.create_project.setToolTip("Create Project")
        self.top_layout.addWidget(self.create_project)

        self.project_list_widget = QtWidgets.QWidget()
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidget(self.project_list_widget)
        self.v_layout.addWidget(self.project_list_widget)

        self.project_list_layout = QtWidgets.QVBoxLayout()
        self.project_list_widget.setLayout(self.project_list_layout)

        self.resize(QtCore.QSize(600, 400))

        self.project_list: list[tuple[str, str]] = list(project_list.items())
        self.project_list.sort(key=lambda x: x[1])

        self.project_objects: dict[str, ProjectInList] = {}
        self.generate_list()

    def generate_list(self):
        for project_id, project_name in self.project_list:
            project_in_list = ProjectInList(self, project_name, project_id, self.on_remove, self.on_rename, self.on_open)
            project_in_list.show()
            self.project_list_layout.addWidget(project_in_list)
            self.project_objects[project_id] = project_in_list
        self.project_list_layout.addStretch()

    def add_project(self, project_name, project_id):
        obj = project_id, project_name
        self.project_list.append(obj)
        self.project_list.sort(key=lambda x: x[1])
        index = self.project_list.index(obj)

        project_in_list = ProjectInList(self, project_name, project_id, self.on_remove, self.on_rename, self.on_open)
        project_in_list.show()

        self.project_list_layout.insertWidget(index, project_in_list)
        self.project_objects[project_id] = project_in_list

    def remove_project(self, project_id):
        idx = -1
        for i, (project_id_, project_name) in enumerate(self.project_list):
            if project_id == project_id_:
                idx = i
                break
        if idx == -1:
            return
        self.project_list.pop(idx)
        project_in_list = self.project_objects.pop(project_id)
        self.project_list_layout.removeWidget(project_in_list)
        project_in_list.deleteLater()

    def rename_project(self, project_id, new_name):
        self.remove_project(project_id)
        self.add_project(new_name, project_id)

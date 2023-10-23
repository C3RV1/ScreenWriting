import os.path

from client.gui.ScriptEditor import ScriptEditor
from PySide6 import QtWidgets, QtGui, QtCore
from common.Project import Folder, Document
from common.ServerEndpoints import *
from client.Net import Net


class DocumentWidget(QtWidgets.QWidget):
    DOCUMENT_ICON = 0

    def __init__(self, parent, name, path, document: Document, net: Net):
        super().__init__(parent)
        self.path = path
        self.net: Net = net
        self.document = document

        self.header_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.header_layout)

        self.header_icon = QtWidgets.QLabel(self)
        if DocumentWidget.DOCUMENT_ICON is None:
            palette = self.palette()
            icon = QtGui.QPixmap("client/icons/document.svg")
            mask = icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
            icon.fill(palette.light().color())
            icon.setMask(mask)
            DocumentWidget.DOCUMENT_ICON = icon
        self.header_icon.setPixmap(DocumentWidget.DOCUMENT_ICON)
        self.header_layout.addWidget(self.header_icon)

        self.name_label = QtWidgets.QPushButton(name, self)
        self.name_label.clicked.connect(self.open)
        self.header_layout.addWidget(self.name_label)

        self.header_layout.addStretch()

    def open(self):
        pass


class FolderWidget(QtWidgets.QWidget):
    FOLDER_ICON = None
    OPEN_FOLDER_ICON = None

    def __init__(self, parent, name, folder: Folder, path: str, net: Net):
        super().__init__(parent)
        self.path = path
        self.net: Net = net

        self.v_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.v_layout)

        self.header_layout = QtWidgets.QHBoxLayout()
        self.v_layout.addLayout(self.header_layout)

        self.header_icon = QtWidgets.QLabel(self)
        if FolderWidget.FOLDER_ICON is None:
            palette = self.palette()
            icon = QtGui.QPixmap("client/icons/folder.svg")
            mask = icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
            icon.fill(palette.light().color())
            icon.setMask(mask)
            FolderWidget.FOLDER_ICON = icon
        if FolderWidget.OPEN_FOLDER_ICON is None:
            palette = self.palette()
            icon = QtGui.QPixmap("client/icons/folder_open.svg")
            mask = icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
            icon.fill(palette.light().color())
            icon.setMask(mask)
            FolderWidget.OPEN_FOLDER_ICON = icon
        self.header_icon.setPixmap(FolderWidget.FOLDER_ICON)
        self.header_layout.addWidget(self.header_icon)

        self.name_label = QtWidgets.QPushButton(name, self)
        self.name_label.clicked.connect(self.toggle_shown)
        self.header_layout.addWidget(self.name_label)

        self.header_layout.addStretch()

        self.shown = False

        self.inner_widget = QtWidgets.QWidget(self)
        self.inner_widget.setContentsMargins(2, 0, 0, 0)
        self.inner_widget.hide()
        self.v_layout.addWidget(self.inner_widget)

        self.v_layout.addStretch()

        self.inner_layout = QtWidgets.QVBoxLayout()
        self.inner_widget.setLayout(self.inner_layout)

        self.folders: dict[str, FolderWidget] = {}

        for name, folder in folder.folders.items():
            self.add_child_folder(name, folder)

    def toggle_shown(self):
        self.shown = not self.shown
        if self.shown:
            self.inner_widget.show()
            self.header_icon.setPixmap(FolderWidget.OPEN_FOLDER_ICON)
        else:
            self.inner_widget.hide()
            self.header_icon.setPixmap(FolderWidget.FOLDER_ICON)
        self.header_icon.repaint()

    def add_child_folder(self, name: str, folder: Folder):
        folder_widget = FolderWidget(self, name, folder, os.path.join(self.path, name), self.net)
        self.folders[name] = folder_widget
        self.inner_layout.addWidget(folder_widget)


class ProjectFileSystem(FolderWidget):
    def __init__(self, parent, project: Project, net: Net):
        super().__init__(parent, "File System", project.filesystem, "", net)
        self.toggle_shown()
        self.name_label.setEnabled(False)
        self.project = project
        self.net: Net = net

    def created_doc(self, msg):
        pass

    def created_folder(self, msg):
        pass


class ProjectWindow(QtWidgets.QMainWindow):
    def __init__(self, project: Project, other_users: list[User], net: Net):
        super().__init__()
        self.setWindowTitle(f"Project {project.name}")
        self.resize(1280, 720)

        self.script_editor = ScriptEditor()
        self.setCentralWidget(self.script_editor)

        self.filesystem_dock = QtWidgets.QDockWidget()
        self.filesystem_dock.setAllowedAreas(
            QtGui.Qt.DockWidgetArea.LeftDockWidgetArea |
            QtGui.Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(QtGui.Qt.DockWidgetArea.LeftDockWidgetArea, self.filesystem_dock)
        self.filesystem = ProjectFileSystem(self, project, net)
        self.filesystem_dock.setWidget(self.filesystem)

        self.project: Project = project
        self.other_users = other_users
        self.net: Net = net

    def opened_project(self, msg: OpenedProject):
        self.other_users.append(msg.user)

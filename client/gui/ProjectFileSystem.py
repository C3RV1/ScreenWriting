import os
import typing

from PySide6 import QtWidgets, QtGui, QtCore

from common.Project import Folder, Document, Project
from common.ProjectEndpoints import *

from client.Net import Net


class ProjectFileSystem(QtWidgets.QTreeWidget):
    FOLDER_ICON = None
    DOCUMENT_ICON = None

    def __init__(self, parent, project: Project, net: Net):
        super().__init__(parent)
        if ProjectFileSystem.FOLDER_ICON is None:
            palette = self.palette()
            icon = QtGui.QPixmap("client/icons/folder.svg")
            mask = icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
            icon.fill(palette.light().color())
            icon.setMask(mask)
            ProjectFileSystem.FOLDER_ICON = icon
        if ProjectFileSystem.DOCUMENT_ICON is None:
            palette = self.palette()
            icon = QtGui.QPixmap("client/icons/document.svg")
            mask = icon.createMaskFromColor(QtGui.QColor(0, 0, 0), QtCore.Qt.MaskMode.MaskOutColor)
            icon.fill(palette.light().color())
            icon.setMask(mask)
            ProjectFileSystem.DOCUMENT_ICON = icon
        self.project = project
        self.net = net

        self.setHeaderHidden(True)
        self.generate_file_system(project.filesystem)
        self.itemClicked.connect(self.item_clicked)

    def created_doc(self, msg: CreatedDoc):
        pass

    def created_folder(self, msg: CreatedFolder):
        pass

    def generate_file_system(self, root: Folder):
        def add_folder_recursive(folder: Folder, path, parent: typing.Optional[QtWidgets.QTreeWidgetItem]):
            def create_item(name_, icon, data):
                widget = QtWidgets.QTreeWidgetItem()
                widget.setIcon(0, icon)
                widget.setText(0, name_)
                widget.setData(0, QtCore.Qt.ItemDataRole.UserRole, (os.path.join(path, name_), data))
                if parent is None:
                    self.addTopLevelItem(widget)
                else:
                    parent.addChild(widget)
                return widget

            for name, folder_ in folder.folders.items():
                folder_widget = create_item(name, ProjectFileSystem.FOLDER_ICON, folder_)
                add_folder_recursive(folder_, os.path.join(path, name), folder_widget)
            for name, document_ in folder.documents.items():
                create_item(name, ProjectFileSystem.DOCUMENT_ICON, document_)

        self.setColumnCount(1)
        add_folder_recursive(root, "", None)

    def item_clicked(self, item: QtWidgets.QTreeWidgetItem, column: int):
        if column != 0:
            return
        path, data = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(data, Document):
            self.net.sock.send_endp(
                JoinDoc(data.file_id)
            )
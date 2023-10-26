from PySide6 import QtWidgets, QtGui, QtCore

from common.ServerEndpoints import *
from common.ProjectEndpoints import *
from common.ScriptEndpoints import *
from common.EndpointCallbackSocket import Endpoint

from client.Net import Net
from client.RealTimeDocumentClient import RealTimeDocumentClient

from client.gui.ScriptEditor import ScriptEditor
from client.gui.ProjectFileSystem import ProjectFileSystem


class ProjectWindow(QtWidgets.QMainWindow):

    def __init__(self, project: Project, other_users: list[User], net: Net):
        super().__init__()
        self.setWindowTitle(f"Project {project.name}")
        self.resize(1280, 720)

        self.script_editor_tabs = QtWidgets.QTabWidget()

        self.script_editors: list[ScriptEditor] = []
        
        self.setCentralWidget(self.script_editor_tabs)

        self.filesystem_dock = QtWidgets.QDockWidget()
        self.filesystem_dock.setWindowTitle("Filesystem")
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

        self.net.sock.set_endpoint(Endpoint(self.sync_document, SyncDoc))
        self.net.sock.set_endpoint(Endpoint(self.project_wide_error, ProjectScopeRequestError))
        self.net.sock.set_endpoint(Endpoint(self.patched_document, PatchedScript))
        self.net.sock.set_endpoint(Endpoint(self.ack_change, AckPatch))

        self.realtime_document_clients: dict[str, RealTimeDocumentClient] = {}

    def opened_project(self, msg: OpenedProject):
        self.other_users.append(msg.user)

    def patched_document(self, msg: PatchedScript):
        realtime_client = self.realtime_document_clients.get(msg.document_id, None)
        if realtime_client is None:
            return
        realtime_client.got_change(msg)

    def ack_change(self, msg: AckPatch):
        realtime_client = self.realtime_document_clients.get(msg.document_id, None)
        if realtime_client is None:
            return
        realtime_client.ack_change(msg)

    def project_wide_error(self, msg: ProjectScopeRequestError):
        QtWidgets.QMessageBox.critical(
            None,
            "Project Wide Error!",
            msg.message
        )

    def sync_document(self, msg: SyncDoc):
        realtime_client = RealTimeDocumentClient(
            msg.blocks,
            msg.file_id,
            self.net
        )
        self.realtime_document_clients[realtime_client.file_id] = realtime_client

        script_editor = ScriptEditor(realtime_client)
        self.script_editors.append(script_editor)
        self.script_editor_tabs.addTab(script_editor, "Open file")

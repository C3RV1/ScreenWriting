import datetime
import logging
import os.path
import socket
import ssl
import threading
import typing

import pymongo
import pymongo.errors
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
from server import Config, ClientHandler
import select
from common.ServerEndpoints import *
from server.ServerProject import ServerProject
from server.RealTimeDocument import RealTimeDocument, RealTimeUser


def generate_certificate(cert_path, key_path):
    print("No certificate could be found!")
    print("Generating a certificate...")

    common_name = input("Common name: ")
    hostname = input("Hostname: ")

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(b'passphrase')
        ))

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"ES"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name)
    ])

    cert = x509.CertificateBuilder()\
        .subject_name(subject)\
        .issuer_name(issuer)\
        .public_key(key.public_key())\
        .serial_number(x509.random_serial_number())\
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))\
        .not_valid_after(
            datetime.datetime.now(
                datetime.timezone.utc) + datetime.timedelta(days=365*20)
        )\
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(hostname)]),
            critical=False
        )\
        .sign(key, hashes.SHA256())

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return True


class Console(threading.Thread):
    def __init__(self, managed: 'Net'):
        super().__init__()
        self.managed: 'Net' = managed

    def run(self):
        while True:
            command = input("> ")
            if command == "quit":
                self.managed.exit_event.set()
                break


class Net:
    def __init__(self):
        logging.info("Initializing server...")
        self.exit_event = threading.Event()

        self.connected_lock = threading.RLock()
        self.connected_clients = []

        self.open_projects_lock = threading.RLock()
        self.open_projects: dict[str, ServerProject] = {}

        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.mongo_client = pymongo.MongoClient("localhost", 27017)
        self.database = self.mongo_client["screenwriting"]
        try:
            self.database.command("ping")
        except pymongo.errors.ConnectionFailure:
            logging.critical("Couldn't connect to the MongoDB database!")
            self.exit_event.set()
            return

        logging.info("Checking certificates...")
        if not os.path.isfile("cert.pcm") or not os.path.isfile("key.pcm"):
            generate_certificate("cert.pcm", "key.pcm")
        self.ssl_context.load_cert_chain("cert.pcm", keyfile="key.pcm", password="passphrase")

        logging.info("Loaded certificates...")
        self.bind_socket = socket.socket()
        self.bind_socket.bind(Config.ServerConfig.LISTENING_ADDR)
        self.bind_socket.listen(Config.ServerConfig.MAX_BIND)

        self.last_checked_alive = datetime.datetime.now(datetime.timezone.utc)

    def run(self):
        while not self.exit_event.is_set():
            if select.select([self.bind_socket], [], [], 0.2)[0]:
                sock, sock_addr = self.bind_socket.accept()
                sock = self.ssl_context.wrap_socket(sock, server_side=True)
                handler = ClientHandler.ClientHandler(sock, sock_addr, self)
                handler.start()
                with self.connected_lock:
                    self.connected_clients.append(handler)
            for client in self.connected_clients.copy():
                client: ClientHandler.ClientHandler
                if not client.is_alive():
                    self.close_client(client)
            if datetime.datetime.now(datetime.timezone.utc) - self.last_checked_alive > datetime.timedelta(seconds=5):
                self.last_checked_alive = datetime.datetime.now(datetime.timezone.utc)
                for client in self.connected_clients.copy():
                    client.check_alive()

        for client in self.connected_clients.copy():
            self.close_client(client)

    def close_client(self, client):
        with self.connected_lock:
            if client not in self.connected_clients:
                return
            if client.current_project:
                for rtu in client.current_real_time_users.values():
                    self.leave_realtime_user(rtu, client.current_project)
                client.current_project.opened_users.remove(client)
                self.check_close_project(client.current_project)
                client.current_project = None
            logging.info(f"Closing client {client.sock_addr}...")
            self.connected_clients.remove(client)
            client.close()

    def check_close_project(self, project):
        if not project.opened_users:
            self.close_project(project)

    def close_project(self, project: ServerProject):
        logging.info(f"Closing project {project.name}")
        with self.open_projects_lock:
            project.save_to_database(self.database)

    def leave_realtime_user(self, realtime_user: RealTimeUser,
                            project: ServerProject):
        rtd = realtime_user.rtd
        with rtd.document_lock:
            rtd.broadcast_leave_client(realtime_user)
            with rtd.editing_users_lock:
                if len(rtd.editing_users) == 0:
                    self.close_realtime_document(rtd, project)

    def close_realtime_document(self, rtd: RealTimeDocument, project: ServerProject):
        rtd.save()
        with project.open_rtd_lock:
            project.open_rtd.pop(rtd.file_id, None)

    def get_project_list(self) -> list[tuple[str, str]]:
        project_collection = self.database["projects"]
        project_names = [(p["name"], str(p["_id"])) for p in project_collection.find()]
        return project_names

    def broadcast_created_project(self, project: ServerProject):
        msg = CreatedProject(project.project_id, project.name)
        with self.connected_lock:
            for client in self.connected_clients:
                client: ClientHandler.ClientHandler
                client.sock.send_endp(msg)

    def remove_project(self, project):
        msg = DeletedProject(project.project_id)
        project.remove_from_database(self.database)
        with self.connected_lock:
            for client in self.connected_clients:
                client: ClientHandler.ClientHandler
                client.sock.send_endp(msg)

    def broadcast_rename_project(self, project):
        msg = RenamedProject(project.project_id, project.name)
        with self.connected_lock:
            for client in self.connected_clients:
                client: ClientHandler.ClientHandler
                client.sock.send_endp(msg)

    def get_project_by_id(self, id_) -> ServerProject:
        with self.open_projects_lock:
            project = self.open_projects.get(id_, None)
            if project is None:
                return ServerProject.load_from_id(self.database, id_)
            return project

    def open_project_by_id(self, id_, client_handler: ClientHandler.ClientHandler) -> typing.Optional[ServerProject]:
        if client_handler.user is None:
            return None

        with self.open_projects_lock:
            project = self.open_projects.get(id_, None)
            if project is None:
                project = ServerProject.load_from_id(self.database, id_)
            if project is None:
                return None
            self.open_projects[project.project_id] = project

            with project.project_lock:
                project.opened_users.append(client_handler)
                self.broadcast_opened_project(project, client_handler)
        return project

    def broadcast_opened_project(self, project: ServerProject, client_handler: 'ClientHandler.ClientHandler'):
        for user in project.opened_users:
            if user == client_handler:
                continue
            user.sock.send_endp(OpenedProject(client_handler.user))

    def open_realtime_document_by_id(self, client_handler: 'ClientHandler.ClientHandler',
                                     document_id: str):
        if client_handler.user is None:
            return None
        if client_handler.current_project is None:
            return None

        project = client_handler.current_project
        with project.open_rtd_lock:
            open_rtd = project.open_rtd.get(document_id, None)
            if open_rtd is None:
                open_rtd = RealTimeDocument.open_from_database(self.database, document_id, project.project_id)
                if open_rtd is not None:
                    project.open_rtd[open_rtd.file_id] = open_rtd

            if open_rtd is None:
                return None

            with open_rtd.editing_users_lock:
                if client_handler in open_rtd.editing_users:
                    return None

                return open_rtd.join_client(client_handler)

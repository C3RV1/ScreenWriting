import datetime
import logging
import os.path
import socket
import ssl
import struct
import threading

import pymongo
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
from server import Config, ClientHandler
import select
from common.EndpointID import EndpointID
from server.ServerProject import ServerProject


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
    def __init__(self, config: Config.Config):
        logging.info("Initializing server...")
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.config = config
        self.mongo_client = pymongo.MongoClient("localhost", 27017)
        self.database = self.mongo_client["screenwriting"]

        logging.info("Checking certificates...")
        if not os.path.isfile("cert.pcm") or not os.path.isfile("key.pcm"):
            generate_certificate("cert.pcm", "key.pcm")
        self.ssl_context.load_cert_chain("cert.pcm", keyfile="key.pcm", password="passphrase")

        logging.info("Loaded certificates...")
        self.bind_socket = socket.socket()
        self.bind_socket.bind(config.LISTENING_ADDR)
        self.bind_socket.listen(config.MAX_BIND)

        self.connected_lock = threading.Lock()
        self.connected_clients = []

        self.exit_event = threading.Event()

        self.last_checked_alive = datetime.datetime.now(datetime.timezone.utc)

        self.open_projects: list[ServerProject] = []

    def run(self):
        while not self.exit_event.is_set():
            if select.select([self.bind_socket], [], [], 0)[0]:
                sock, sock_addr = self.bind_socket.accept()
                sock = self.ssl_context.wrap_socket(sock, server_side=True)
                handler = ClientHandler.ClientHandler(sock, sock_addr, self)
                handler.start()
                self.connected_lock.acquire()
                self.connected_clients.append(handler)
                self.connected_lock.release()
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
        self.connected_lock.acquire()
        if client not in self.connected_clients:
            self.connected_lock.release()
            return
        logging.info(f"Closing client {client.sock_addr}...")
        self.connected_clients.remove(client)
        self.connected_lock.release()
        client.close()

    def get_project_list(self) -> list[tuple[str, str]]:
        project_collection = self.database["projects"]
        project_names = [(p["name"], str(p["_id"])) for p in project_collection.find()]
        return project_names

    def broadcast_created_project(self, project):
        name_encoded = project.name.encode("utf-8")
        msg = struct.pack("B", len(name_encoded)) + name_encoded + project.project_id
        for client in self.connected_clients:
            client: ClientHandler.ClientHandler
            client.sock.do_send(EndpointID.CREATED_PROJECT, msg)

    def remove_project(self, project):
        project.remove_from_database(self.database)
        msg = project.project_id
        for client in self.connected_clients:
            client: ClientHandler.ClientHandler
            client.sock.do_send(EndpointID.DELETED_PROJECT, msg)

    def broadcast_rename_project(self, project):
        name_encoded = project.name.encode("utf-8")
        msg = project.project_id + struct.pack("B", len(name_encoded)) + name_encoded
        for client in self.connected_clients:
            client: ClientHandler.ClientHandler
            client.sock.do_send(EndpointID.RENAMED_PROJECT, msg)

    def get_project_by_id(self, id_) -> ServerProject:
        for project in self.open_projects:
            if project.project_id == id_:
                return project
        return ServerProject.load_from_id(self.database, id_, self.config)


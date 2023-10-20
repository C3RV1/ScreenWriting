from client import Client
from PySide6 import QtWidgets
import logging


if __name__ == '__main__':
    logging.basicConfig(filename="server.log", level=logging.INFO)
    console_logger = logging.StreamHandler()
    logging.getLogger().addHandler(console_logger)

    app = QtWidgets.QApplication()

    client = Client.Client()
    client.run("localhost")

    app.exec()


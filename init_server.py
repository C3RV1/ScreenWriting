import logging

from server.Net import Net, Console
from server.Config import Config


if __name__ == '__main__':
    logging.basicConfig(filename="server.log", level=logging.INFO)
    console_logger = logging.StreamHandler()
    logging.getLogger().addHandler(console_logger)
    server = Net(Config())
    console = Console(server)
    console.start()
    server.run()

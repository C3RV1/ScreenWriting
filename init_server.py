import logging

from server.Net import Net, Console


if __name__ == '__main__':
    logging.basicConfig(filename="server.log", level=logging.INFO)
    console_logger = logging.StreamHandler()
    logging.getLogger().addHandler(console_logger)
    server = Net()
    console = Console(server)
    console.start()
    server.run()

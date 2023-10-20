import time

from client import Net, Config
from common.EndpointID import EndpointID
from common.EndpointCallbackSocket import Endpoint
import logging


if __name__ == '__main__':
    logging.basicConfig(filename="server.log", level=logging.INFO)
    console_logger = logging.StreamHandler()
    logging.getLogger().addHandler(console_logger)

    client = Net.Net(Config.Config())
    client.connect_to_server("localhost", lambda hostname: True)
    running = True

    def pong_endpoint(_msg):
        global running
        print("Pong received")
        running = False

    def close_endpoint(_msg=b""):
        global running
        print("Close received")
        running = False

    def alive_endpoint(_msg):
        global running, client
        client.sock.do_send(EndpointID.I_AM_ALIVE)

    client.sock.on_close = close_endpoint

    client.sock.set_endpoint(
        EndpointID.PONG,
        Endpoint(pong_endpoint, max_data_size=0)
    )
    client.sock.set_endpoint(
        1,
        Endpoint(close_endpoint, max_data_size=0)
    )
    client.sock.set_endpoint(
        EndpointID.ARE_U_ALIVE,
        Endpoint(alive_endpoint, max_data_size=0)
    )
    client.sock.do_send(EndpointID.PING)

    while running:
        client.sock.do_receive()
        time.sleep(0.1)


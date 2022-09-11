import asyncio

import websockets

from crewmate import BaseCrewmate, CrewmateProperty
from util import MessageTypes, MessageFields
import os

# raspberry pi imports
dir_path = os.path.dirname(os.path.realpath(__file__))

class RainProxy(BaseCrewmate):
    """
    proxy for rain.html so it can use UDP shout
    """

    def __init__(self):
        self.address = "RAIN_PROXY"
        super(RainProxy, self).__init__()


if __name__ == "__main__":
    qm = RainProxy()
    start_server = websockets.serve(qm.run_proxy, "0.0.0.0", 31336)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_until_complete(qm.start())
    asyncio.get_event_loop().run_forever()


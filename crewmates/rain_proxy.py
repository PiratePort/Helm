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

    async def main():
        async with websockets.serve(qm.run_proxy, "0.0.0.0", 31336,
                                    process_request=qm.serve_http_in_websocket_process_request):
            await qm.start()
            await asyncio.Future()  # run forever

    asyncio.run(main())
    # start_server = websockets.serve(qm.run_proxy, "0.0.0.0", 31336,
    #                                 process_request=qm.serve_http_in_websocket_process_request)
    # asyncio.run(start_server)
    #asyncio.get_running_loop().run_until_complete(qm.start())
    #asyncio.get_running_loop().run_forever()


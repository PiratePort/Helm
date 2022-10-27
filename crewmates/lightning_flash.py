import asyncio

import websockets

from crewmate import BaseCrewmate, CrewmateProperty
from util import MessageTypes, MessageFields
import os

# raspberry pi imports
dir_path = os.path.dirname(os.path.realpath(__file__))

try:
    import RPi.GPIO as GPIO
    on_pi = True
    has_gpio = True
    LIGHT_PIN = 37
    print("on PI")
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(LIGHT_PIN, GPIO.OUT)
    
except ModuleNotFoundError as e:
    print("No GPIOs, can't actually fire anything")


class LightningFlash(BaseCrewmate):
    """
    proxy for rain.html so it can use UDP shout
    """

    def __init__(self):
        self.address = "LIGHTNING_FLASH"
        super(LightningFlash, self).__init__()


    async def on_connection(self, ws):
        await self.on_prop_change("RAIN", "strike", self.on_strike)

    async def on_strike(self, val):
        # only flash when it's turned TRUE
        if not val:
            return
        if on_pi:
            GPIO.output(LIGHT_PIN, 1)
        print("LIGHTNING")
        await asyncio.sleep(1.5)
        print("/LIGHTNING")
        if on_pi:
            GPIO.output(LIGHT_PIN, 0)



if __name__ == "__main__":
    qm = LightningFlash()
    asyncio.get_event_loop().run_until_complete(qm.start())
    asyncio.get_event_loop().run_forever()


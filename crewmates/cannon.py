import asyncio
from crewmate import BaseCrewmate, CrewmateProperty
from util import MessageTypes, MessageFields
import os

# raspberry pi imports
dir_path = os.path.dirname(os.path.realpath(__file__))
on_pi = False
on_bbb = False
has_gpio = False
LIGHT_PIN = None
SMOKE_PIN = None
try:
    import RPi.GPIO as GPIO
    on_pi = True
    has_gpio = True
    LIGHT_PIN = 5
    SMOKE_PIN = 5
    print("on PI")
except ModuleNotFoundError as e:
    try:
        import Adafruit_BBIO.GPIO as GPIO
        on_bbb = True
        has_gpio = True
        print("on BBB")
        LIGHT_PIN = "P8_7"
        SMOKE_PIN = "P9_12"
    except ModuleNotFoundError as e2:
        print("No GPIOs, can't actually fire anything")


class Cannon(BaseCrewmate):
    """
    The cannon.... fires the cannon
    """

    firing = CrewmateProperty()
    jammed = CrewmateProperty()  # set to True if we're jammed (firing too fast)
    loading = CrewmateProperty()  # smoke machine is running

    def __init__(self):
        self.address = "CANNON"
        self.firing = False

        if on_pi:
            GPIO.setmode(GPIO.BOARD)

        if has_gpio:
            GPIO.setup(LIGHT_PIN, GPIO.OUT)
            GPIO.setup(SMOKE_PIN, GPIO.OUT)

        super(Cannon, self).__init__()

    async def handle_command(self, msg):
        if msg[MessageFields.DATA]["command"] == "FIRE":
            if self.firing or self.loading or self.jammed:
                self.jammed = True  # this triggers a sound effect in 'ambiance' crewmate
                await asyncio.sleep(0.25)
                self.jammed = False
                return
            try:
                await self.load_cannon()
                if has_gpio:
                    GPIO.output(LIGHT_PIN, 1)
                print("**BOOM**")
                self.firing = True
                await asyncio.sleep(0.5)
                #playsound(dir_path+"/sounds/nri-cannon.mp3", block=False)
                await asyncio.sleep(2.5)
                if has_gpio:
                    GPIO.output(LIGHT_PIN, 0)

                # give the cannon a rest
                await asyncio.sleep(0.5)
                # await asyncio.sleep(0.5)
                # playsound(dir_path+"/sounds/splash.mp3", block=False)
                # await asyncio.sleep(2.5)

            finally:
                self.firing = False

    async def load_cannon(self):
        print("**LOADING**")
        try:
            self.loading = True
            await self._toggle_smoke()
            await asyncio.sleep(2)
            await self._toggle_smoke()
        finally:
            self.loading = False

    async def _toggle_smoke(self):
        """ Toggles smoke machine on or off (it's a momentary switch) """
        if has_gpio:
            GPIO.output(SMOKE_PIN, 1)
        await asyncio.sleep(0.25)
        if has_gpio:
            GPIO.output(SMOKE_PIN, 0)



if __name__ == "__main__":
    qm = Cannon()
    asyncio.get_event_loop().run_until_complete(qm.start())
    asyncio.get_event_loop().run_forever()


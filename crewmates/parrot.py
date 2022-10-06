import asyncio
import alsaaudio
from crewmate import BaseCrewmate, CrewmateProperty
from util import MessageTypes, MessageFields
import os
from playsound import playsound
import numpy as np
import soundfile
import time
import sys
import math

# raspberry pi imports
dir_path = os.path.dirname(os.path.realpath(__file__))
on_pi = False
has_gpio = False
try:
    import RPi.GPIO as GPIO
    on_pi = True
    has_gpio = True
    TILT_SERVO = 15
    PAN_SERVO  = 14
    from adafruit_servokit import ServoKit
    servo_kit = ServoKit(channels=16)
    print("on PI")
except ModuleNotFoundError as e:
    print("No GPIOs, Not on Pi")

# Sound/animation prep
VOICE_PATH = dir_path + "/sounds/parrot.wav"
VOL_RANGE = 25  # volume is an int between 0 and this. This lets us dial in a fixed precision

MAX_SQUAK_VOL = 50 # out of 100. Bigger is louder
# ch2 = np.array([data[i][1] for i in range(len(data))])  # channel 2

class Parrot(BaseCrewmate):
    """
    The cannon.... fires the cannon
    """

    def __init__(self):
        self.address = "Parrot"
        self.squawking = True
        self.sleep_time_secs = 30
        self.volume = MAX_SQUAK_VOL
        self._dance_instead = False
        self._pan_factor = 0
        self._tilt_factor = 0
        self._squawk_timestamp = 0
        self._pan = 0
        self._tilt = 0
        self._pan_dev_dir = 1.0  # Set to 1 to rotate clockwise, -1 anti-clockwise
        self._last_pan_dev_switch = 0

        # Retrieve the data from the wav file
        speech_data_stereo, speech_samplerate = soundfile.read(VOICE_PATH)

        # Working with stereo audio, there are two channels in the audio data.
        # Let's just average the channels
        sq_speech_data = np.square(speech_data_stereo.mean(axis=1))
        print(speech_samplerate)
        print(len(sq_speech_data))
        del speech_data_stereo
        # sample rate is way higher than we need. Let's smooth it out while taking RMS to get intensity
        smooth_time_secs = 0.005  # every ms
        smooth_every = int(speech_samplerate * smooth_time_secs)
        # resize array to it's an even divisor
        sq_speech_data.resize(math.ceil(len(sq_speech_data)/smooth_every)*smooth_every)
        rms_speech_data = np.sqrt(np.mean(sq_speech_data.reshape(-1, smooth_every), axis=1))
        print(len(rms_speech_data))
        del sq_speech_data
        min_speech = np.min(rms_speech_data)
        # cut out floor
        rms_speech_data = rms_speech_data - min_speech
        max_speech = np.max(rms_speech_data)

        # make multiple of  next smoothing round
        second_smooth_every = 5
        rms_speech_data.resize(math.ceil(len(rms_speech_data)/second_smooth_every)*second_smooth_every)

        # smooth again for servos, but this time by setting it to the max for every x sample
        rms_speech_data = np.max(rms_speech_data.reshape(-1, second_smooth_every), axis=1)

        # convert to int range based on VOL_RANGE
        self._speech_movement_array = ((rms_speech_data / max_speech) * VOL_RANGE).astype(int)
        self._speech_sample_rate = 1.0/smooth_time_secs/second_smooth_every

        super(Parrot, self).__init__()

    async def on_connection(self, ws):
        # start the parrot when we connect
        loop = asyncio.get_event_loop()
        loop.create_task(self.squawk_forever())
        loop.create_task(self.pan_forever())
        await self.set_volume(MAX_SQUAK_VOL)
        await self.on_prop_change("PUMPKINS", "singing", self.on_pumpkin_singing_change)

    async def on_pumpkin_singing_change(self, val):
        # we go quiet when pumpkins are singing
        print("Changing volume " + str(val))
        self._dance_instead = val  # we should DANCE to the punkin pirates
        await self.set_volume(0 if val else MAX_SQUAK_VOL)


    async def set_volume(self, vol):
        m = alsaaudio.Mixer()
        self.volume = vol
        m.setvolume(vol)

    async def handle_command(self, msg):
        pass
        #if msg[MessageFields.DATA]["command"] == "FIRE":

    # Squawking logic
    async def squawk_forever(self):
        # do a squawk first to preload sound
        await self.squawk()
        while self.squawking:
            await self.squawk()
            # need some fancy sleep logic to wake and DANCE
            for x in range(self.sleep_time_secs):
                if not self._dance_instead:
                    await asyncio.sleep(1)

            while self._dance_instead:
                await self.dance()
                await asyncio.sleep(0.25)

    async def pan_forever(self):
        # do a squawk first to preload sound
        while self.squawking:
            for i in range(0, VOL_RANGE, int(VOL_RANGE/5)):
                self.set_pan(i)
                await asyncio.sleep(4)
            for i in range(VOL_RANGE, 0, -1*int(VOL_RANGE / 5)):
                self.set_pan(i)
                await asyncio.sleep(4)


    async def squawk(self):
        loop = asyncio.get_event_loop()
        if self._dance_instead:
            return

        await asyncio.gather(
            loop.run_in_executor(None, self._squawk_blocking),
            self._animate(time.perf_counter()))

    def _squawk_blocking(self):
        print("SQUAWK ")
        #self._squawk_timestamp = time.perf_counter()
        playsound(VOICE_PATH, block=True)
        #self._animate_blocking(self._squawk_timestamp)
        print("/SQUAWK")

    # Moving Logic
    async def _animate(self, start_timestamp):
        try:
            samp_idx = 0
            data_len = len(self._speech_movement_array)
            await asyncio.sleep(0.01)
            print("-" * 100)
            while samp_idx < data_len:
                if self._dance_instead:
                    return # skip through fast
                time_idx = time.perf_counter() - start_timestamp
                samp_idx = int(time_idx * self._speech_sample_rate) + 1
                if samp_idx >= data_len:
                    return
                vol = self._speech_movement_array[samp_idx]
                self.set_tilt(vol)
                await asyncio.sleep(0.05)
        finally:
            while self._dance_instead:
                await self.dance()
                await asyncio.sleep(0.25)

    async def dance(self):
        # do a little jig
        tilt_angles = [65, 75, 75, 65, 75]
        # pan_angles = [80, 82, 80, 80, 82]
        sleeps     = [0.3, 0.3, 1.0, 0.3, 0.3]
        for i in range(len(sleeps)):
            servo_kit.servo[TILT_SERVO].angle = tilt_angles[i]
            # servo_kit.servo[PAN_SERVO].angle = pan_angles[i]
            await asyncio.sleep(sleeps[i])

    def set_tilt(self, vol):
        if vol == self._tilt:
            return

        self._tilt = vol

        factor = float(vol)/VOL_RANGE
        if not on_pi:
            print("\r" + "-" * int(100 * factor), end="")
            sys.stdout.flush()
        else:
            # these are backwards because lower servo = higher angle
            MAX_ANGLE = 50.0
            MIN_ANGLE = 100.0
            angle = (MAX_ANGLE - MIN_ANGLE) * factor + MIN_ANGLE
            servo_kit.servo[TILT_SERVO].angle = angle

    def set_pan(self, vol):
        if vol == self._pan:
            return
        self._pan = vol
        factor = float(vol) / VOL_RANGE
        if on_pi:
            # these are backwards because lower servo = higher angle
            MAX_ANGLE = 65.0
            MIN_ANGLE = 100.0
            angle = (MAX_ANGLE - MIN_ANGLE) * factor + MIN_ANGLE
            servo_kit.servo[PAN_SERVO].angle = angle



if __name__ == "__main__":
    qm = Parrot()
    asyncio.get_event_loop().run_until_complete(qm.start())
    asyncio.get_event_loop().run_forever()


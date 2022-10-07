import asyncio
import json
import os
import http
from util import MessageTypes, MessageFields, shout_client
import websockets


class CrewmateProperty:
    """
    A property that can be queried from outside and will notify if changed
    """

    crewmate = None  # the crewmate that set this
    value = None

    def __set_name__(self, owner, name):
        self.public_name = name
        self.value = None

    def __get__(self, obj, objtype=None):
        return self.value

    def __set__(self, obj, value):
        if self.crewmate is not None:
            asyncio.create_task(self.crewmate.notify({"prop": self.public_name, "val": value}))

        self.value = value

def get_dict_attr(obj, attr):
    for obj in [obj] + obj.__class__.mro():
        if attr in obj.__dict__:
            return obj.__dict__[attr]
    raise AttributeError

class BaseCrewmate:
    _uri = "ws://localhost:31337"
    address = "ANONYMOUS"  # override this plz
    ws = None
    on_deck = False
    prop_names = []
    proxy_ws = []

    def __init__(self):
        # find all the properties, register with them and cache them
        self.prop_names = [x for x in self.__class__.__dict__.keys() if isinstance(self.__class__.__dict__[x], CrewmateProperty)]
        for prop_name in self.prop_names:
            print("registering " + prop_name)
            self.__class__.__dict__[prop_name].crewmate = self

        self._notify_listeners = []
        try:
            self._http_server_root = os.path.realpath(os.path.dirname(os.path.realpath(__file__)) + "/../ui")
        except Exception as e:
            print("Can not setup HTTP server because: " + str(e))
            self._http_server_root = None

    async def on_connection(self, ws):
        """ Overwrite this if you want to do something on connection"""
        pass

    async def handle_custom_msg(self, msg):
        """ overwrite this if you want to handle custom messages"""
        pass

    async def handle_command(self, msg):
        """ overwrite this to handle a command """
        pass

    async def on_prop_change(self, crewmate, prop, async_handler):
        self._notify_listeners.append((crewmate, prop, async_handler))
        await self.ws.send(json.dumps({
            MessageFields.TYPE: MessageTypes.SUBSCRIBE,
            MessageFields.ADDRESS: crewmate
        }))

    async def _handle_msg(self, msg):
        """ Do NOT overwrite this """
        if msg[MessageFields.TYPE] == MessageTypes.COMMAND and msg[MessageFields.ADDRESS] == self.address and \
                msg[MessageFields.DATA].get("c", None) == "~P~":
            await self.notify_all_properties()
        elif msg[MessageFields.TYPE] == MessageTypes.COMMAND and msg[MessageFields.ADDRESS] == self.address:
            await self.handle_command(msg)
        else:
            # this a notify we subbed to for someone else?
            handled = False
            if msg[MessageFields.TYPE] == MessageTypes.NOTIFY:
                for crewmate, prop, handler in self._notify_listeners:
                    if msg[MessageFields.ADDRESS] == crewmate and msg[MessageFields.DATA].get('prop','') == prop:
                        handled = True
                        await handler(msg[MessageFields.DATA].get('val', None))
            if not handled:
                await self.handle_custom_msg(msg)

    async def start(self):
        await self.find_uri()
        print("Boarding the good ship: " + self._uri)
        async with websockets.connect(self._uri) as ws:
            try:
                await ws.send(json.dumps({
                    MessageFields.TYPE: MessageTypes.SET_ADDRESS,
                    MessageFields.ADDRESS: self.address
                }))
                await ws.send(json.dumps({
                    MessageFields.TYPE: MessageTypes.SUBSCRIBE,
                    MessageFields.ADDRESS: self.address
                }))
                await asyncio.sleep(0.01)
                self.ws = ws
                self.on_deck = True
                await self.on_connection(ws)
                async for msg in ws:
                    asyncio.create_task(self._handle_msg(json.loads(msg)))
                    for p in self.proxy_ws:
                        print("Proxy Send"+msg)
                        await p.send(msg)

            except ConnectionError as e:
                print(e)
                self.on_deck = False
                return

    async def run_proxy(self, proxy_ws, path):
        """local proxy on 31336 for local crewmates who cant shout (e.g. rain.html)"""
        try:
            self.proxy_ws.append(proxy_ws)
            print(f"Proxying msgs for {proxy_ws.remote_address}")
            async for msg in proxy_ws:
                if self.ws:
                    print("Proxy " + msg)
                    await self.ws.send(msg)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"{proxy_ws.remote_address} removed from proxy")
        finally:
            self.proxy_ws.remove(proxy_ws)

    async def serve_http_in_websocket_process_request(self, path, request_headers):
        if "Upgrade" in request_headers:
            return  # Probably a WebSocket connection

        if self._http_server_root is None:
            return  # error in http server root discovery

        if path == "/":
            path = "/mobile.html"

        response_headers = [
            ('Server', 'asyncio websocket server'),
            ('Connection', 'close'),
        ]

        full_path = os.path.realpath(os.path.join(self._http_server_root, path[1:]))
        # Validate the path
        if os.path.commonpath([self._http_server_root, full_path]) != self._http_server_root or \
                not os.path.exists(full_path) or not os.path.isfile(full_path):
            print("HTTP GET {} 404 NOT FOUND".format(full_path))
            return http.HTTPStatus.NOT_FOUND, [], b'404 NOT FOUND'

        # Guess file content type
        MIME_TYPES = {
            "html": "text/html",
            "js": "text/javascript",
            "css": "text/css",
            "mp4": "video/mp4"
        }

        extension = full_path.split(".")[-1]
        mime_type = MIME_TYPES.get(extension, "application/octet-stream")
        response_headers.append(('Content-Type', mime_type))

        # Read the whole file into memory and send it out
        body = open(full_path, 'rb').read()
        response_headers.append(('Content-Length', str(len(body))))
        print("HTTP GET {} 200 OK".format(path))
        return http.HTTPStatus.OK, response_headers, body

    async def find_uri(self):
        ip = await shout_client()
        self._uri = f"ws://{ip}:31337"

    async def notify_all_properties(self):
        for prop_name in self.prop_names:
            prop = self.__class__.__dict__[prop_name]
            await self.notify({"prop": prop.public_name, "val": prop.value})

    async def notify(self, data):
        await self.ws.send(json.dumps({MessageFields.TYPE: MessageTypes.NOTIFY,
                                       MessageFields.ADDRESS: self.address,
                                       MessageFields.FROM: self.address,
                                       MessageFields.DATA: data}))

    async def command(self, address, data):
        await self.ws.send(json.dumps({MessageFields.TYPE: MessageTypes.COMMAND,
                                       MessageFields.ADDRESS: address,
                                       MessageFields.FROM: self.address,
                                       MessageFields.DATA: data}))


if __name__ == "__main__":
    bc = BaseCrewmate()
    asyncio.get_event_loop().run_until_complete(bc.start())

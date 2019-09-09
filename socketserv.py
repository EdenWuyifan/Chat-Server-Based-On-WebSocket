import asyncio
import json
import websockets

import logging
logger = logging.getLogger('websockets.server')
logger.setLevel(logging.ERROR)
logger.addHandler(logging.StreamHandler())

"""
msgtypes
========
Note: when setting destination, prefix with # for a channel and @ for a user.

REGISTER: Send to claim a username. Server responds with REGISTERED.
    sender - Username to claim

    If registration failed, responds with REGFAILED.

JOIN: Send to join a chatroom. Server responds with JOINED if successful.
    sender - Your username
    destination - The chatroom to join
    content - [JOINED only] A list of users in the room, separated by ', '.

NOTICE: Sent by server if a user has joined or left a room you are in.
    sender - The user that triggered the event.
    destination - The chatroom that the event happened in.
    content - 'join' for a join, and 'leave' for a leave.

LEAVE: Send to leave a chatroom. There is no response.
    sender - Your username
    destination - The chatroom to leave.

MSG: Send to send a message to a chatroom. On receive, means an event has happened.
    sender - Who is speaking
    destination - The chatroom to speak to. If it is SELF, that means this message is only meant for you.
    content - The content of the message

ERROR: An error from the server.
    sender - Always SERVER
    content - The error message.

REGFAILED: Sent by server when the username is already taken.
    sender - Always SERVER
    content - The username that failed.
"""
MSGTYPES = ['REGISTER', 'JOIN', 'JOINED', 'NOTICE', 'LEAVE', 'MSG', 'ERROR', 'REGISTERED', 'REGFAILED']

class MessageFormatException(Exception):
    value = None

    def __init__(self, msg):
        super().__init__(msg)
        self.value = msg


class ChatRoom:
    def __init__(self, name):
        self.name = name
        self.members = set()

    async def join(self, user):
        msg = Message('NOTICE', sender=user.name, destination=f'#{self.name}', content='join')
        msgjson = msg.serialize()
        loop = asyncio.get_event_loop()
        for member in self.members:
            ws = member.ws
            loop.create_task(ws.send(msgjson))
        self.members.add(user)
        users = ', '.join(sorted([x.name for x in self.members]))
        msg = Message('JOINED', sender='SERVER', destination=f'#{self.name}', content=users)
        await user.ws.send(msg.serialize())

    async def leave(self, user):
        msg = Message('NOTICE', sender=user.name, destination=f'#{self.name}', content='leave')
        msgjson = msg.serialize()
        self.members.remove(user)
        loop = asyncio.get_event_loop()
        for member in self.members:
            loop.create_task(member.ws.send(msgjson))

    async def broadcast(self, msg):
        loop = asyncio.get_event_loop()
        msgjson = msg.serialize()
        # Broadcasts messages to all users except the one who sent it
        for member in self.members:
            if member.name != msg.sender:
                loop.create_task(member.ws.send(msgjson))


"""
A data class that represents a Message, and provides methods to validate incoming
messages or serialize instantiated ones.

A raw Message is in JSON format, represented as a single object with these keys:
* msgtype: the type of message
* sender: Who sent the message

Depending on the msgtype, it may also have these keys:
* destination: The intended target of the message
* content: Data that is the content

See the MSGTYPES comment for details.
"""
class Message:
    def __init__(self, msgtype=None, sender=None, *, destination=None, content=None, ws=None):
        self.ws = ws
        self.msgtype = msgtype
        self.sender = sender
        self.destination = destination
        self.content = content

    @classmethod
    def loads(cls, string, ws=None):
        try:
            msg = cls(ws=ws, **json.loads(string))
            msg.verify()
            return msg
        except json.JSONDecodeError:
            raise MessageFormatException('Mesage must be valid JSON')

    def verify(self):
        if self.msgtype not in MSGTYPES:
            raise MessageFormatException('Message must have msgtype and it must be valid')
        if self.sender is None:
            raise MessageFormatException('Message must have sender')
        if len(self.sender) == 0:
            raise MessageFormatException('Sender must be at least 1 character long')
        if len(self.sender) > 64:
            raise MessageFormatException('Screennames should only be up to 64 characters long.')
        # If it's not a REGISTER message, the sender MUST correspond to the websocket
        if self.msgtype != 'REGISTER':
            if self.sender not in USERS:
                raise MessageFormatException(f"The user {self.sender} doesn't exist.")
            if USERS[self.sender].ws != self.ws:
                raise MessageFormatException(f"You're not {self.sender}! >:(")

        if self.msgtype in ['JOIN', 'LEAVE', 'MSG']:
            if self.destination is None:
                raise MessageFormatException('JOIN, LEAVE, MSG messages must have a destination')
            if self.destination[0] not in ['@', '#']:
                raise MessageFormatException('Destination must be a @user or #chatroom.')
        if self.msgtype in ['MSG']:
            if self.content is None:
                raise MessageFormatException('JOIN, LEAVE, MSG must have content')

    def serialize(self):
        obj = {'msgtype': self.msgtype, 'sender': self.sender}
        if self.destination is not None:
            obj['destination'] = self.destination
        if self.content is not None:
            obj['content'] = self.content
        return json.dumps(obj)


class User:
    def __init__(self, name, ws):
        self.name = name
        self.ws = ws

    def __eq__(self, other):
        if isinstance(other, User):
            return self.ws == other.ws
        elif isinstance(other, str):
            return self.ws == other
        return False

    def __hash__(self):
        return hash(self.name)

# The various kinds of messages you can send over the websocket
CHATROOMS = {}
USERS = {}

# Takes a Message.
async def register(msg, ws):
    if msg.sender in USERS:
        await ws.send(Message('REGFAILED', 'SERVER', content=msg.sender).serialize())
    else:
        USERS[msg.sender] = User(msg.sender, ws)
        # Return a list of available channels
        rooms = ['#' + name for name in CHATROOMS.keys()]
        roomlist = ' '.join(rooms)
        res = Message('REGISTERED', 'SERVER', content=f"Welcome to chat, {msg.sender}. Currently available rooms are: {roomlist}")
        await ws.send(res.serialize())

# Accept a Message and attempts to join a chat room, or create one if it doesn't exist.
async def join(msg, ws):
    user = USERS[msg.sender]
    chatname = msg.destination[1:]
    if chatname not in CHATROOMS:
        # Make said chatroom
        CHATROOMS[chatname] = ChatRoom(chatname)
    # Then join chatroom
    await CHATROOMS[chatname].join(user)

async def leave(msg, ws):
    user = USERS[msg.sender]
    chatname = msg.destination[1:]
    if chatname in CHATROOMS:
        await CHATROOMS[chatname].leave(user)
        if len(CHATROOMS[chatname].members) == 0:
            del CHATROOMS[chatname]

# Sends a message to a user or a chatroom.
async def message(msg, ws):
    target = msg.destination
    if target[0] == '@':
        # It's a user.
        if target[1:] in USERS:
            res = Message('MSG', sender=msg.sender, destination=target, content=msg.content)
            await USERS[target[1:]].ws.send(res.serialize())
        else:
            raise MessageFormatException(f"The user '{target}' does not exist.")
    elif target[0] == '#':
        # It's a channel
        if target[1:] in CHATROOMS:
            await CHATROOMS[target[1:]].broadcast(msg)
        else:
            raise MessageFormatException(f"The channel '{target}' does not exist.")
    else:
        raise MessageFormatException("Can only send to a @user or #chatroom.")

MSG_HANDLERS = {
    'REGISTER': register,
    'JOIN': join,
    'MSG': message,
    'LEAVE': leave
}

async def listen(websocket, path):
    async for message in websocket:
        print(message)
        try:
            msg = Message.loads(message, websocket)
            await MSG_HANDLERS[msg.msgtype](msg, websocket)
        except MessageFormatException as e:
            res = Message('ERROR', 'SERVER', content=e.value)
            await websocket.send(res.serialize())
        except KeyError:
            res = Message('ERROR', 'SERVER', content='Unknown message format')
            await websocket.send(res.serialize())

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(
        websockets.serve(listen, 'localhost', 8081))
    asyncio.get_event_loop().run_forever()

#!/usr/bin/python3
#
# simple web socket interface to Home Assistant ZHA web socket
# loops forever getting current zigbee devices and their attributes in JSON format

import json
import time

from websocket import create_connection

ACCESS_TOKEN = ""


ws = create_connection("ws://localhost:8123/api/websocket")

ws.send(json.dumps(
        {'type': 'auth',
         'access_token': ACCESS_TOKEN}
    ))

result =  ws.recv()

# print(result)

result =  ws.recv()

# print(result)

ident = 1

while True :
    ws.send(json.dumps(
            {'id': ident, 'type': 'zha/devices'}
        ))

    result =  ws.recv()

    print(result)

    # print(80 * "-")
    # result =  ws.recv()

    # print(result)

    time.sleep( 5 )

    ident = ident + 1


# # EOF

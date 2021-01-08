#!/usr/bin/python3
# ws02.py
# 202101081021
#
# simple web socket interface to Home Assistant ZHA web socket
# loops forever getting current zigbee devices and their attributes in JSON format

import sys
import json
import time

from websocket import create_connection

ACCESS_TOKEN = ""

ws = create_connection("ws://localhost:8123/api/websocket")

result =  ws.recv()

ws.send(json.dumps(
        {'type': 'auth',
         'access_token': ACCESS_TOKEN}
    ))

result =  ws.recv()

ident = 1

try:
    while True :
        ws.send(json.dumps(
                {'id': ident, 'type': 'zha/devices'}
            ))

        result =  ws.recv()

        print(result)

        # print(80 * "-")

        time.sleep( 5 )

        ident = ident + 1

except KeyboardInterrupt :
    sys.exit(0)


# # EOF

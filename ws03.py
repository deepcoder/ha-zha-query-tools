#!/usr/bin/python3
# ws03.py
# 202101080001 
#
# use home assistant web sockets to read zha zigbee devices current state and insert a record into SQLite database for each device found
# https://developers.home-assistant.io/docs/api/websocket/
# https://developers.home-assistant.io/docs/frontend/data
# https://github.com/dmulcahey/zha-network-card/blob/master/zha-network-card.js
# http://jsonviewer.stack.hu/

import json
import time
import sqlite3

from pathlib import Path
from websocket import create_connection

# Home Assistant Long-Lived Access Token
ACCESS_TOKEN = ""

# SQLite database file
DATABASE_FILE = "ws03.db"

# home assistant server IP address
HOME_ASSISTANT_IP = "192.168.1.100"

# number of seconds between queries to ZHA
QUERY_PERIOD_SECONDS = 5

# open database and create table if it does not exists
conn = sqlite3.connect(DATABASE_FILE)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS zha (retrieve_ts integer, ieee_address text, attributes json)")

# open web socket connection to Home Assistant server
ws = create_connection("ws://" + HOME_ASSISTANT_IP + ":8123/api/websocket")

# send authentication token to HA server
ws.send(json.dumps(
        {'type': 'auth',
         'access_token': ACCESS_TOKEN}
    ))

# we get two results back, first is connection ack
# second is authentication result
result =  ws.recv()

result =  ws.recv()

# we need a unique identifier to sent for each web socket request
ident = 1

# loop forever retrieving the current zha devices
try :
    while True :

        # this is the query to get the json list of current zigbee devices
        ws.send(json.dumps(
                {'id': ident, 'type': 'zha/devices'}
            ))

        # get the data string back from the web socket call
        result =  ws.recv()

        # record the time stamp of when the data was retrieved
        retrieve_time = int(time.time())

        # convert the string that came back to JSON
        json_result = json.loads(result)

        # retrieve each device that was returned
        for device in json_result["result"] :
            print(retrieve_time, device["ieee"], device)

            # insert the record for each device into the database table
            c.execute("insert into zha values (?, ?, ?)", \
                [retrieve_time, str(device["ieee"]), json.dumps(device)])
            conn.commit()


    # sleep until next query
        time.sleep( QUERY_PERIOD_SECONDS )

    # increment our unique web socket identifier
        ident = ident + 1

        # end loop forever

    except KeyboardInterrupt :
        conn.close()
        sys.exit(0)


# EOF

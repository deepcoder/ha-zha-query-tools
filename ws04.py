#!/usr/bin/python3
# ws04.py
# 202101081223   
#
# use home assistant web sockets to read zha zigbee devices current state and insert a record into SQLite database for each device found
# https://developers.home-assistant.io/docs/api/websocket/
# https://developers.home-assistant.io/docs/frontend/data
# https://github.com/dmulcahey/zha-network-card/blob/master/zha-network-card.js
# http://jsonviewer.stack.hu/
# https://github.com/websocket-client/websocket-client
# pip3 install websocket-client        0.53.0

import sys
import json
import time
import sqlite3
from rich.console import Console
# from deepdiff import DeepDiff
# from pprint import pprint
from datetime import datetime
from datetime import timedelta

from pathlib import Path
from websocket import create_connection

# rich print setup
# stops rich print from interpreting some parts of MAC addresses as emojis 
console = Console(emoji=False, color_system="256", highlight=False)

# Home Assistant Long-Lived Access Token
ACCESS_TOKEN = ""


# SQLite database file
DATABASE_FILE = "ws03.db"

# home assistant server IP address
HOME_ASSISTANT_IP = "localhost"

# number of seconds between queries to ZHA
QUERY_PERIOD_SECONDS = 5

# open database and create table if it does not exists
# conn = sqlite3.connect(DATABASE_FILE)
# c = conn.cursor()
# c.execute("CREATE TABLE IF NOT EXISTS zha (retrieve_ts integer, ieee_address text, attributes json)")

# open web socket connection to Home Assistant server
ws = create_connection("ws://" + HOME_ASSISTANT_IP + ":8123/api/websocket")
# connection ack
result =  ws.recv()
# send authentication token to HA server
ws.send(json.dumps(
        {'type': 'auth',
         'access_token': ACCESS_TOKEN}
    ))

# authentication result
result =  ws.recv()

# we need a unique identifier to sent as part of each web socket request
ident = 1

device_db = {}

# loop forever retrieving the current zha devices
try :
    while True :

        # this is the query to get the json list of current zigbee devices
        ws.send(json.dumps(
                {'id': ident, 'type': 'zha/devices'}
            ))

        # get the data string back from the web socket call
        result =  ws.recv()

        # record the time when the data was retrieved
        retrieve_time = datetime.now()

        # convert the string that came back to JSON
        json_result = json.loads(result)

        # device_db = {}

        # retrieve each device that was returned
        for device in json_result["result"] :
            # print(retrieve_time, device["ieee"], device)
            datetime_object = datetime.strptime(device["last_seen"], '%Y-%m-%dT%H:%M:%S')
            device_db[device["ieee"]] = {"user_given_name" : device["user_given_name"], "last_seen" : datetime_object}

            # print(type(device_db[device["ieee"]]), device_db[device["ieee"]])
            for neighbor in device["neighbors"] :
                if True :
                # if neighbor["relationship"] == "Child" :
                    # print(f"{retrieve_time:%H:%M:%S} ", end="")
                    # print(f"{device['device_type']:<11} ", end="")
                    # print(f"{str(device['user_given_name']):40.40} ", end="")

                    # delta_last_seen = retrieve_time - device_db.get(neighbor['ieee'], {'user_given_name': '****', 'last_seen': datetime_object})['last_seen']
                    # print(f" Last seen (minutes) :{delta_last_seen.seconds/60.0:6.1f} ", end="")
                    # print(f" Parent of : {neighbor['device_type']:<11} ", end="") 
                    # print(f"{device_db.get(neighbor['ieee'], {'user_given_name': '****', 'last_seen': ''})['user_given_name']:40.40}")


                    console.print(f"{retrieve_time:%H:%M:%S} ", end="")
                    console.print(f"{neighbor['device_type']:<11} ", end="") 
                    delta_last_seen = retrieve_time - device_db.get(neighbor['ieee'], {'user_given_name': '****', 'last_seen': datetime_object})['last_seen']
                    delta_last_seen_style = 'bold green on black'
                    if neighbor['device_type'] == "Router" and delta_last_seen > timedelta(minutes=1) :
                        delta_last_seen_style = 'bold yellow on black'
                    if neighbor['device_type'] == "Router" and delta_last_seen > timedelta(minutes=5) :
                        delta_last_seen_style = 'bold red on black'
                    if neighbor['device_type'] == "EndDevice" and delta_last_seen > timedelta(minutes=25) :
                        delta_last_seen_style = 'bold yellow on white'
                    if neighbor['device_type'] == "EndDevice" and delta_last_seen > timedelta(minutes=35) :
                        delta_last_seen_style = 'bold red on white'
                    console.print(f" Last seen (minutes) ", end="")
                    console.print(f"{delta_last_seen.seconds/60.0:6.1f} ", style=delta_last_seen_style, end="")
                    console.print(f"{str(device_db.get(neighbor['ieee'], {'user_given_name': '****', 'last_seen': ''})['user_given_name']):40.40}", end="")
                    console.print(f" Neighbor of : {str(device['user_given_name']):40.40} ")

        console.print(40*"-")




            # insert the record for each device into the database table
            # c.execute("insert into zha values (?, ?, ?)", \
            #     [retrieve_time, str(device["ieee"]), json.dumps(device)])
            # conn.commit()

    # sleep until next query
        time.sleep( QUERY_PERIOD_SECONDS )

    # increment our unique web socket identifier
        ident = ident + 1

        # end loop forever

except KeyboardInterrupt :
    # conn.close()
    ws.close()
    sys.exit(0)


# EOF

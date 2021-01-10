#!/usr/bin/python3
# ws04.py

PROGRAM_NAME = "ws04"
VERSION_MAJOR = "1"
VERSION_MINOR = "1"
WORKING_DIRECTORY = ""

# 202101091421   
#
# use home assistant web sockets to read zha zigbee devices current state and insert a record into SQLite database for each device found
# https://developers.home-assistant.io/docs/api/websocket/
# https://developers.home-assistant.io/docs/frontend/data
# https://github.com/dmulcahey/zha-network-card/blob/master/zha-network-card.js
# http://jsonviewer.stack.hu/
# https://github.com/websocket-client/websocket-client
# pip3 install websocket-client        0.53.0

import sys

# check version of python
if not (sys.version_info.major == 3 and sys.version_info.minor >= 7):
    print("This script requires Python 3.7 or higher!")
    print("You are using Python {}.{}.".format(sys.version_info.major, sys.version_info.minor))
    sys.exit(1)
#print("{} {} is using Python {}.{}.".format(PROGRAM_NAME, VERSION_MAJOR + "." + VERSION_MINOR, sys.version_info.major, sys.version_info.minor))


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

import logging
import logging.handlers

# Logging setup

# select logging level
logging_level_file = logging.getLevelName('INFO')
#level_file = logging.getLevelName('DEBUG')
logging_level_rsyslog = logging.getLevelName('INFO')

# log to both a local file and to a rsyslog server
LOG_FILENAME = PROGRAM_NAME + '.log'
LOG_RSYSLOG = ('192.168.2.5', 514)

root_logger = logging.getLogger()

#set loggers

# file logger
handler_file = logging.handlers.RotatingFileHandler(LOG_FILENAME, backupCount=5)
handler_file.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
handler_file.setLevel(logging_level_file)

root_logger.addHandler(handler_file)

# Roll over file logs on application start
handler_file.doRollover()

# rsyslog handler
handler_rsyslog = logging.handlers.SysLogHandler(address = LOG_RSYSLOG)
handler_rsyslog.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
handler_rsyslog.setLevel(logging_level_rsyslog)

root_logger.addHandler(handler_rsyslog)

my_logger = logging.getLogger(PROGRAM_NAME)
my_logger.setLevel(logging_level_file)


# rich print setup
# stops rich print from interpreting some parts of MAC addresses as emojis 
console = Console(emoji=False, color_system="256", highlight=False)

# Home Assistant Long-Lived Access Token
ACCESS_TOKEN = ""

# SQLite database file
DATABASE_FILE = PROGRAM_NAME + ".db"

# home assistant server IP address
HOME_ASSISTANT_IP = "localhost"

# number of seconds between queries to ZHA
QUERY_PERIOD_SECONDS = 5

def main():

    my_logger.info("Program start : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)

 
    # open database and create table if it does not exists
    sql_conn = sqlite3.connect(DATABASE_FILE)
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute("CREATE TABLE IF NOT EXISTS zha (retrieve_ts integer, ieee_address text, user_given_name text, delta_last_seen real, nwk int, lqi int, rssi int, available text, attributes json)")

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


    # do one processing pass on the first ZHA web socket call to populate the devices
    SETUP_PASS = True

    # we will create a database (dictionary) of zigbee devices that are returned by the web socket call to ZHA
    # we keep appending on new entries with each web socket call
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

            if SETUP_PASS :
                console.print("First ZHA data retrieval pass, setting up database")

            # retrieve each device that was returned in current web socket call
            for device in json_result["result"] :
                # print(retrieve_time, device["ieee"], device)
                datetime_object = datetime.strptime(device["last_seen"], '%Y-%m-%dT%H:%M:%S')
                if device["available"] :
                    device_status = "true"
                else :
                    device_status = "false"

                # add a record to our database (dictionary) of zigbee devices on the network
                device_db[device["ieee"]] = {"user_given_name" : device["user_given_name"], \
                    "last_seen" : datetime_object, \
                    "nwk" : device["nwk"], \
                    "lqi" : device["lqi"], \
                    "rssi" : device["rssi"], \
                    "available" : device_status \
                    }

                # this is a 'fake' record of database, so we can retrieve 'default' values from it, if the key does not exist
                device_db_template = {"user_given_name" : "****", \
                    "last_seen" : datetime(1970, 1, 1, 0, 0, 0, 0), \
                    "nwk" : -1, \
                    "lqi" : -1, \
                    "rssi" : 0, \
                    "available" : "unk" \
                    }

                # iterate thru each neighbor of the device returned
                # so basically we are going to display / find / 'pull up' / extract the network of devices by the neighbor connections
                for neighbor in device["neighbors"] :

                    # don't display or record in db anything for the first web socket, we is this pass just to populate in memory database
                    if not SETUP_PASS :
                        # we can look at all neighbors of this device, or only the end devices
                        if True :
                        # if neighbor["relationship"] == "Child" :
     
                            console.print(f"{retrieve_time:%H:%M:%S} ", end="")
                            console.print(f"{neighbor['device_type']:<11} ", end="") 

                            # devices available seems to be set at some point by ZHA to false if the device is no visable on network
                            device_available = device_db.get(neighbor['ieee'], device_db_template)['available']
                            if device_available == "false" :
                                style = 'bold red on black'
                            else :
                                style = 'bold green on black'
                            # hack for coordinator, it thinks it is off line, which could not be, display it as online
                            if neighbor['device_type'] == "Coordinator" :
                                device_available = "true"
                                style = 'bold green on black'

                            console.print(f" Online : ", end="")
                            console.print(f"{device_available:<5} ", style=style, end="")

                            # calculate the time delta from this retrieve from ZHA web socket to when this devices was last seen, decimal minutes
                            delta_last_seen = retrieve_time - device_db.get(neighbor['ieee'], device_db_template)['last_seen']
                            delta_last_seen_style = 'bold green on black'
                            if neighbor['device_type'] == "Router" and delta_last_seen > timedelta(minutes=1) :
                                delta_last_seen_style = 'bold yellow on black'
                            if neighbor['device_type'] == "Router" and delta_last_seen > timedelta(minutes=5) :
                                delta_last_seen_style = 'bold red on black'
                            if neighbor['device_type'] == "EndDevice" and delta_last_seen > timedelta(minutes=25) :
                                delta_last_seen_style = 'bold yellow on white'
                            if neighbor['device_type'] == "EndDevice" and delta_last_seen > timedelta(minutes=35) :
                                delta_last_seen_style = 'bold red on white'
                            console.print(f" Last seen (min) ", end="")
                            device_delta_last_seen = delta_last_seen.seconds/60.0
                            console.print(f"{device_delta_last_seen:6.1f} ", style=delta_last_seen_style, end="")

                            # display the device name
                            console.print(f"{str(device_db.get(neighbor['ieee'], device_db_template)['user_given_name']):40.40}", end="")

                            # display the name of the devices neighbor, end devices are the only device type that will ONLY ONE neighbor (??)
                            peer_available = device_db.get(neighbor['ieee'], device_db_template)['available']
                            if peer_available == "false" :
                                style = 'bold red'
                            else :
                                style = 'bold white'
                            console.print(f" {neighbor['relationship']:14.14} of : ", end="")
                            console.print(f"{str(device['user_given_name']):40.40} ", style=style)

                            # insert the record for each device into the database table
                            sql_cursor.execute("insert into zha values (?, ?, ?, ?, ?, ?, ?, ?, ?)", \
                                [retrieve_time, \
                                str(neighbor["ieee"]), \
                                str(device_db.get(neighbor['ieee'], device_db_template)['user_given_name']), \
                                device_delta_last_seen, \
                                device_db.get(neighbor['ieee'], device_db_template)['nwk'], \
                                device_db.get(neighbor['ieee'], device_db_template)['lqi'], \
                                device_db.get(neighbor['ieee'], device_db_template)['rssi'], \
                                device_available, \
                                json.dumps(device)])
                            sql_conn.commit()

            console.print(40*"-")


            # reset of 1st pass thru web socket retreval flag
            SETUP_PASS = False

            # sleep until next query
            time.sleep( QUERY_PERIOD_SECONDS )

            # increment our unique web socket identifier
            ident = ident + 1

            # end loop forever

    except KeyboardInterrupt :
        # proper exit
        sql_conn.close()
        ws.close()
        my_logger.info("Program end : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)
        sys.exit(0)

if __name__ == '__main__':
   main()


# EOF

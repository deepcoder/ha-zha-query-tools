#!/usr/bin/python3
# ws08.py

PROGRAM_NAME = "ws08"
VERSION_MAJOR = "1"
VERSION_MINOR = "1"
WORKING_DIRECTORY = ""

# 202101181453      
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


import traceback
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
# if you do not have a rsyslog server, don't be concerned, program will log locally
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
handler_rsyslog.setFormatter(logging.Formatter(fmt='%(name)s %(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

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

# flag to indicate of the raw web socket json results should be kept in a .json file
RAW_JSON_KEEP = False

def main():

    my_logger.info("Program start : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)


    if len(ACCESS_TOKEN) == 0 :
        print("Error : HA Long-Lived token not defined in variable ACCESS_TOKEN")
        my_logger.error("Error : HA Long-Lived token not defined in variable ACCESS_TOKEN")
        sys.exit(1)
     
    # open database and create table if it does not exists
    sql_conn = sqlite3.connect(DATABASE_FILE)
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute("CREATE TABLE IF NOT EXISTS zha (packet integer, retrieve_ts integer, neighbor_address text, neighbor_given_name text, neighbor_lqi int, neighbor_rssi int, neighbor_delta_last_seen real, neighbor_last_seen_ts integer, neighbor_device_type text, neighbor_available text, neighbor_depth int, neighbor_relationship text, peer_nwk int, peer_lqi int, peer_rssi int, peer_available text, peer_address text, peer_given_name text)")

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

    neighbor_db = {}

    # initialize dump file of raw received json
    if RAW_JSON_KEEP :
        f = open(PROGRAM_NAME + '.json', 'w')
        f.write('[\n')
        f.close()

    # loop forever retrieving the current zha devices
    try :
        while True :

            try :
                # this is the query to get the json list of current zigbee devices
                ws.send(json.dumps(
                        {'id': ident, 'type': 'zha/devices'}
                    ))

                # get the data string back from the web socket call
                result =  ws.recv()

                # record the time when the data was retrieved
                retrieve_time = datetime.now().replace(microsecond=0)

                # convert the string that came back to JSON
                json_result = json.loads(result)

                # append the current web socket result to the raw json dump file
                if RAW_JSON_KEEP :
                    f = open(PROGRAM_NAME + '.json', 'a')
                    f.write(result + ',\n')
                    f.close()

            except Exception as e:
                print("Error : Unable to execute web socket call.")
                print(traceback.format_exc())
                my_logger.error("Error : Unable to execute web socket call : " + traceback.format_exc())
                continue
#               sys.exit(1)


            # if we did not get a success result back from service call, log the face and do not process results, cause there are none
            if json_result['success'] == False :
                my_logger.error("Error : Did not receive a success indicator from web socket call : " + result)
            # if we did receive a indication of a successful web socket call, process the results
            else :

                if SETUP_PASS :
                    console.print("First ZHA data retrieval pass, setting up database")

                # retrieve each device that was returned in current web socket call
                for device in json_result["result"] :
                    # print(retrieve_time, device["ieee"], device)
                    last_seen_ts = datetime.strptime(device["last_seen"], '%Y-%m-%dT%H:%M:%S')
                    if device["available"] :
                        device_status = "true"
                    else :
                        device_status = "false"

                    # add a record to our database (dictionary) of zigbee devices on the network

                    if str(device["lqi"]) == "None" :
                        device_lqi = 0
                    else :
                        device_lqi = int(device["lqi"])
 
                    if str(device["rssi"]) == "None" :
                        device_rssi = 0
                    else :
                        device_rssi = int(device["rssi"])

                    # if we already have a record for this device, then keep it current recording of whether is has
                    # been found to be the neighbor of another device on network
                    if device["ieee"] in device_db :
                        is_neigh = device_db[device["ieee"]]["is_neighbor"]
                    else :
                        is_neigh = "false"

                    # update or add the current info for the device retrieved from the ZHA web socket call
                    device_db[device["ieee"]] = {"user_given_name" : device["user_given_name"], \
                        "last_seen" : last_seen_ts, \
                        "device_type" : device["device_type"], \
                        "nwk" : device["nwk"], \
                        "lqi" : device_lqi, \
                        "rssi" : device_rssi, \
                        "available" : device_status, \
                        "is_neighbor" : is_neigh \
                        }

                    # this is a 'fake' record of database, so we can retrieve 'default' values from it, if the key does not exist
                    device_db_template = {"user_given_name" : "", \
                        "last_seen" : retrieve_time, \
                        "device_type" : "*", \
                        "nwk" : -1, \
                        "lqi" : -1, \
                        "rssi" : 0, \
                        "available" : "unk", \
                        "is_neighbor" : "false" \
                        }


                    # if the device has NO neighbors, then create a fake neighbor, these are end devices

                    if len(device['neighbors']) == 0 :
                        device['neighbors'].append({"device_type" : "*", \
                            "rx_on_when_idle" : "unk", \
                            "relationship" : "none", \
                            "extended_pan_id" : "cc:cc:cc:cc:00:00:00:00", \
                            "ieee" : "00:00:00:00:00:00:00:00", \
                            "nwk" : "0x0000", \
                            "permit_joining" : "unk", \
                            "depth" : "0", \
                            "lqi" : device["lqi"] \
                            })


                    # iterate thru each neighbor of the device returned
                    # so basically we are going to display / find / 'pull up' / extract the network of devices by the neighbor connections
                    for neighbor in device['neighbors'] :

                        # check if the current device is found to be the neighor in another device, if not, this is an indicator
                        # if we loop thru all devices and all the neighbors for each device and this stays 'false' then the device
                        # is not in any other devices neighbor table, so we will display it at the end as a off line drive
                        # this is complicated!!! and not sure I have it right, some how a 'parent' device can NOT appear in any other
                        # 'parent' device neighbor table, however have the 'peer' in it's neighbor table 
                        if neighbor['ieee'] in device_db :
                            # indicates that the current device is found to be the neighbor of another device
                            device_db[neighbor['ieee']]['is_neighbor'] = 'true'

                        neighbor_db[device['ieee'] + ':' + neighbor['ieee']] = {'lqi' : neighbor['lqi'] \
                            }
                        # print(neighbor_db[device['ieee'] + ':' + neighbor['ieee']])
                        # this is a 'fake' record of database, so we can retrieve 'default' values from it, if the key does not exist
                        neighbor_db_template = {'lqi' : 0, \
                            }


                        # don't display or record in db anything for the first web socket, we is this pass just to populate in memory database
                        if not SETUP_PASS :
                            # we can look at all neighbors of this device, or only the end devices
                            if True :
                            # if neighbor["relationship"] == "Child" :
         
                                console.print(f"{retrieve_time:%H:%M:%S} ", style = 'white', end="")
                                console.print(f"{neighbor['device_type']:1.1} ", style = 'bold white', end="") 

                                # devices available seems to be set at some point by ZHA to false if the device is no visable on network
                                neighbor_available = device_db.get(neighbor['ieee'], device_db_template)['available']
                                if neighbor_available == "false" :
                                    av_text = "F"
                                    style = 'bold red on black'
                                else :
                                    av_text = "T"
                                    style = 'bold green on black'
                                # hack for coordinator, it thinks it is off line, which could not be, display it as online
                                if neighbor['device_type'] == "Coordinator" :
                                    neighbor_available = "true"
                                    av_text = "T"
                                    style = 'bold green on black'

                                console.print(f"Online ", style = 'white', end="")
                                console.print(f"{av_text:1}", style=style, end="")

                                # calculate the time delta from this retrieve from ZHA web socket to when this devices was last seen, decimal minutes
                                delta_last_seen = retrieve_time - device_db.get(neighbor['ieee'], device_db_template)['last_seen']

                                # if this is a end device then calculate it's last seen delta from it's device record, not a neighbor record
                                if neighbor['device_type'] == "*" :
                                    delta_last_seen = retrieve_time - device_db.get(device['ieee'], device_db_template)['last_seen']

                                delta_last_seen_style = 'bold green on black'
                                if neighbor['device_type'] == "Router" and delta_last_seen > timedelta(minutes=1) :
                                    delta_last_seen_style = 'bold yellow on black'
                                if neighbor['device_type'] == "Router" and delta_last_seen > timedelta(minutes=5) :
                                    delta_last_seen_style = 'bold red on black'
                                if (neighbor['device_type'] == "EndDevice" or neighbor['device_type'] == "*") and delta_last_seen > timedelta(minutes=25) :
                                    delta_last_seen_style = 'black on yellow'
                                if (neighbor['device_type'] == "EndDevice" or neighbor['device_type'] == "*") and delta_last_seen > timedelta(minutes=35) :
                                    delta_last_seen_style = 'black on red'
                                console.print(f" Last seen ", style = 'white', end="")
                                device_delta_last_seen = delta_last_seen.seconds/60.0
                                console.print(f"{device_delta_last_seen:6.1f}", style=delta_last_seen_style, end="")

                                # display the device name

                                neighbor_name = str(device_db.get(neighbor['ieee'], device_db_template)['user_given_name'])
                                neighbor_type = str(device_db.get(neighbor['ieee'], device_db_template)['device_type'])

                                if neighbor_type == "Coordinator" :
                                    console.print(f" {'Coordinator':38.38} ", style = 'white', end="")
                                else:
                                    console.print(f" {neighbor_name:38.38} ", style = 'white', end="")

                                # 'up link' from neighbor to peer, end devices will not have this link

                                # lqi_display = int(neighbor['lqi'])
                                key = neighbor['ieee'] + ':' + device['ieee']
                                lqi_display = int(neighbor_db.get(key, neighbor_db_template)['lqi'])

                                style = 'bold green on black'
                                if lqi_display < 170 :
                                    style = 'bold yellow on black'
                                if lqi_display < 85 :
                                    style = 'bold red on black'

                                # if this neighbor device is listed as 'off line' display unknown for LQI and RSSI connections to this neighbor
                                # which if were true, then the network would be down
                                neighbor_available = device_db.get(neighbor['ieee'], device_db_template)['available']

                                if neighbor_available == "false" and device_db.get(neighbor['ieee'], device_db_template)['device_type'] != "Coordinator" :
                                    console.print(f"{'unk':4}", style='bold red on black', end="")
                                elif lqi_display == 0 :
                                    console.print(f"{'na':>3}", style='bold red on black', end="")
                                else :
                                    console.print(f"{lqi_display:3}", style=style, end="")

                                # this rssi is the one reported by the neighbor device
                                rssi_display = int(device_db.get(neighbor['ieee'], device_db_template)['rssi'])
                                style = 'bold green on black'
                                if rssi_display < -70 :
                                    style = 'bold red on black'
                                if rssi_display < -60 :
                                    style = 'bold yellow on black'
 
                                if neighbor_available == "false" and device_db.get(neighbor['ieee'], device_db_template)['device_type'] != "Coordinator" :
                                    console.print(f"{'unk':>4.4} ", style='bold red on black', end="")
                                else :
                                    console.print(f" {rssi_display:4} ", style=style, end="")


                                # peer

                                lqi_display = int(neighbor['lqi'])

                                # key = neighbor['ieee'] + ':' + device['ieee']
                                # lqi_display = int(neighbor_db.get(key, neighbor_db_template)['lqi'])

                                style = 'bold green on black'
                                if lqi_display < 170 :
                                    style = 'bold yellow on black'
                                if lqi_display < 85 :
                                    style = 'bold red on black'

                                # if this 'peer' device is listed as 'off line' display unknown for LQI and RSSI connections to this neighbor
                                # which if were true, then the network would be down
                                peer_available = device_db.get(device['ieee'], device_db_template)['available']

                                if peer_available == "false" and device_db.get(device['ieee'], device_db_template)['device_type'] != "Coordinator" :
                                    console.print(f"{'unk':4}", style='bold red on black', end="")
                                else :
                                    console.print(f"{lqi_display:3}", style=style, end="")

                                # this rssi is the one reported by the peer device
                                rssi_display = int(device_db.get(device['ieee'], device_db_template)['rssi'])
                                style = 'bold green on black'
                                if rssi_display < -70 :
                                    style = 'bold red on black'
                                if rssi_display < -60 :
                                    style = 'bold yellow on black'
 
                                if peer_available == "false" and device_db.get(device['ieee'], device_db_template)['device_type'] != "Coordinator" :
                                    console.print(f"{'unk':>4.4}", style='bold red on black', end="")
                                else :
                                    console.print(f" {rssi_display:4}", style=style, end="")

                                # display then name of the device 'peer', remember we are stepping thru each 'neighbor' of this device
                                # to display, so these are all the devices which are 'parents', end devices do not have neighbors, so
                                # no end devices will appear in this column.

                                console.print(f" {neighbor['relationship']:14.14} of ", style = 'white', end="")

                                # if this 'parent' device is listed as 'off line' color it red, the coordinator seems to always be 'off line'
                                # which if were true, then the network would be down
                                style = 'white'
                                if device_db[device['ieee']]["device_type"] != "Coordinator" and peer_available == "false" :
                                    style = 'bold red'

                                # if the peer is not found to be a neighbor of any other device then flag
                                # device_db[neighbor['ieee']]['is_neighbor']
                                if device_db[device['ieee']]['is_neighbor'] == "false" :
                                    style = "bold red on black"

                                # so far, it does not look like the Coordinator can be given a 'user given name' so that is always 'none'
                                # so for the coordinator, display the device type of 'Coordinator'
                                if device_db[device['ieee']]["device_type"] == "Coordinator" :
                                    console.print(f"{'Coordinator':38.38} ", style=style)
                                else:
                                    console.print(f"{str(device['user_given_name']):38.38} ", style=style)

                                # insert the record for status of each device into the database table for this web socket call
                                # note we are pulling out the devices by the neighbor each device returned this call
                                # we write the web socket call identifier out for information, we decrement by 1 to align with json
                                # entities starting at zero, but our first web socket call for real data starts at 1
                                # NOTE: the last_seen time delta and timestamp, may be from prior record, not this web socket call
                                # because if we have not processed the main entry for this device on this web socket call
                                # these value remain from the prior web socket call, this is an aberation of walking thru
                                # the devices by their neighbor relationship. Is there a way to correct this????

                                key = neighbor['ieee'] + ':' + device['ieee']
                                lqi_display = int(neighbor_db.get(key, neighbor_db_template)['lqi'])

                                sql_cursor.execute('insert into zha values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', \
                                    [int(json_result['id']) - 1, \
                                    retrieve_time, \
                                    str(neighbor['ieee']), \
                                    str(device_db.get(neighbor['ieee'], device_db_template)['user_given_name']), \
                                    lqi_display, \
                                    device_db.get(neighbor['ieee'], device_db_template)['rssi'], \
                                    device_delta_last_seen, \
                                    device_db.get(neighbor['ieee'], device_db_template)['last_seen'], \
                                    neighbor['device_type'], \
                                    neighbor_available, \
                                    neighbor['depth'], \
                                    neighbor['relationship'], \
                                    device['nwk'], \
                                    neighbor['lqi'], \
                                    device_db.get(device['ieee'], device_db_template)['rssi'], \
                                    peer_available, \
                                    str(device['ieee']), \
                                    str(device['user_given_name']) ])
                                sql_conn.commit()


                # display a line for all the device which are offline, the coordinator seems to put itself 'offline', so we
                # ignore if coordinator says it is 'offline', if that were case, network would be 'offline'
                if not SETUP_PASS :
                    for ii in device_db :
                        # print(device_db[ii])
                        if device_db[ii]["available"] == "false" and device_db[ii]["device_type"] != "Coordinator" :
                            console.print(f"{retrieve_time:%H:%M:%S} ", style = 'white', end="")
                            console.print(f"{device_db[ii]['device_type']:1.1} ", style = 'bold white', end="") 

                            # devices available seems to be set at some point by ZHA to false if the device is no visable on network
                            device_available = device_db[ii]['available']
                            if device_available == "false" :
                                av_text = "F"
                                style = 'bold red on black'
                            else :
                                av_text = "T"
                                style = 'bold green on black'
                            # hack for coordinator, it thinks it is off line, which could not be, display it as online
                            # if neighbor['device_type'] == "Coordinator" :
                            #     device_available = "true"
                            #     av_text = "T"
                            #     style = 'bold green on black'

                            console.print(f" Online : ", style = 'white', end="")
                            console.print(f"{av_text:1}", style=style, end="")

                            # calculate the time delta from this retrieve from ZHA web socket to when this devices was last seen, decimal minutes
                            delta_last_seen = retrieve_time - device_db[ii]['last_seen']
                            delta_last_seen_style = 'bold green on black'
                            if device_db[ii]['device_type'] == "Router" and delta_last_seen > timedelta(minutes=1) :
                                delta_last_seen_style = 'bold yellow on black'
                            if device_db[ii]['device_type'] == "Router" and delta_last_seen > timedelta(minutes=5) :
                                delta_last_seen_style = 'bold red on black'
                            if neighbor['device_type'] == "EndDevice" and delta_last_seen > timedelta(minutes=25) :
                                delta_last_seen_style = 'black on yellow'
                            if device_db[ii]['device_type'] == "EndDevice" and delta_last_seen > timedelta(minutes=35) :
                                delta_last_seen_style = 'black on red'
                            console.print(f" Last seen (min) ", style = 'white', end="")
                            device_delta_last_seen = delta_last_seen.seconds/60.0
                            console.print(f"{device_delta_last_seen:6.1f}", style=delta_last_seen_style, end="")

                            # display the peer device name

                            peer_name = str(device_db[ii]['user_given_name'])
                            peer_type = str(device_db[ii]['device_type'])

                            style = "white"
                            if device_db[device['ieee']]['is_neighbor'] == "false" :
                                style = "red"

                            if peer_type == "Coordinator" :
                                console.print(f" {'Coordinator':40.40} ", style = style, end="")
                            else:
                                console.print(f" {peer_name:40.40} ", style = style, end="")

                            console.print(f"{'unk  unk':>8.8}", style='bold red on black')

                console.print(40*"-")


                # reset of 1st pass thru web socket retreval flag
                SETUP_PASS = False

                # sleep until next query
                time.sleep( QUERY_PERIOD_SECONDS )

                # end if successful web socket packet received

            # increment our unique web socket identifier
            ident = ident + 1

            # end loop forever

    except KeyboardInterrupt :
        # proper exit
        sql_conn.close()
        ws.close()

        # finalize dump file of raw received json by putting a proper end of json structure in place
        if RAW_JSON_KEEP :
            f = open(PROGRAM_NAME + '.json', 'a')
            f.write(']\n')
            f.close()

        my_logger.info("Program end : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)
        sys.exit(0)

    except :
        my_logger.critical("Unhandled error : " + traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
   main()


# EOF

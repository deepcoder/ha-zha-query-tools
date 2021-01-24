#!/usr/bin/python3
# zha_ws.py

PROGRAM_NAME = "zha_ws"
VERSION_MAJOR = "1"
VERSION_MINOR = "1"
WORKING_DIRECTORY = "/home/user/ha-websocket/"

# 202101231638        
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
import yaml
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
logging_level_file = logging.getLevelName('DEBUG')
#level_file = logging.getLevelName('DEBUG')
logging_level_rsyslog = logging.getLevelName('INFO')

# set local logging
LOG_FILENAME = PROGRAM_NAME + '.log'

root_logger = logging.getLogger()

# set loggers
# file logger
handler_file = logging.handlers.RotatingFileHandler(LOG_FILENAME, backupCount=5)
handler_file.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
handler_file.setLevel(logging_level_file)

root_logger.addHandler(handler_file)

# Roll over file logs on application start
handler_file.doRollover()

# configure highest level combo logger, this is what we log to and it automagically goes to the log receivers that we have configured
# logging.getLogger("timeloop").setLevel(logging.CRITICAL)
my_logger = logging.getLogger(PROGRAM_NAME)

# read yaml config file 
try :
    raw_yaml = Path(WORKING_DIRECTORY + PROGRAM_NAME + ".yaml").read_text()
except Exception as e:
    my_logger.error("Error : configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " not found.")
    sys.exit(1)

try : 
    PROGRAM_CONFIG = yaml.load(Path(WORKING_DIRECTORY + PROGRAM_NAME + ".yaml").read_text(), Loader=yaml.FullLoader)
except Exception as e :
    my_logger.error("Error : YAML syntax problem in configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " .")
    sys.exit(1)


# Logging setup
# read debug from YAML config file
# simple key value pair in YAML file : debug_level: "level" and set debug level
DEBUG_LEVEL = PROGRAM_CONFIG.get("debug_level", "")
if ( DEBUG_LEVEL == "" ) :
    DEBUG_LEVEL = "INFO"

logging_level_file = logging.getLevelName(DEBUG_LEVEL)
handler_file.setLevel(logging_level_file)


# read rsyslog info from YAML config file
# simple key value pair in YAML file : rsyslog: "<rsyslog server info>"
# simple string
RSYSLOG_SERVER = PROGRAM_CONFIG.get("rsyslog", "")
LOG_RSYSLOG = (RSYSLOG_SERVER, 514)

# rsyslog handler, if an IP address was specified in the YAML config file that configure to log to a RSYSLOG server
if (RSYSLOG_SERVER != "") :
    handler_rsyslog = logging.handlers.SysLogHandler(address = LOG_RSYSLOG)
    handler_rsyslog.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    handler_rsyslog.setLevel(logging_level_rsyslog)
    root_logger.addHandler(handler_rsyslog)


logging_level_file = logging.getLevelName('DEBUG')
root_logger.setLevel(logging_level_file)

# number of seconds between queries to ZHA
QUERY_PERIOD_SECONDS = PROGRAM_CONFIG.get("check_interval", 5)

# Home Assistant Long-Lived Access Token
ACCESS_TOKEN = PROGRAM_CONFIG.get("access_token", "")

if (ACCESS_TOKEN == "") :
    my_logger.error("Error : Home Assistant Long Lived Access Token Missing.")
    sys.exit(1)

# SQLite database file
DATABASE_FILE = PROGRAM_NAME + ".db"

# home assistant server IP address
HOME_ASSISTANT_IP = PROGRAM_CONFIG.get("ha_ip", "localhost:8123")

# flag to indicate of the raw web socket json results should be kept in a .json file
RAW_JSON_KEEP = PROGRAM_CONFIG.get("raw_json_keep", False)

# rich print setup
# stops rich print from interpreting some parts of MAC addresses as emojis 
console = Console(emoji=False, color_system="256", highlight=False)


# set up web socket call to Home Assistant
def ws_init() :

    not_connected = True

    while not_connected :
        try :
            # open web socket connection to Home Assistant server
            ha_web_socket_handle = create_connection("ws://" + HOME_ASSISTANT_IP + "/api/websocket")
            # connection ack
            result =  ha_web_socket_handle.recv()
            # send authentication token to HA server
            ha_web_socket_handle.send(json.dumps(
                    {'type': 'auth',
                     'access_token': ACCESS_TOKEN}
                ))

            # authentication result
            result =  ha_web_socket_handle.recv()

            # we need a unique identifier to sent as part of each web socket request
            ws_identifier = 1

            not_connected = False

        except Exception as e:
            print("Error : Unable connect to web socket, retrying.")
            print(traceback.format_exc())
            my_logger.error("Error : Unable connect to web socket, retrying : " + traceback.format_exc())
            # pause
            time.sleep( QUERY_PERIOD_SECONDS * 5)
            continue

    return ha_web_socket_handle, ws_identifier


def main():

    my_logger.info("Program start : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)

    my_logger.info("Web socket call interval (seconds) : " + str(QUERY_PERIOD_SECONDS))


    if len(ACCESS_TOKEN) == 0 :
        print("Error : HA Long-Lived token not defined in variable ACCESS_TOKEN")
        my_logger.error("Error : HA Long-Lived token not defined in variable ACCESS_TOKEN")
        sys.exit(1)
     
    # open database and create tables if they do not exists
    sql_conn = sqlite3.connect(DATABASE_FILE)
    sql_cursor = sql_conn.cursor()
    sql_cursor.execute("CREATE TABLE IF NOT EXISTS zha (packet integer, retrieve_ts integer, neighbor_address text, neighbor_lqi int, neighbor_rssi int, neighbor_delta_last_seen real, neighbor_last_seen_ts integer, neighbor_device_type text, neighbor_available text, neighbor_depth int, neighbor_relationship text, peer_nwk int, peer_lqi int, peer_rssi int, peer_available text, peer_address text)")
    sql_cursor.execute("CREATE TABLE IF NOT EXISTS zha_device_name (device_address text primary key, device_given_name text)")

    # connect to Home Assistant Web Socket Interface
    ws, ident = ws_init()

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
                # pause
                time.sleep( QUERY_PERIOD_SECONDS * 5)
                # reconnect to Home Assistant Web Socket interface
                ws, ident = ws_init()
                continue
#               sys.exit(1)


            # if we did not get a success result back from service call, log the face and do not process results, cause there are none
            if json_result['success'] == False :
                my_logger.error("Error : Did not receive a success indicator from web socket call : " + result)
                # pause
                time.sleep( QUERY_PERIOD_SECONDS * 5)
            # if we did receive a indication of a successful web socket call, process the results
            else :

                if SETUP_PASS :
                    console.print("First ZHA data retrieval pass, setting up database")


                # remove from device database devices that do not show up in current retrieval from ZHA web socket call

                for ii in device_db :
                    device_found = False
                    for jj in json_result["result"] :
                        if jj["ieee"] in device_db :
                            device_found = True
                    if not device_found :
                        print("removing : " + ii["ieee"])
                        device_db.pop(ii["ieee"], "err")

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
                            "lqi" : device_lqi \
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
                                # print(neighbor)
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

                                sql_cursor.execute('insert into zha values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', \
                                    [int(json_result['id']) - 1, \
                                    retrieve_time, \
                                    str(neighbor['ieee']), \
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
                                    str(device['ieee']) ])
                                sql_conn.commit()

                                sql_cursor.execute('insert or ignore into zha_device_name values (?, ?)', \
                                    [str(neighbor['ieee']), \
                                    str(device_db.get(neighbor['ieee'], device_db_template)['user_given_name']) ])
                                sql_cursor.execute('''update zha_device_name set device_given_name = ? where device_address = ?''', \
                                    (str(neighbor['ieee']), \
                                    str(device_db.get(neighbor['ieee'], device_db_template)['user_given_name']) ))
                                sql_conn.commit()


                # display a line for all the device which are offline, the coordinator seems to put itself 'offline', so we
                # ignore if coordinator says it is 'offline', if that were case, network would be 'offline'
                if not SETUP_PASS :
                    for ii in device_db :
                        # print(device_db[ii])
                        if device_db[ii]["available"] == "false" and device_db[ii]["device_type"] != "Coordinator" :
                            console.print(f"{retrieve_time:%H:%M:%S} ", style = 'white', end="")
                            console.print(f"{device_db[ii]['device_type']:1.1}", style = 'bold white', end="") 

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

                            console.print(f" Online ", style = 'white', end="")
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
                            console.print(f" Last seen ", style = 'white', end="")
                            device_delta_last_seen = delta_last_seen.seconds/60.0
                            console.print(f"{device_delta_last_seen:6.1f}", style=delta_last_seen_style, end="")

                            # display the peer device name

                            peer_name = str(device_db[ii]['user_given_name'])
                            peer_type = str(device_db[ii]['device_type'])

                            style = "white"
                            if device_db[device['ieee']]['is_neighbor'] == "false" :
                                style = "red"

                            if peer_type == "Coordinator" :
                                console.print(f" {'Coordinator':38.38} ", style = style, end="")
                            else:
                                console.print(f" {peer_name:38.38} ", style = style, end="")

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

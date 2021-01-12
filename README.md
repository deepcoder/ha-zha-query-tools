# ha-zha-query-tools
Python tools to get zigbee device info from Home Assistant ZHA

You can run these python programs anywhere you can launch your browser to get to your Home Assistant server, not necessary to run on the server itself. Don't try to run them within HA, they will not run inside the HA python environment. These are python 3 programs. The python import files you will need to PIP3 install are found in the requirements.txt file in this repository:

```
 pip3 install -r requirements.txt
 ```

These programs retrieve the same data from the ZHA subsystem of HA as the ZHA network visualization page in HA, these programs just display the data in a different format and collect the data overtime into a SQLite database that you can query and see changes to your zigbee network and devices over time.

Change the HA server IP address in this variable if you are not running these programs on the HA server:
```
HOME_ASSISTANT_IP = "localhost"
```
Add a Home Assistant Long-Lived Access Token and IP address of your Home Assistant server in the code of each program, variable is:
```
ACCESS_TOKEN = ''
```

#ws05.py :

has better error handling and is logging less data (not including raw json) to sqlite database so it does not grow so fast

#ws04.py :

stores all the raw json data retrieved in the SQLite database

This program tries to display ZHA devices based on their 'neighbor' relationship. It also records a SQLite database of the data returned by each web socket call to ZHA. Devices seems to stay in ZHA until you delete them, so this routine displays and records when a device goes 'OFFLINE' to the ZHA coordinator. It also records the length of time between when the coordinator sees a device and the devices RSSI and LQI values. Still trying to understand how to interpret this data.
Run this program in tmux or other background way to have it collect data over time. And also so you can get another view of the current state of your ZHA zigbee network.

Example output:

![alt text](https://github.com/deepcoder/ha-zha-query-tools/blob/main/ws04-display.png?raw=true)

Example SQLite database records:

![alt text](https://github.com/deepcoder/ha-zha-query-tools/blob/main/ws04-sqlite-db.png?raw=true)

#ws02.py

This program just loops and dumps in JSON format the current ZHA devices database via web sockets. Two examples below of how to use jq linux JSON utility to display records:

This JSON parser will give you a good overview of the records returned by ZHA, run the program ws02.py and let it capture one query of the ZHA devices, paste it into this tool:
http://jsonviewer.stack.hu/

```
# current date and time in local time, ieee address, device name, lqi
./ws02.py | jq -c '.result[] | {date: (now|strflocaltime("%Y-%m-%d %H:%M:%S%Z")), ieee: .ieee, name: .name, lqi: .lqi}'
{"date":"2021-01-07 22:31:16PST","ieee":"60:a4:23:ff:fe:dd:22:aa","name":"Silicon Labs EZSP","lqi":255}
{"date":"2021-01-07 22:31:16PST","ieee":"f0:d1:b8:00:00:09:34:be","name":"LEDVANCE PLUG","lqi":196}
{"date":"2021-01-07 22:31:16PST","ieee":"00:15:8d:00:02:ab:56:02","name":"LUMI lumi.weather","lqi":255}
```


```
# UTC Timestamp
./ws02.py | jq -c '.result[] | {date: (now|strftime("%s")), ieee: .ieee, name: .name, lqi: .lqi}'
{"date":"1610116915","ieee":"60:a4:23:ff:fe:a3:22:08","name":"Silicon Labs EZSP","lqi":255}
{"date":"1610116915","ieee":"f0:d1:b8:00:00:56:4a:8e","name":"LEDVANCE PLUG","lqi":196}
{"date":"1610116915","ieee":"00:15:8d:00:02:ba:f5:02","name":"LUMI lumi.weather","lqi":255}
```

```
# display only EndDevices:
./ws02.py | jq -c '.result[]  | select( .device_type == "EndDevice" )  | {date: (now|strflocaltime("%Y-%m-%d %H:%M:%S%Z")), ieee: .ieee, name: .name, device_type: .device_type, lqi: .lqi}'
{"date":"2021-01-08 10:37:45PST","ieee":"00:15:8d:00:02:22:f5:72","name":"LUMI lumi.weather","device_type":"EndDevice","lqi":255}
{"date":"2021-01-08 10:37:45PST","ieee":"28:6d:97:00:01:a2:0e:05","name":"Samjin multi","device_type":"EndDevice","lqi":192}
{"date":"2021-01-08 10:37:45PST","ieee":"00:15:8d:00:02:a6:07:c5","name":"LUMI lumi.sensor_motion.aq2","device_type":"EndDevice","lqi":212}
```

```
# display the children that are end devices
# this needs work, getting duplicates and need to show parent as well
./ws02.py | jq -c '.result[]  |
select( .neighbors[].relationship == "Child" )  |
select(.neighbors[].relationship == "Child") |
select(.neighbors[].relationship == "Child") | .neighbors[] | select(.device_type == "EndDevice") | {ieee: .ieee, depth: .depth, lqi: .lqi}'
{"ieee":"d0:52:a8:00:31:61:00:03","depth":"1","lqi":"183"}
{"ieee":"00:15:8d:00:02:c2:05:c2","depth":"1","lqi":"255"}
{"ieee":"00:15:8d:00:02:74:07:35","depth":"1","lqi":"213"}
{"ieee":"00:15:8d:00:02:ca:f0:17","depth":"1","lqi":"173"}
{"ieee":"00:15:8d:00:02:c6:dd:96","depth":"1","lqi":"194"}
{"ieee":"d0:52:a8:00:31:61:00:03","depth":"1","lqi":"183"}

```




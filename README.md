# ha-zha-query-tools
Python tools to get zigbee device info from Home Assistant ZHA

ws02.py

Add a Home Assistant Long-Lived Access Token. The web socket address is coded to localhost.

This JSON parser will give you a good overview of the records returned by ZHA, run the program ws02.py and let it capture one query of the ZHA devices, paste it into this tool:
http://jsonviewer.stack.hu/

This program just loops and dumps in JSON format the current ZHA devices database via web sockets. Two examples below of how to use jq linux JSON utility to display records:

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

ws03.py

Add a Home Assistant Long-Lived Access Token and IP address of your Home Assistant server.
This program will loop and collect the zigbee devices found and their JSON addributes into a SQLite database table.

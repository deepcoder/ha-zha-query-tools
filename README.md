# ha-zha-query-tools
Python tools to get zigbee device info from Home Assistant ZHA

ws02.py

Add a Home Assistant Long-Lived Access Token. The web socket address is coded to localhost. This program just loops and dumps in JSON format the current ZHA devices database via web sockets. Two examples below of how to use jq linux JSON utility to display records:

```
# current date and time in local time, ieee address, device name, lqi
./ws02.py | jq -c '.result[] | {date: (now|strflocaltime("%Y-%m-%d %H:%M:%S%Z")), ieee: .ieee, name: .name, lqi: .lqi}'
{"date":"2021-01-07 22:31:16PST","ieee":"60:a4:23:ff:fe:dd:22:aa","name":"Silicon Labs EZSP","lqi":255}
{"date":"2021-01-07 22:31:16PST","ieee":"f0:d1:b8:00:00:09:34:be","name":"LEDVANCE PLUG","lqi":196}
{"date":"2021-01-07 22:31:16PST","ieee":"00:15:8d:00:02:ab:56:02","name":"LUMI lumi.weather","lqi":255}
```


```
#UTC Timestamp
./ws02.py | jq -c '.result[] | {date: (now|strftime("%s")), ieee: .ieee, name: .name, lqi: .lqi}'
{"date":"1610116915","ieee":"60:a4:23:ff:fe:a3:22:08","name":"Silicon Labs EZSP","lqi":255}
{"date":"1610116915","ieee":"f0:d1:b8:00:00:56:4a:8e","name":"LEDVANCE PLUG","lqi":196}
{"date":"1610116915","ieee":"00:15:8d:00:02:ba:f5:02","name":"LUMI lumi.weather","lqi":255}
```

ws03.py

Add a Home Assistant Long-Lived Access Token and IP address of your Home Assistant server.
This program will loop and collect the zigbee devices found and their JSON addributes into a SQLite database table.

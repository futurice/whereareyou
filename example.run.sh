SLAVE_ID="SLAVE_ID"
FLOW_TOKEN="FLOW_TOKEN"
INTERFACE="wlan0"
NETWORK="ItHurtsWhenIP"
MASTER_ADDRESS="https://192.168.0.2:5000"
CMD="sudo airmon-ng start $INTERFACE; /usr/bin/python slave.py --network $NETWORK --wifi-interface mon0 --slave-id $SLAVE_ID --master-address $MASTER_ADDRESS"
eval $CMD
STATUS=$?
MSG="Slave '$SLAVE_ID' terminated with exit code $STATUS"
curl -X POST -H "Content-Type: application/json" https://api.flowdock.com/v1/messages/chat/$FLOW_TOKEN -d "{\"event\": \"message\", \"external_user_name\": \"ErrorTracker\", \"content\": \"$MSG\"}"

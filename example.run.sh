SLAVE_ID="SLAVE_ID"
FLOW_TOKEN="FLOW_TOKEN"
INTERFACE="wlan0"
NETWORK="ItHurtsWhenIP"
MASTER_ADDRESS="https://192.168.0.2:5000"
STD_OUT="stdout.txt"
ERROR_FILE="error.txt"
CMD="sudo airmon-ng start $INTERFACE; /usr/bin/python -W slave.py --network $NETWORK --wifi-interface mon0 --slave-id $SLAVE_ID --master-address $MASTER_ADDRESS > $STD_OUT 2> $ERROR_FILE"
eval $CMD
STATUS=$?
STD_TAIL=$(tail -n 20 $STD_OUT)
ERROR_TAIL=$(tail -n 20 $ERROR_FILE)
MSG="@team Slave '$SLAVE_ID' terminated with exit code $STATUS: $STD_TAIL $ERROR_TAIL"
curl -X POST -H "Content-Type: application/json" https://api.flowdock.com/v1/messages/chat/$FLOW_TOKEN -d "{\"event\": \"message\", \"external_user_name\": \"SlaveDied\", \"content\": \"$MSG\"}"

#!/usr/bin/python
# -*- coding: iso-8859-15 -*-

import pandas as pd
import argparse
import subprocess
import os
import time
import traceback
import requests
from tqdm import tqdm
from urllib import urlencode
from urllib import urlopen
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class Slave(object):
    LOG_FILE = 'airodump-log'
    FNULL = open(os.devnull, 'w')
    AIRODUMP_KILL_COMMAND = 'sudo killall airodump-ng'
    REMOVE_CSV_FILES_COMMAND = 'sudo rm -rf *.csv'
    WAITING_DELAY = 15
    UPDATE_INTERVAL = 5
    MAXIMUM_AGE = 5 * 60

    def __init__(self, network_name, wifi_interface, slave_id, master_address):
        self.network_name = network_name
        self.wifi_interface = wifi_interface
        self.slave_id = slave_id
        self.master_address = master_address
        self.access_point_mac = None
        self.airodump_command = "sudo airodump-ng --output-format csv --write {} {}".format(Slave.LOG_FILE, wifi_interface)

    def start_wifi_monitoring(self):
        print "Starting background Wifi monitoring ..."
        os.system(Slave.REMOVE_CSV_FILES_COMMAND)
        subprocess.Popen(self.airodump_command.split(" "), shell=False, stdout=Slave.FNULL, stderr=subprocess.STDOUT)

    def run(self):
        for _ in tqdm(range(Slave.WAITING_DELAY)):
            time.sleep(1)
        if not os.path.isfile(Slave.LOG_FILE + '-01.csv'):
            raise Exception(Slave.LOG_FILE + '-01.csv does not exist. Please make sure "' + self.airodump_command + '" succeeds.')
        try:
            df = pd.read_csv(Slave.LOG_FILE + '-01.csv', engine='c', error_bad_lines=False)
        except:
            raise Exception("Can't read data CSV - content: " + open(Slave.LOG_FILE + "-01.csv").read())
        df = df.rename(index=str, columns=dict(zip(df.columns, [str(c).strip() for c in df.columns])))
        df[["ESSID", "BSSID"]] = df[["ESSID", "BSSID"]].apply(lambda x: x.str.strip())
        self.access_point_mac = df.loc[df["ESSID"] == self.network_name].BSSID.unique()[0]
        while True:
            for _ in tqdm(range(Slave.UPDATE_INTERVAL)):
                time.sleep(1)
            df = pd.read_csv(Slave.LOG_FILE + '-01.csv', engine='c', error_bad_lines=False)
            df_stations = self.get_stations(df)
            if len(df_stations) > 0:
                self.send_measurements_to_server(df_stations)
                print df_stations.to_string(index=False)
            else:
                print "No nearby connected Wifi devices found"

    def stop_wifi_monitoring(self):
        print "Stopping background Wifi monitoring ..."
        os.system(Slave.AIRODUMP_KILL_COMMAND)

    def get_stations(self, df):
        station_index = df.loc[df["BSSID"] == "Station MAC"].index[0]
        df_stations = df.loc[station_index:, :]

        new_header = df_stations.loc[station_index]
        df_stations = df_stations.loc[station_index + 1:]
        df_stations = df_stations.rename(columns=new_header)
        return self.get_relevant_stations(df_stations)

    def get_relevant_stations(self, df):
        df_stations = df.copy()
        df_stations = df_stations.rename(index=str, columns=dict(zip(df_stations.columns, [str(c).strip() for c in df_stations.columns])))
        df_stations = df_stations[["Station MAC", "Last time seen", "BSSID", "Power"]]
        time_pattern = ' %Y-%m-%d %H:%M:%S'
        try:
            df_stations["Last time seen"] = df_stations["Last time seen"].apply(lambda x: int(time.mktime(time.strptime(x, time_pattern))))
        except:
            raise Exception("Can't parse " + df_stations["Last time seen"])
        df_stations["Time delta"] = (time.time() - df_stations["Last time seen"])
        df_stations = df_stations[df_stations["Time delta"] < Slave.MAXIMUM_AGE]
        #df_stations = df_stations.loc[df_stations["BSSID"] == self.access_point_mac]
        df_stations = df_stations[df_stations["Power"].astype(int) < 0]
        return df_stations[["Station MAC", "Power", "Last time seen", "Time delta"]]


    def send_measurements_to_server(self, df):
        data = []
        for _, row in df.iterrows():
            data.append({
              'mac': row["Station MAC"],
              'power': row["Power"],
              'last_seen': str(row["Last time seen"])
            })
        requests.post(self.master_address + '/update', json={'slave_id': self.slave_id, 'data': data}, verify=False)


def send_notification_to_flowdock(content):
    flowdock_token = os.environ.get("FLOW_TOKEN", None)
    if flowdock_token:
        params = urlencode({
            'event': 'message',
            'external_user_name': 'ErrorTracker',
            'content': content
        })
        urlopen('https://api.flowdock.com/v1/messages/chat/' + flowdock_token, params)


def main():
    parser = argparse.ArgumentParser(description='Monitor nearby Wifi devices that are connected to the same network')
    parser.add_argument('-n', '--network', required=True, help='Name of the shared network')
    parser.add_argument('-w', '--wifi-interface', required=True, help='Name of the Wifi network interface e.g. wlan0 or wlp3s0')
    parser.add_argument('-s', '--slave-id', required=True, help='Unique identifier of the slave device')
    parser.add_argument('-m', '--master-address', required=True, help='URL and port of the master device e.g. http://192.168.1.2:5000')
    args = parser.parse_args()
    network_name, wifi_interface, slave_id, master_address = args.network, args.wifi_interface, args.slave_id, args.master_address
    slave = Slave(network_name, wifi_interface, slave_id, master_address)
    while True:
        try:
            slave.start_wifi_monitoring()
            slave.run()
        except Exception, e:
            slave.stop_wifi_monitoring()
            stack_trace = traceback.format_exc()
            message = "@team Exception '{e}' from Slave '{slave_id}' for network {network_name} with interface {wifi_interface} with master {master_address}: {stack_trace}".format(**locals())
            send_notification_to_flowdock(message)
            time.sleep(60)


if __name__ == '__main__':
    main()

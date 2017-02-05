import pandas as pd
import argparse
import subprocess
import os
import time

NETWORK_NAME = None
ACCESS_POINT_MAC = None
WIFI_INTERFACE = None
LOG_FILE = 'airodump-log'

FNULL = open(os.devnull, 'w')
AIRMON_COMMAND = None
AIRODUMP_COMMAND = None
AIRODUMP_KILL_COMMAND = 'sudo killall airodump-ng'
REMOVE_CSV_FILES_COMMAND = 'sudo rm -rf *.csv'


def main():
    global NETWORK_NAME, WIFI_INTERFACE, AIRMON_COMMAND, AIRODUMP_COMMAND
    parser = argparse.ArgumentParser(description='Monitor nearby Wifi devices that are connected to the same network')
    parser.add_argument('-n', '--network', required=True, help='Name of the shared network')
    parser.add_argument('-w', '--wifi-interface', required=True, help='Name of the Wifi network interface e.g. wlan0 or wlp3s0')
    args = parser.parse_args()
    NETWORK_NAME = args.network
    WIFI_INTERFACE = args.wifi_interface
    AIRMON_COMMAND = 'sudo airmon-ng start ' + WIFI_INTERFACE
    AIRODUMP_COMMAND = "sudo airodump-ng --output-format csv --write {} {}".format(LOG_FILE, WIFI_INTERFACE)

    try:
        global ACCESS_POINT_MAC
        start_wifi_monitoring()
        time.sleep(15)
        if not os.path.isfile(LOG_FILE + '-01.csv'):
            raise Exception(LOG_FILE + '-01.csv does not exist. Please make sure "' + AIRODUMP_COMMAND + '" succeeds.')
        df = pd.read_csv(LOG_FILE + '-01.csv', delimiter=' *, *', engine='python')
        ACCESS_POINT_MAC = df.loc[df["ESSID"] == NETWORK_NAME].BSSID.unique()[0]
        while True:
            time.sleep(15)
            df = pd.read_csv(LOG_FILE + '-01.csv', delimiter=' *, *', engine='python')
            df_stations = get_stations(df)
            if len(df_stations) > 0:
                print df_stations.to_string(index=False)
            else:
                print "No nearby connected Wifi devices found"
    except Exception, e:
        stop_wifi_monitoring()
        print e


def start_wifi_monitoring():
    print "Starting background Wifi monitoring ..."
    os.system(REMOVE_CSV_FILES_COMMAND)
    subprocess.Popen(AIRODUMP_COMMAND.split(" "), shell=False, stdout=FNULL, stderr=subprocess.STDOUT)


def stop_wifi_monitoring():
    print "Stopping background Wifi monitoring ..."
    os.system(AIRODUMP_KILL_COMMAND)


def get_stations(df):
    station_index = df.loc[df["BSSID"] == "Station MAC"].index[0]
    df_stations = df.loc[station_index:, :]

    new_header = df_stations.loc[station_index]
    df_stations = df_stations.loc[station_index + 1:]
    df_stations = df_stations.rename(columns=new_header)
    return get_relevant_stations(df_stations)


def get_relevant_stations(df_stations):
    df_stations = df_stations[["Station MAC", "BSSID", "Power"]]
    df_stations = df_stations.loc[df_stations["BSSID"] == ACCESS_POINT_MAC]
    df_stations = df_stations[df_stations["Power"].astype(int) < 0]
    return df_stations[["Station MAC", "Power"]]


if __name__ == '__main__':
    main()

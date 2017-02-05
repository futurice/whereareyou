import pandas as pd
import argparse
import subprocess
import os
import time


class Slave(object):
    LOG_FILE = 'airodump-log'
    FNULL = open(os.devnull, 'w')
    AIRODUMP_KILL_COMMAND = 'sudo killall airodump-ng'
    REMOVE_CSV_FILES_COMMAND = 'sudo rm -rf *.csv'
    TIME_DELAY = 15

    def __init__(self, network_name, wifi_interface):
        self.network_name = network_name
        self.wifi_interface = wifi_interface
        self.access_point_mac = None
        self.airodump_command = "sudo airodump-ng --output-format csv --write {} {}".format(Slave.LOG_FILE, wifi_interface)

    def start_wifi_monitoring(self):
        print "Starting background Wifi monitoring ..."
        os.system(Slave.REMOVE_CSV_FILES_COMMAND)
        subprocess.Popen(self.airodump_command.split(" "), shell=False, stdout=Slave.FNULL, stderr=subprocess.STDOUT)

    def run(self):
        time.sleep(Slave.TIME_DELAY)
        if not os.path.isfile(Slave.LOG_FILE + '-01.csv'):
            raise Exception(Slave.LOG_FILE + '-01.csv does not exist. Please make sure "' + self.airodump_command + '" succeeds.')
        df = pd.read_csv(Slave.LOG_FILE + '-01.csv', delimiter=' *, *', engine='python')
        self.access_point_mac = df.loc[df["ESSID"] == self.network_name].BSSID.unique()[0]
        while True:
            time.sleep(Slave.TIME_DELAY)
            df = pd.read_csv(Slave.LOG_FILE + '-01.csv', delimiter=' *, *', engine='python')
            df_stations = self.get_stations(df)
            if len(df_stations) > 0:
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

    def get_relevant_stations(self, df_stations):
        df_stations = df_stations[["Station MAC", "BSSID", "Power"]]
        df_stations = df_stations.loc[df_stations["BSSID"] == self.access_point_mac]
        df_stations = df_stations[df_stations["Power"].astype(int) < 0]
        return df_stations[["Station MAC", "Power"]]


def main():
    parser = argparse.ArgumentParser(description='Monitor nearby Wifi devices that are connected to the same network')
    parser.add_argument('-n', '--network', required=True, help='Name of the shared network')
    parser.add_argument('-w', '--wifi-interface', required=True, help='Name of the Wifi network interface e.g. wlan0 or wlp3s0')
    args = parser.parse_args()
    slave = Slave(args.network, args.wifi_interface)
    try:
        slave.start_wifi_monitoring()
        slave.run()
    except Exception, e:
        slave.stop_wifi_monitoring()
        print e


if __name__ == '__main__':
    main()

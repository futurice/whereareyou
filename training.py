from sklearn.tree import DecisionTreeClassifier, export_graphviz
from sklearn.preprocessing import LabelEncoder
from sklearn.externals import joblib
import pandas as pd
import os
import datetime

MODEL_NAME = 'model.pkl'
MODEL_MAC_NAME = 'model_mac.pkl'
MAXIMUM_AGE = 60
POWER_SLAVE_PREFIX = "Power_Slave_"
OLD_TIME_DELTA_MINUTES = 5

without_mac_clf = None
mac_clf = None


def train_models(data):
    #train_model(data, with_mac=True)
    train_model(data, with_mac=False)


def train_model(data, with_mac=True):
    global without_mac_clf, mac_clf
    df = pd.DataFrame.from_dict(data)
    y = df.pop("location")
    features = [f for f in df.columns if f is not 'mac']
    df = df.rename(columns=dict(zip(features, [POWER_SLAVE_PREFIX + f for f in features])))
    model_name = MODEL_MAC_NAME if with_mac else MODEL_NAME
    if with_mac:
        df = df.apply(LabelEncoder().fit_transform)
    else:
        df.drop("mac", axis=1, inplace=True)
    clf = DecisionTreeClassifier()
    clf.fit(df, y)
    joblib.dump(clf, model_name)
    if with_mac and mac_clf is None:
        mac_clf = clf
    if not with_mac and without_mac_clf is None:
        without_mac_clf = clf
    export_graphviz(clf, feature_names=list(df.columns), class_names=y.unique(), filled=True, rounded=True, out_file='model.dot')
    os.system("dot -Tpng model.dot -o model.png")


def measurement_too_old(measurement):
    return measurement.last_seen < datetime.datetime.now() - datetime.timedelta(minutes=OLD_TIME_DELTA_MINUTES)


def get_df_from_detection(detection_list):
    detection_data = []
    for det in detection_list:
        json_data = det.serialize()
        if len(json_data["measurements"]) == 0:
            continue
        most_recent_timestamp = max([m["last_seen"] for m in json_data["measurements"]])
        most_recent_timestamp = datetime.datetime.fromtimestamp(most_recent_timestamp)
        if most_recent_timestamp < datetime.datetime.now() - datetime.timedelta(minutes=MAXIMUM_AGE):
            continue
        else:
            for m in json_data["measurements"]:
                power = m["power"]
                if datetime.datetime.fromtimestamp(m["last_seen"]) < most_recent_timestamp - datetime.timedelta(minutes=OLD_TIME_DELTA_MINUTES):
                    power = -100
                json_data[POWER_SLAVE_PREFIX + m["slave_id"]] = power
            del json_data["measurements"]
            json_data["most_recent_seen"] = most_recent_timestamp
            detection_data.append(json_data)
    df = pd.DataFrame(detection_data)
    return df


def predict_location(df):
    global without_mac_clf
    if without_mac_clf is None:
        without_mac_clf = joblib.load(MODEL_NAME)
    clf = without_mac_clf
    df.fillna(-100, inplace=True)
    df['predicted_location'] = clf.predict(df[[c for c in df.columns if c.startswith(POWER_SLAVE_PREFIX)]])
    return df
